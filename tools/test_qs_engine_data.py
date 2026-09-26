"""Tests for the QS Rate Analysis Engine data block (#raQsEngine), written by tools/qs_engine_data.py.

    python3 -m unittest tools/test_qs_engine_data.py

Browser tests of the engine itself: tools/test_qs_engine.js.
"""
import json
import re
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "zameen-developments" / "index.html"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def block(html, bid):
    m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % bid, html, re.S)
    return json.loads(m.group(1)) if m else None


class QsEngineData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.d = block(cls.html, "raQsEngine")

    def test_block_present_and_engine_script_follows(self):
        self.assertIsNotNone(self.d)
        self.assertIn("QS Rate Analysis Engine", self.html)
        self.assertLess(self.html.index('id="raQsEngine"'), self.html.index("/* ===== QS Rate Analysis Engine"))

    def test_nineteen_categories(self):
        self.assertEqual(len(self.d["cats"]), 19)
        self.assertEqual([c["id"] for c in self.d["cats"]], [f"C{i:02d}" for i in range(1, 20)])

    def test_rules_point_at_real_categories_and_compile(self):
        ids = {c["id"] for c in self.d["cats"]}
        for r in self.d["rules"]:
            self.assertIn(r["c"], ids)
            for k in ("code", "cat", "sub", "desc"):
                if k in r:
                    re.compile(r[k])
        self.assertFalse(any(k in self.d["rules"][-1] for k in ("code", "cat", "sub", "desc")), "last rule must be a catch-all")

    def test_every_rate_follows_the_source_rule(self):
        """CLAUDE.md: '<source>, DD-Mon-YYYY — <details>' with the same date as the effective date,
        or 0 / ASSUMPTION when there is no dated source."""
        for r in self.d["rates"]:
            with self.subTest(code=r["code"]):
                if not r["rate"] or not r["date"]:
                    self.assertIn("ASSUMPTION", r["src"])
                    self.assertEqual(r["vs"], "A")
                    continue
                y, m, dd = r["date"].split("-")
                self.assertIn(f"{dd}-{MON[int(m) - 1]}-{y}", r["src"], "effective date must appear in the remarks")
                self.assertIn(r["vs"], ("V", "I", "A"))

    def test_grn_lines_match_the_grn_register(self):
        g = block(self.html, "raGrnData")
        latest = {}
        for ix, date, rate, qty, grn, vi in g["rc"]:
            if ix not in latest or (date, grn) > (latest[ix][0], latest[ix][2]):
                latest[ix] = (date, rate, grn)
        by_desc = {}
        for ix, it in enumerate(g["items"]):
            by_desc.setdefault(it[2], []).append((ix, it))
        for r in self.d["rates"]:
            if not r["code"].startswith("GRN-"):
                continue
            with self.subTest(code=r["code"]):
                hits = by_desc.get(r["name"], [])
                self.assertTrue(hits)
                ix, it = next((ix, it) for ix, it in hits if g["sites"][it[0]][:3].upper() in r["code"])
                self.assertEqual(r["date"], latest[ix][0])
                self.assertAlmostEqual(r["rate"], round(latest[ix][1] * it[7], 2), places=2)

    def test_gypsum_board_is_not_invented(self):
        bd = next(r for r in self.d["rates"] if r["code"] == "QE-GYP-BD12")
        self.assertEqual(bd["rate"], 0)
        self.assertEqual(bd["unit"], "Sheet")

    def test_builder_parameters_reference_known_lines(self):
        codes = {r["code"] for r in self.d["rates"]} | {"TILE-POR", "TILE-CER", "TILEADH", "GROUT", "CABLE-LT",
                                                         "SAND-CH", "PROPS", "MOULD", "NAILS"}
        for it in self.d["conv"] + self.d["items"]:
            for k, v in it["gen"]["p"].items():
                if isinstance(v, str) and re.match(r"^(GRN-|QE-)", v):
                    self.assertIn(v, codes, f"{it['id']}.{k}")
            for c in it["gen"]["p"].get("coats", []):
                self.assertIn(c["ref"], codes)

    def test_screed_correction_arithmetic(self):
        """SC-420 seed: cement 0.0217 'bag' and sand 0.1083 cft per Sft for 1" 1:4 — both 25 % high."""
        dry = 1 / 12 * 1.30
        self.assertAlmostEqual(dry, 0.1083, 4)
        self.assertAlmostEqual(dry / 5, 0.0217, 4)          # the seed's cement figure is the cement VOLUME
        self.assertAlmostEqual(dry / 5 / 1.25, 0.01733, 5)   # in bags
        self.assertAlmostEqual(dry * 4 / 5, 0.08667, 5)      # sand share, not the whole dry volume

    def test_gypsum_demo(self):
        """Prompt example: 8 × 4 ft board at 500 / sheet with 5 % wastage."""
        self.assertAlmostEqual(500 / 32, 15.625)
        self.assertAlmostEqual(500 / 32 * 1.05, 16.40625)

    def test_conversion_guards_match_the_seed(self):
        conv = {c["id"]: c for c in self.d["conv"]}
        self.assertEqual(conv["FN-550"]["guard"], [["GYPBD", 1]])
        self.assertEqual(conv["SC-420"]["guard"], [["CEM", 0.0217], ["SAND-CH", 0.1083], ["WATER", 0.008]])


if __name__ == "__main__":
    unittest.main()
