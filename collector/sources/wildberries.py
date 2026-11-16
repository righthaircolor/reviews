"""Wildberries: отзывы на товары бренда. Работает только с домашнего компьютера —
серверам GitHub площадка отвечает отказом.

Ищет товары по запросу, оставляет те, у которых бренд совпадает с запросом,
берёт самые обсуждаемые и собирает отзывы. Отзывы на WB общие для всех стран.
"""
from __future__ import annotations

import time

import requests

from ..models import Review

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "*/*", "Origin": "https://www.wildberries.ru",
      "Referer": "https://www.wildberries.ru/"}
SEARCH_VERSIONS = ["v18", "v14", "v13", "v9", "v7", "v5", "v4"]


def _products(j: dict) -> list[dict]:
    return (j.get("products") or (j.get("data") or {}).get("products") or [])


def find_products(query: str, max_products: int, pages: int = 3) -> list[dict]:
    words = query.lower().split()
    found: dict[int, dict] = {}
    version = None
    for page in range(1, pages + 1):
        items = None
        for v in ([version] if version else SEARCH_VERSIONS):
            r = requests.get(
                f"https://search.wb.ru/exactmatch/ru/common/{v}/search",
                params={"ab_testing": "false", "appType": 1, "curr": "rub", "dest": -1257786,
                        "lang": "ru", "page": page, "query": query, "resultset": "catalog",
                        "sort": "popular", "spp": 30, "suppressSpellcheck": "false"},
                headers=UA, timeout=30)
            if r.status_code == 200:
                try:
                    items = _products(r.json())
                except ValueError:
                    items = None
                if items:
                    version = v
                    break
            elif r.status_code in (403, 429) and v == SEARCH_VERSIONS[-1] and page == 1:
                raise RuntimeError(f"Wildberries ответил отказом ({r.status_code})")
        if not items:
            break
        for p in items:
            brand = (p.get("brand") or "").lower()
            if p.get("root") and (p.get("feedbacks") or 0) > 0 and all(w in brand for w in words):
                found.setdefault(p["root"], p)  # root общий у вариантов одного товара
        time.sleep(0.5)
    top = sorted(found.values(), key=lambda p: p.get("feedbacks") or 0, reverse=True)
    return top[:max_products]


def parse_feedbacks(j: dict, brand: str, market: str, product: dict) -> list[Review]:
    out = []
    for f in j.get("feedbacks") or []:
        parts = [f.get("text") or ""]
        if (f.get("pros") or "").strip():
            parts.append("Плюсы: " + f["pros"].strip())
        if (f.get("cons") or "").strip():
            parts.append("Минусы: " + f["cons"].strip())
        nm = f.get("nmId") or product.get("id")
        out.append(Review(
            brand=brand, source="wildberries", market=market,
            date=str(f.get("createdDate") or "")[:10],
            rating=float(f["productValuation"]) if f.get("productValuation") else None,
            text="\n".join(p for p in parts if p.strip()),
            url=f"https://www.wildberries.ru/catalog/{nm}/feedbacks",
            product=product.get("name") or "",
            id=f"wb-{f['id']}" if f.get("id") else "",
        ).finalize())
    return [r for r in out if r.text]


def feedbacks(root) -> dict:
    for host in ("feedbacks1", "feedbacks2"):
        for v in ("v2", "v1"):
            try:
                r = requests.get(f"https://{host}.wb.ru/feedbacks/{v}/{root}", headers=UA, timeout=30)
                if r.status_code == 200 and (r.json().get("feedbacks")):
                    return r.json()
            except (requests.RequestException, ValueError):
                continue
    return {}


def collect(brand: str, query: str, market: str = "ru", limit: int = 2000,
            max_products: int = 15) -> list[Review]:
    products = find_products(query, max_products)
    if not products:
        raise LookupError(f"на Wildberries нет товаров бренда «{query}» с отзывами")
    seen: dict[str, Review] = {}
    for p in products:
        for rev in parse_feedbacks(feedbacks(p["root"]), brand, market, p):
            seen.setdefault(rev.id, rev)
        time.sleep(0.5)
    if not seen:
        raise RuntimeError("товары найдены, но отзывы Wildberries не отдал")
    newest = sorted(seen.values(), key=lambda r: r.date, reverse=True)
    return newest[:limit]
