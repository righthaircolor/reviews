"""2ГИС: отзывы о филиале (точке) по его id из ссылки 2gis.ru/.../firm/<id>."""
from __future__ import annotations

import re
import time

import requests

from ..models import Review

UA = {"User-Agent": "Mozilla/5.0 (reviews-collector)"}
# общий ключ, с которым работает сам сайт 2gis.ru; можно заменить переменной TWOGIS_KEY
import os
KEY = os.environ.get("TWOGIS_KEY", "6e7e1929-4ea9-4a5d-8c05-d601860389bd")


def branch_id(value) -> str:
    m = re.search(r"(\d{10,})", str(value))
    if not m:
        raise ValueError(f"не похоже на id филиала 2ГИС: {value}")
    return m.group(1)


def to_review(rv: dict, brand: str, market: str, bid: str) -> Review:
    return Review(
        brand=brand, source="2gis", market=market,
        date=str(rv.get("date_created") or "")[:10],
        rating=float(rv["rating"]) if rv.get("rating") else None,
        text=rv.get("text") or "",
        url=f"https://2gis.ru/firm/{bid}/tab/reviews",
        product=f"филиал {bid}",
        id=f"2gis-{rv['id']}" if rv.get("id") else "",
    ).finalize()


def collect(brand: str, branch, market: str = "ru", limit: int = 500) -> list[Review]:
    bid = branch_id(branch)
    url = f"https://public-api.reviews.2gis.com/2.0/branches/{bid}/reviews"
    params = {"limit": 50, "is_advertiser": "false", "rated": "true",
              "sort_by": "date_edited", "key": KEY, "locale": "ru_RU",
              "fields": "meta.branch_rating,meta.total_count"}
    out: list[Review] = []
    while url and len(out) < limit:
        r = requests.get(url, params=params, headers=UA, timeout=30)
        if r.status_code != 200:
            if not out:
                raise RuntimeError(f"2ГИС ответил {r.status_code} для филиала {bid}")
            break
        j = r.json()
        items = j.get("reviews") or []
        out.extend(to_review(rv, brand, market, bid) for rv in items)
        url, params = (j.get("meta") or {}).get("next_link"), None
        if not items:
            break
        time.sleep(0.3)
    out = [r for r in out if r.text][:limit]
    if not out:
        raise LookupError(f"у филиала {bid} нет отзывов в 2ГИС")
    return out
