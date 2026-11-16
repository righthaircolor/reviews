import json, sys
sys.path.insert(0, '.')
from collector.sources import twogis, yandex_maps
out = []
for tag, fn in [("2gis", lambda: twogis.collect("T", "https://2gis.ru/firm/4504127908538375", "ru", 120)),
                ("yandex_maps", lambda: yandex_maps.collect("T", "https://yandex.ru/maps/org/yandeks/1124715036/reviews/", "ru"))]:
    try:
        r = fn(); ds = sorted(x.date for x in r)
        out.append({"tag": tag, "n": len(r), "ids": len({x.id for x in r}), "dates": [ds[0], ds[-1]], "rated": sum(x.rating is not None for x in r), "sample": r[0].to_dict()})
    except Exception as e:
        out.append({"tag": tag, "error": repr(e)[:400]})
json.dump(out, open("probe/result.json", "w"), ensure_ascii=False, indent=1)
