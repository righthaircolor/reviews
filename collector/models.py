"""Единый формат отзыва для всех источников."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass


@dataclass
class Review:
    brand: str
    source: str          # app_store | google_play | url
    market: str          # код страны: by, ru, us ... или global
    date: str            # ISO-дата YYYY-MM-DD ("" если неизвестна)
    rating: float | None  # 1..5 или None
    text: str
    title: str = ""
    version: str = ""    # версия приложения, если есть
    url: str = ""        # ссылка на первоисточник
    product: str = ""    # название приложения / страницы
    id: str = ""

    def finalize(self) -> "Review":
        self.text = (self.text or "").strip()
        self.title = (self.title or "").strip()
        if not self.id:
            raw = "|".join(
                [self.brand, self.source, self.market, self.date, self.title, self.text]
            )
            self.id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return self

    def to_dict(self) -> dict:
        return asdict(self)
