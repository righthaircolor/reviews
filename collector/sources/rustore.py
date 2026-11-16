"""RuStore (Россия): открытый список отзывов приложения по имени пакета."""
from __future__ import annotations

import time

import requests

from ..models import Review

UA = {"User-Agent": "Mozilla/5.0 (reviews-collector)"}


def to_review(c: dict, brand: str, package: str) -> Review:
    return Review(
        brand=brand, source="rustore", market="ru",
        date=str(c.get("commentDate") or "")[:10],
        rating=float(c["appRating"]) if c.get("appRating") else None,
        text=c.get("commentText") or "",
        url=f"https://www.rustore.ru/catalog/app/{package}",
        product=package,
        id=f"rs-{c['commentId']}" if c.get("commentId") else "",
    ).finalize()


def collect(brand: str, package: str, limit: int = 1000) -> list[Review]:
    out: list[Review] = []
    page = 0
    while len(out) < limit:
        r = requests.get(
            "https://backapi.rustore.ru/comment/comment",
            params={"packageName": package, "pageNumber": page, "pageSize": 100,
                    "sortBy": "NEW_FIRST"},
            headers=UA, timeout=30,
        )
        if r.status_code != 200:
            if page == 0:
                raise LookupError(f"приложение {package} не найдено в RuStore (ответ {r.status_code})")
            break
        body = r.json().get("body") or {}
        items = body.get("content") or []
        out.extend(to_review(c, brand, package) for c in items)
        page += 1
        if not items or page >= (body.get("totalPages") or 0):
            break
        time.sleep(0.3)
    out = [r for r in out if r.text][:limit]
    if not out:
        raise LookupError(f"у {package} нет отзывов в RuStore")
    return out
