"""Google Play: отзывы через библиотеку google-play-scraper.

Google Play делит отзывы по ЯЗЫКУ, а не по стране: для by и ru приходит один и тот же
русскоязычный поток. Поэтому сбор идёт один раз на язык, рынок помечается как lang-ru и т.п.
"""
from __future__ import annotations

from ..models import Review

# язык отзывов по умолчанию для страны
LANG = {"by": "ru", "ru": "ru", "kz": "ru", "ua": "uk", "us": "en", "gb": "en",
        "de": "de", "fr": "fr", "es": "es", "it": "it", "pl": "pl", "tr": "tr",
        "br": "pt", "rs": "sr"}


def find_app(name: str, country: str, lang: str) -> tuple[str, str] | None:
    from google_play_scraper import search

    for hit in search(name, n_hits=5, lang=lang, country=country):
        if hit.get("appId"):
            return hit["appId"], hit.get("title", "")
    return None


def to_review(item: dict, brand: str, lang: str, app_id: str, product: str) -> Review:
    at = item.get("at")
    return Review(
        brand=brand,
        source="google_play",
        market=f"lang-{lang}",
        date=at.strftime("%Y-%m-%d") if at else "",
        rating=float(item["score"]) if item.get("score") else None,
        text=item.get("content") or "",
        version=item.get("reviewCreatedVersion") or "",
        url=f"https://play.google.com/store/apps/details?id={app_id}&hl={lang}",
        product=product,
        id=f"gp-{lang}-{item.get('reviewId', '')}" if item.get("reviewId") else "",
    ).finalize()


def collect(brand: str, lang: str, app_id: str | None, limit: int = 1000,
            country: str = "us") -> list[Review]:
    from google_play_scraper import Sort, reviews

    product = ""
    if not app_id:
        found = find_app(brand, country, lang)
        if not found:
            raise RuntimeError(f"приложение «{brand}» не найдено в Google Play ({country})")
        app_id, product = found
    out: list[Review] = []
    token = None
    while len(out) < limit:
        batch, token = reviews(
            app_id, lang=lang, country=country, sort=Sort.NEWEST,
            count=min(200, limit - len(out)), continuation_token=token,
        )
        if not batch:
            break
        out.extend(to_review(i, brand, lang, app_id, product) for i in batch)
        if token is None or getattr(token, "token", None) is None:
            break
    out = [r for r in out if r.text]
    if not out:
        raise RuntimeError(f"0 отзывов для {app_id} (язык {lang}) — проверьте id")
    return out
