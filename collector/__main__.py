"""Запуск сбора: python -m collector

Читает brands.yml, собирает отзывы из всех источников, дополняет базу
docs/data/reviews.json (без дублей) и пишет отчёт о запуске в docs/data/meta.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .sources import appstore, googleplay, url_extract

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "brands.yml"
DATA = ROOT / "docs" / "data"


def run(config: dict) -> tuple[list[dict], list[dict]]:
    limits = config.get("limits") or {}
    reviews, log = [], []

    def attempt(brand, source, market, fn):
        entry = {"brand": brand, "source": source, "market": market}
        try:
            got = fn()
            reviews.extend(r.to_dict() for r in got)
            entry.update(ok=True, count=len(got))
        except Exception as e:  # один сбой не должен ронять весь сбор
            entry.update(ok=False, count=0, error=str(e)[:300])
        print(entry, flush=True)
        log.append(entry)

    for b in config.get("brands") or []:
        name = b["name"]
        stores = b.get("stores", True)
        markets = [str(m).lower() for m in b.get("markets") or []]
        if stores and b.get("app_store", True) is not False:
            for market in markets:
                attempt(name, "app_store", market, lambda: _as(b, name, market, limits))
        if stores and b.get("google_play", True) is not False:
            # Google Play делит отзывы по языку, а не по стране — один сбор на язык
            langs = {}
            for m in markets:
                langs.setdefault(googleplay.LANG.get(m, "en"), m)
            for lg in b.get("google_play_langs") or []:
                langs.setdefault(str(lg).lower(), markets[0] if markets else "us")
            for lang, country in langs.items():
                attempt(name, "google_play", f"lang-{lang}",
                        lambda: _gp(b, name, lang, country, limits))
        for u in b.get("urls") or []:
            url, market = (u, "global") if isinstance(u, str) else (u["url"], u.get("market", "global"))
            attempt(name, url, market, lambda: url_extract.collect(name, url, market))
    return reviews, log


def _as(b, name, market, limits):
    got = appstore.collect(b.get("search") or name, market,
                           str(b["app_store_id"]) if b.get("app_store_id") else None,
                           limits.get("app_store", 500))
    for r in got:
        r.brand = name
    return got


def _gp(b, name, lang, country, limits):
    got = googleplay.collect(b.get("search") or name, lang, b.get("google_play_id"),
                             limits.get("google_play", 1000), country)
    for r in got:
        r.brand = name
    return got


def merge(old: list[dict], new: list[dict]) -> list[dict]:
    by_id = {r["id"]: r for r in old}
    by_id.update({r["id"]: r for r in new})
    return sorted(by_id.values(), key=lambda r: (r.get("date") or "", r["id"]), reverse=True)


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "reviews.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    new, log = run(config)
    merged = merge(old, new)
    path.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(merged), "added": len(merged) - len(old), "log": log,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Всего в базе: {len(merged)} (новых: {len(merged) - len(old)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
