"""Универсальный извлекатель: достаёт отзывы с любой открытой страницы.

1) Сначала читает структурированную разметку отзывов (schema.org: JSON-LD и microdata) —
   её ставят Trustpilot, многие отзовики и интернет-магазины.
2) Если разметки нет и задан секрет ANTHROPIC_API_KEY — просит ИИ вытащить отзывы из текста.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..models import Review

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "ru,en;q=0.8",
}
LLM_MODEL = os.environ.get("REVIEWS_LLM_MODEL", "claude-haiku-5-5")


def _num(v) -> float | None:
    try:
        f = float(str(v).replace(",", "."))
        return f if 0 < f <= 5 else None
    except (TypeError, ValueError):
        return None


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _is_review(d: dict) -> bool:
    t = d.get("@type")
    types = t if isinstance(t, list) else [t]
    return "Review" in types or "UserReview" in types


def from_jsonld(soup: BeautifulSoup) -> list[dict]:
    found = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for d in _walk(data):
            if not _is_review(d):
                continue
            body = d.get("reviewBody") or d.get("description") or ""
            if not isinstance(body, str) or not body.strip():
                continue
            rating = d.get("reviewRating") or {}
            found.append({
                "text": body,
                "title": d.get("headline") or d.get("name") or "",
                "rating": _num(rating.get("ratingValue")) if isinstance(rating, dict) else None,
                "date": str(d.get("datePublished") or "")[:10],
            })
    return found


def from_microdata(soup: BeautifulSoup) -> list[dict]:
    found = []
    for box in soup.find_all(attrs={"itemprop": "review"}):
        body = box.find(attrs={"itemprop": ["reviewBody", "description"]})
        if not body:
            continue
        rv = box.find(attrs={"itemprop": "ratingValue"})
        dt = box.find(attrs={"itemprop": "datePublished"})
        found.append({
            "text": body.get_text(" ", strip=True),
            "title": "",
            "rating": _num(rv.get("content") or rv.get_text(strip=True)) if rv else None,
            "date": ((dt.get("content") or dt.get("datetime") or dt.get_text(strip=True))
                     if dt else "")[:10],
        })
    return found


def from_llm(page_text: str, api_key: str) -> list[dict]:
    prompt = (
        "Ниже текст веб-страницы. Извлеки из него все пользовательские отзывы. "
        "Верни ТОЛЬКО JSON-массив объектов с полями: text (дословный текст отзыва), "
        "title, rating (число 1-5 или null), date (YYYY-MM-DD или \"\"). "
        "Не выдумывай отзывы и не включай имена авторов. Если отзывов нет — верни [].\n\n"
        + page_text[:60000]
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": LLM_MODEL, "max_tokens": 8000,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=180,
    )
    r.raise_for_status()
    answer = "".join(b.get("text", "") for b in r.json().get("content", []))
    m = re.search(r"\[.*\]", answer, re.S)
    items = json.loads(m.group(0)) if m else []
    return [i for i in items if isinstance(i, dict) and str(i.get("text") or "").strip()]


def extract(html: str) -> tuple[list[dict], str]:
    """Возвращает (отзывы, способ извлечения)."""
    soup = BeautifulSoup(html, "html.parser")
    items = from_jsonld(soup)
    if items:
        return items, "разметка JSON-LD"
    items = from_microdata(soup)
    if items:
        return items, "разметка microdata"
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        return from_llm(soup.get_text("\n", strip=True), key), "ИИ"
    return [], "нет разметки отзывов (для таких страниц нужен ключ ANTHROPIC_API_KEY)"


def collect(brand: str, url: str, market: str = "global") -> list[Review]:
    r = requests.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
    items, how = extract(r.text)
    if not items:
        raise RuntimeError(f"отзывы не найдены: {how}")
    host = urlparse(url).netloc.removeprefix("www.")
    return [
        Review(
            brand=brand, source=host, market=market,
            date=str(i.get("date") or "")[:10], rating=_num(i.get("rating")),
            title=str(i.get("title") or ""), text=str(i.get("text") or ""),
            url=url, product=host,
        ).finalize()
        for i in items
    ]
