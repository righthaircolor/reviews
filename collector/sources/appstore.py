"""App Store: открытая RSS-лента отзывов Apple (до ~500 последних на страну)."""
from __future__ import annotations

import time

import requests

from ..models import Review

UA = {"User-Agent": "Mozilla/5.0 (reviews-collector)"}
MAX_PAGES = 10  # ограничение самой ленты Apple


def find_app(name: str, country: str) -> tuple[str, str] | None:
    """Ищет приложение по названию в сторе страны. Возвращает (id, название)."""
    r = requests.get(
        "https://itunes.apple.com/search",
        params={"term": name, "country": country, "entity": "software", "limit": 1},
        headers=UA,
        timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    return str(results[0]["trackId"]), results[0].get("trackName", "")


def parse_feed(data: dict, brand: str, country: str, app_id: str, product: str) -> list[Review]:
    entries = (data.get("feed") or {}).get("entry") or []
    if isinstance(entries, dict):
        entries = [entries]
    out = []
    for e in entries:
        if "im:rating" not in e:  # запись о самом приложении, не отзыв
            continue
        rid = (e.get("id") or {}).get("label", "")
        out.append(
            Review(
                brand=brand,
                source="app_store",
                market=country,
                date=((e.get("updated") or {}).get("label") or "")[:10],
                rating=float(e["im:rating"]["label"]),
                title=(e.get("title") or {}).get("label", ""),
                text=(e.get("content") or {}).get("label", ""),
                version=(e.get("im:version") or {}).get("label", ""),
                url=f"https://apps.apple.com/{country}/app/id{app_id}?see-all=reviews",
                product=product,
                id=f"as-{country}-{rid}" if rid else "",
            ).finalize()
        )
    return out


def collect(brand: str, country: str, app_id: str | None, limit: int = 500) -> list[Review]:
    product = ""
    if not app_id:
        found = find_app(brand, country)
        if not found:
            raise RuntimeError(f"приложение «{brand}» не найдено в App Store ({country})")
        app_id, product = found
    out: list[Review] = []
    for page in range(1, MAX_PAGES + 1):
        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby=mostrecent/json"
        )
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200:
            break
        batch = parse_feed(r.json(), brand, country, str(app_id), product)
        if not batch:
            break
        out.extend(batch)
        if len(out) >= limit:
            break
        time.sleep(0.5)
    if not out:
        raise RuntimeError(f"0 отзывов для id {app_id} ({country}) — проверьте id и страну")
    return out[:limit]
