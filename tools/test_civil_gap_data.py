"""Tests for the civil gap-analysis data block (#raCivilData), written by tools/civil_gap_data.py.

    python3 -m unittest tools/test_civil_gap_data.py

Browser checks (merge into a fresh and a saved library): tools/test_civil_gap.js.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import civil_gap_data as cg  # noqa: E402

HTML = Path(__file__).resolve().parent.parent / "zameen-developments" / "index.html"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
UNITS = {"Cft", "Sft", "Rft", "Nos", "Kg", "Day", "Job"}
METRIC = re.compile(r"\b\d+(\.\d+)?\s?(mm|cm|m|sqm|cum|m²|m³)\b|\bmetre|\bmeter", re.I)


def block(html, bid):
    m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % bid, html, re.S)
    return json.loads(m.group(1)) if m else None


class CivilGapData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.d = block(cls.html, "raCivilData")
        cls.rates = {r["code"]: r for r in cls.d["rates"]}

    def test_block_present_and_loader_wired(self):
        self.assertIsNotNone(self.d)
        self.assertIn('raSyncBlk(e,raBlk("raCivilData"),"civRev")', self.html)
        self.assertIn('function raSyncMep(e){raSyncBlk(e,raMepData(),"mepRev")}', self.html)

    def test_block_is_current(self):
        """The committed block is what the generator writes for its own date."""
        want = cg.make(self.html, __import__("datetime").date.fromisoformat(self.d["rev"][:10]))
        self.assertEqual(want["rev"], self.d["rev"], "re-run tools/civil_gap_data.py --as-of " + self.d["rev"][:10])

    def test_all_items_of_the_list(self):
        ids = [i["id"] for i in self.d["items"]]
        self.assertEqual(ids[:130], [f"CV-{n:03d}" for n in range(1, 131)])
        self.assertEqual(ids[130:], ["CV-R01", "CV-R02", "CV-R03"])
        self.assertEqual(sorted(u["id"] for u in self.d["upd"]), ["EW-950", "EW-960", "FN-560"])

    def test_every_rate_follows_the_source_rule(self):
        """CLAUDE.md: '<source>, DD-Mon-YYYY — <details>' with the same date as the effective date,
        or 0 / ASSUMPTION when there is no dated source."""
        for r in self.d["rates"]:
            with self.subTest(code=r["code"]):
                if r["vs"] == "A":
                    self.assertTrue(r["src"].startswith(cg.NOSRC), "assumptions say so first")
                    self.assertEqual(r["date"], "")
                    continue
                self.assertTrue(r["rate"] > 0)
                y, m, dd = r["date"].split("-")
                self.assertIn(f"{dd}-{MON[int(m) - 1]}-{y} —", r["src"], "effective date must appear in the remarks")
                self.assertIn(r["vs"], ("V", "I"))

    def test_mrs_lines_match_the_register(self):
        mrs = block(self.html, "raMrsData")
        by = {f"MRS-C{a[0]}-{a[1]}-{a[2]}": a for a in mrs["items"]}
        for code, r in self.rates.items():
            if not code.startswith("MRS-"):
                continue
            with self.subTest(code=code):
                lab = code.endswith("-L") or r["kind"] == "L"
                a = by[code[:-2] if code.endswith("-L") else code]
                v = a[9] if lab else a[10]
                self.assertAlmostEqual(r["rate"], round(v * a[8], 4), places=4)
                self.assertEqual(r["date"], mrs["from"])

    def test_rows_reference_known_lines_and_units_are_feet(self):
        for it in self.d["items"]:
            with self.subTest(item=it["id"]):
                self.assertIn(it["unit"], UNITS)
                self.assertTrue(it["desc"].endswith("complete in all respects"))
                self.assertFalse(METRIC.search(it["desc"] + " " + it["spec"]), "no metric units in the item text")
                rows = it["M"] + it["L"] + it["P"]
                self.assertTrue(rows)
                for r in rows:
                    self.assertTrue(r["ref"] in self.rates or r["ref"] in cg.LIB, r["ref"])
                    self.assertGreater(r["qty"], 0)

    def test_library_lines_used_exist_in_the_page(self):
        for code in cg.LIB:
            with self.subTest(code=code):
                self.assertTrue(re.search(r'\["%s",' % re.escape(code), self.html) or f'"{code}"' in self.html)

    def test_assumptions_are_only_where_no_source_was_found(self):
        a = [r for r in self.d["rates"] if r["vs"] == "A"]
        self.assertTrue(all(r["code"].startswith("BM-CV-") or r["code"] == "TOPSOIL" for r in a))
        self.assertEqual(self.rates["TOPSOIL"]["rate"], 0)

    def test_published_versions_guard_updates(self):
        self.assertEqual(self.d["prevRates"]["L-HELPER"], [[1300, "2026-09-23"]])
        self.assertEqual(self.rates["L-HELPER"]["rate"], 1538)
        self.assertEqual(self.d["prevItems"]["FN-560"], [[["DOOR-W", 1], ["DOOR-HW", 0.055]]])

    def test_worked_examples(self):
        bricks, mortar = cg.brick_cft()
        self.assertAlmostEqual(bricks, 12.101, places=3)       # 1 ÷ (9.25 × 4.75 × 3.25 ÷ 1728)
        self.assertAlmostEqual(mortar, 0.14914, places=4)       # wet mortar per cft of brickwork
        cv34 = next(i for i in self.d["items"] if i["id"] == "CV-034")
        cem = next(r for r in cv34["M"] if r["ref"] == "CEM")["qty"]
        self.assertAlmostEqual(cem, 0.14914 * 1.3 / 7 / 1.25, places=4)
        dpc = next(i for i in self.d["items"] if i["id"] == "CV-047")
        bit = next(r for r in dpc["M"] if r["ref"] == "BITUMEN")["qty"]
        self.assertAlmostEqual(bit, 34 / 100 * 0.4536, places=5)  # 34 lb per 100 Sft


if __name__ == "__main__":
    unittest.main()
