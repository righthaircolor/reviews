"""Trustpilot: отзывы о компании по её домену. Работает только с домашнего компьютера —
серверам GitHub площадка отвечает отказом.

Рынок отзыва — страна автора, если Trustpilot её показывает.
"""
from __future__ import annotations

import json
import re
import time

import requests

from ..models import Review
from . import url_extract


def domain_of(value: str) -> str:
    v = str(value).strip()
    m = re.search(r"trustpilot\.com/review/([^/?#]+)", v)
    if m:
        return m.group(1)
    return re.sub(r"^https?://(www\.)?", "", v).split("/")[0]


def parse_page(html: str, brand: str, domain: str) -> tuple[list[Review], int]:
    """Возвращает (отзывы, всего страниц)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return [], 0
    props = (json.loads(m.group(1)).get("props") or {}).get("pageProps") or {}
    pages = (((props.get("filters") or {}).get("pagination")) or {}).get("totalPages") or 1
    out = []
    for rv in props.get("reviews") or []:
        country = ((rv.get("consumer") or {}).get("countryCode") or "").lower()
        date = ((rv.get("dates") or {}).get("publishedDate") or "")[:10]
        out.append(Review(
            brand=brand, source="trustpilot", market=country or "global",
            date=date, rating=float(rv["rating"]) if rv.get("rating") else None,
            title=rv.get("title") or "", text=rv.get("text") or "",
            url=f"https://www.trustpilot.com/reviews/{rv['id']}" if rv.get("id")
                else f"https://www.trustpilot.com/review/{domain}",
            product=domain,
            id=f"tp-{rv['id']}" if rv.get("id") else "",
        ).finalize())
    return [r for r in out if r.text], pages


def collect(brand: str, domain: str, limit: int = 1000) -> list[Review]:
    domain = domain_of(domain)
    out: dict[str, Review] = {}
    page, pages = 1, 1
    while page <= pages and len(out) < limit:
        r = requests.get(f"https://www.trustpilot.com/review/{domain}",
                         params={"languages": "all", "sort": "recency", "page": page},
                         headers=url_extract.UA, timeout=40)
        if r.status_code == 404 and page == 1:
            raise LookupError(f"компании {domain} нет на Trustpilot")
        if r.status_code != 200:
            if page == 1:
                raise RuntimeError(f"Trustpilot ответил отказом ({r.status_code})")
            break
        batch, pages = parse_page(r.text, brand, domain)
        if not batch:
            break
        for rev in batch:
            out.setdefault(rev.id, rev)
        page += 1
        time.sleep(1.0)
    if not out:
        raise LookupError(f"у {domain} нет отзывов на Trustpilot")
    return list(out.values())[:limit]
