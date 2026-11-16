"""Onliner (Беларусь): отзывы на товары бренда из каталога catalog.onliner.by.

Ищет товары по названию бренда, берёт те, у которых есть отзывы, и собирает их.
Цветовые варианты одного товара делят общие отзывы — дубли отсеиваются по id.
"""
from __future__ import annotations

import time

import requests

from ..models import Review

API = "https://catalog.onliner.by/sdapi/catalog.api"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def find_products(query: str, max_products: int, max_pages: int = 15) -> list[dict]:
    words = query.lower().split()
    found = []
    for page in range(1, max_pages + 1):
        r = requests.get(f"{API}/search/products", params={"query": query, "page": page},
                         headers=UA, timeout=30)
        if r.status_code != 200:
            break
        j = r.json()
        for p in j.get("products") or []:
            name = (p.get("full_name") or "").lower()
            if ((p.get("reviews") or {}).get("count") or 0) > 0 and all(w in name for w in words):
                found.append(p)
        if len(found) >= max_products or page >= ((j.get("page") or {}).get("last") or 1):
            break
        time.sleep(0.3)
    return found[:max_products]


def to_review(rv: dict, brand: str, product_name: str, html_url: str) -> Review:
    parts = [rv.get("text") or ""]
    if (rv.get("pros") or "").strip():
        parts.append("Плюсы: " + rv["pros"].strip())
    if (rv.get("cons") or "").strip():
        parts.append("Минусы: " + rv["cons"].strip())
    return Review(
        brand=brand, source="onliner", market="by",
        date=str(rv.get("created_at") or "")[:10],
        rating=float(rv["rating"]) if rv.get("rating") else None,
        title=rv.get("summary") or "",
        text="\n".join(p for p in parts if p.strip()),
        url=html_url,
        product=((rv.get("original_product") or {}).get("full_name")) or product_name,
        id=f"onl-{rv['id']}" if rv.get("id") else "",
    ).finalize()


def collect(brand: str, query: str, limit: int = 1000, max_products: int = 40) -> list[Review]:
    products = find_products(query, max_products)
    if not products:
        raise LookupError(f"на Onliner нет товаров «{query}» с отзывами")
    seen: dict[str, Review] = {}
    for p in products:
        html_url = (p.get("reviews") or {}).get("html_url") or p.get("html_url") or ""
        page = 1
        while len(seen) < limit:
            r = requests.get(f"{API}/products/{p['key']}/reviews",
                             params={"order": "created_at:desc", "page": page},
                             headers=UA, timeout=30)
            if r.status_code != 200:
                break
            j = r.json()
            for rv in j.get("reviews") or []:
                rev = to_review(rv, brand, p.get("full_name") or "", html_url)
                if rev.text:
                    seen.setdefault(rev.id, rev)
            if page >= ((j.get("page") or {}).get("last") or 1):
                break
            page += 1
            time.sleep(0.2)
        if len(seen) >= limit:
            break
    return list(seen.values())[:limit]
