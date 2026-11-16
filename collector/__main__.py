"""Запуск сбора: python -m collector

Читает brands.yml, собирает отзывы из всех источников, дополняет базу
docs/data/reviews.json (без дублей) и пишет отчёт о запуске в docs/data/meta.json.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .sources import (appstore, googleplay, onliner, rustore, trustpilot, twogis,
                      url_extract, wildberries, yandex_maps)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "brands.yml"
DATA = ROOT / "docs" / "data"
# эти площадки не отвечают серверам GitHub — собираются только при запуске с компьютера
LOCAL = not os.environ.get("GITHUB_ACTIONS")


def _list(v) -> list:
    return [] if v in (None, False, True, "") else v if isinstance(v, list) else [v]


def _place(item, default_market):
    """Запись вида id / ссылка / {id: ..., market: ...} → (значение, рынок)."""
    if isinstance(item, dict):
        return item.get("id") or item.get("url"), str(item.get("market") or default_market).lower()
    return item, default_market


def jobs(b: dict, limits: dict):
    """Список задач сбора для бренда: (источник, рынок, функция, автоматически ли подключён)."""
    name = b["name"]
    search = b.get("search") or name
    markets = [str(m).lower() for m in b.get("markets") or []]
    first = markets[0] if markets else "global"
    stores = b.get("stores", True)

    if stores and b.get("app_store", True) is not False:
        aid = str(b["app_store_id"]) if b.get("app_store_id") else None
        for m in markets:
            yield "app_store", m, (lambda m=m: appstore.collect(search, m, aid, limits.get("app_store", 500))), False

    if stores and b.get("google_play", True) is not False:
        # Google Play делит отзывы по языку, а не по стране — один сбор на язык
        langs = {}
        for m in markets:
            langs.setdefault(googleplay.LANG.get(m, "en"), m)
        for lg in _list(b.get("google_play_langs")):
            langs.setdefault(str(lg).lower(), first if markets else "us")
        for lang, country in langs.items():
            yield "google_play", f"lang-{lang}", (lambda lang=lang, country=country: googleplay.collect(
                search, lang, b.get("google_play_id"), limits.get("google_play", 1000), country)), False

    # RuStore: сам подключается для рынка ru, если известен пакет приложения
    rs = b.get("rustore", "ru" in markets and stores)
    package = rs if isinstance(rs, str) else b.get("google_play_id")
    if rs and package:
        yield "rustore", "ru", (lambda: rustore.collect(name, package, limits.get("rustore", 1000))), not isinstance(rs, str)

    # Onliner: сам подключается для рынка by (поиск товаров по названию бренда)
    on = b.get("onliner", "by" in markets)
    if on:
        q = on if isinstance(on, str) else search
        yield "onliner", "by", (lambda: onliner.collect(name, q, limits.get("onliner", 1000))), not isinstance(on, str)

    if LOCAL:
        # Wildberries: сам подключается для рынков ru и by (поиск товаров бренда)
        wb = b.get("wildberries", bool({"ru", "by"} & set(markets)))
        if wb:
            q = wb if isinstance(wb, str) else search
            m = "ru" if "ru" in markets or not markets else first
            yield "wildberries", m, (lambda: wildberries.collect(
                name, q, m, limits.get("wildberries", 2000))), not isinstance(wb, str)
        for d in _list(b.get("trustpilot")):
            yield "trustpilot", "global", (lambda d=d: trustpilot.collect(
                name, d, limits.get("trustpilot", 1000))), False

    for item in _list(b.get("2gis")):
        v, m = _place(item, first if first != "global" else "ru")
        yield "2gis", m, (lambda v=v, m=m: twogis.collect(name, v, m, limits.get("2gis", 500))), False

    for item in _list(b.get("yandex_maps")):
        v, m = _place(item, first if first != "global" else "ru")
        yield "yandex_maps", m, (lambda v=v, m=m: yandex_maps.collect(name, v, m)), False

    for item in _list(b.get("urls")):
        v, m = _place(item, "global")
        yield v, m, (lambda v=v, m=m: url_extract.collect(name, v, m)), False


def run(config: dict) -> tuple[list[dict], list[dict]]:
    limits = config.get("limits") or {}
    reviews, log = [], []
    for b in config.get("brands") or []:
        for source, market, fn, auto in jobs(b, limits):
            entry = {"brand": b["name"], "source": source, "market": market}
            try:
                got = fn()
                for r in got:
                    r.brand = b["name"]
                reviews.extend(r.to_dict() for r in got)
                entry.update(ok=True, count=len(got))
            except LookupError as e:
                # источник подключился сам, но бренда там нет — это не ошибка
                entry.update(ok=auto, count=0, **({"note": str(e)[:300]} if auto else {"error": str(e)[:300]}))
            except Exception as e:  # один сбой не должен ронять весь сбор
                entry.update(ok=False, count=0, error=str(e)[:300])
            print(entry, flush=True)
            log.append(entry)
    return reviews, log


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
