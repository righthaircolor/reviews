"""Яндекс Карты: отзывы об организации по её id из ссылки yandex.ru/maps/org/.../<id>.

Страница отдаёт около 50 отзывов (в порядке «по умолчанию»), больше без браузера не получить.
"""
from __future__ import annotations

import re

import requests

from ..models import Review
from . import url_extract


def org_id(value) -> str:
    m = re.search(r"(\d{6,})", str(value))
    if not m:
        raise ValueError(f"не похоже на id организации Яндекс Карт: {value}")
    return m.group(1)


def collect(brand: str, org, market: str = "ru") -> list[Review]:
    oid = org_id(org)
    url = f"https://yandex.ru/maps/org/{oid}/reviews/"
    r = requests.get(url, headers=url_extract.UA, timeout=40)
    r.raise_for_status()
    if "showcaptcha" in r.url:
        raise RuntimeError("Яндекс показал капчу — попробуйте позже")
    items, _ = url_extract.extract(r.text)
    m = re.search(r"<title>(.*?)</title>", r.text, re.S)
    place = (m.group(1).split(" — ")[0].strip() if m else "") or f"организация {oid}"
    out = [
        Review(brand=brand, source="yandex_maps", market=market,
               date=str(i.get("date") or "")[:10], rating=url_extract._num(i.get("rating")),
               text=str(i.get("text") or ""), url=url, product=place).finalize()
        for i in items
    ]
    if not out:
        raise LookupError(f"отзывы организации {oid} не найдены на Яндекс Картах")
    return out
