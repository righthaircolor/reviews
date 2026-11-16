"""Google Play: отзывы по стране и языку через библиотеку google-play-scraper."""
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


def to_review(item: dict, brand: str, country: str, app_id: str, product: str) -> Review:
    at = item.get("at")
    return Review(
        brand=brand,
        source="google_play",
        market=country,
        date=at.strftime("%Y-%m-%d") if at else "",
        rating=float(item["score"]) if item.get("score") else None,
        text=item.get("content") or "",
        version=item.get("reviewCreatedVersion") or "",
        url=f"https://play.google.com/store/apps/details?id={app_id}&gl={country}",
        product=product,
        id=f"gp-{country}-{item.get('reviewId', '')}" if item.get("reviewId") else "",
    ).finalize()


def collect(brand: str, country: str, app_id: str | None, limit: int = 1000,
            lang: str | None = None) -> list[Review]:
    from google_play_scraper import Sort, reviews

    lang = lang or LANG.get(country, "en")
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
        out.extend(to_review(i, brand, country, app_id, product) for i in batch)
        if token is None or getattr(token, "token", None) is None:
            break
    out = [r for r in out if r.text]
    if not out:
        raise RuntimeError(f"0 отзывов для {app_id} ({country}/{lang}) — проверьте id и страну")
    return out
