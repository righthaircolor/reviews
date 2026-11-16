"""Проверка разбора ответов источников на образцах (без сети): python -m unittest"""
import datetime, unittest
from collector.__main__ import merge
from collector.sources import appstore, googleplay, url_extract

FEED = {"feed": {"entry": [
    {"im:name": {"label": "App"}},
    {"id": {"label": "111"}, "updated": {"label": "2026-10-02T10:00:00-07:00"}, "im:rating": {"label": "1"},
     "im:version": {"label": "5.2"}, "title": {"label": "Плохо"}, "content": {"label": "Не открывается  "},
     "author": {"name": {"label": "Иван"}}},
    {"id": {"label": "112"}, "updated": {"label": "2026-10-03T10:00:00-07:00"}, "im:rating": {"label": "5"},
     "title": {"label": "Супер"}, "content": {"label": "Всё отлично"}}]}}
HTML = '''<html><script type="application/ld+json">{"@type":"Product","review":[
{"@type":"Review","reviewBody":"Доставка быстрая","datePublished":"2026-09-01T00:00:00Z","reviewRating":{"ratingValue":"4,5"},"author":{"name":"X"}},
{"@type":"Review","reviewBody":""}]}</script></html>'''
MICRO = '''<div itemprop="review"><meta itemprop="ratingValue" content="2"><time itemprop="datePublished" datetime="2026-08-08">x</time>
<p itemprop="reviewBody">Долго ждал</p></div>'''

class T(unittest.TestCase):
    def test_appstore(self):
        r = appstore.parse_feed(FEED, "B", "by", "1", "")
        self.assertEqual(len(r), 2)
        self.assertEqual((r[0].rating, r[0].date, r[0].text, r[0].id), (1.0, "2026-10-02", "Не открывается", "as-by-111"))
        self.assertNotIn("Иван", str(r[0].to_dict()))
        self.assertEqual(len(appstore.parse_feed({"feed": {"entry": FEED["feed"]["entry"][1]}}, "B", "by", "1", "")), 1)
        self.assertEqual(appstore.parse_feed({"feed": {}}, "B", "by", "1", ""), [])
    def test_gplay(self):
        r = googleplay.to_review({"reviewId": "a", "userName": "U", "content": "ok", "score": 4,
            "at": datetime.datetime(2026, 5, 1), "reviewCreatedVersion": None}, "B", "ru", "com.x", "X")
        self.assertEqual((r.rating, r.date, r.id, r.version), (4.0, "2026-05-01", "gp-ru-a", ""))
    def test_url(self):
        items, how = url_extract.extract(HTML)
        self.assertEqual(len(items), 1); self.assertEqual(items[0]["rating"], 4.5); self.assertEqual(items[0]["date"], "2026-09-01")
        items, how = url_extract.extract(MICRO)
        self.assertEqual((items[0]["text"], items[0]["rating"], items[0]["date"]), ("Долго ждал", 2.0, "2026-08-08"))
        self.assertEqual(url_extract.extract("<p>нет</p>")[0], [])
    def test_merge(self):
        m = merge([{"id": "1", "date": "2026-01-01"}], [{"id": "1", "date": "2026-01-01"}, {"id": "2", "date": "2026-02-01"}])
        self.assertEqual([x["id"] for x in m], ["2", "1"])

if __name__ == "__main__":
    unittest.main()
