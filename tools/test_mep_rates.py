"""Tests for the MEP rate analyses -- run with: python3 -m unittest tools/test_mep_rates.py

Checks the published #raMepData block against the house rate-data rules. Set
MAK_BILL=/path/to/"MAK Final Bill Checking.xlsx" to also rebuild from the bill and
confirm the published block matches it."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mep_rates as T  # noqa: E402

HTML = T.DEFAULT_HTML
MON = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def block(html):
    return json.loads(T.BLOCK_RE.search(html).group(2))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.d = block(cls.html)
        cls.rates = {r["code"]: r for r in cls.d["rates"]}
        seed = re.search(r"RA_MAT_SEED=(\[.*?\]\]),", cls.html, re.S).group(1)
        cls.seed_codes = set(re.findall(r'\["([A-Z0-9-]+)","[MLP]"', seed))
        units = re.search(r"RA_UNITS=\[(.*?)\]", cls.html).group(1)
        cls.units = set(re.findall(r'"([^"]+)"', units))

    def test_every_reference_resolves(self):
        for it in self.d["items"]:
            for row in it["M"] + it["L"] + it["P"]:
                self.assertTrue(row["ref"] in self.rates or row["ref"] in self.seed_codes, (it["id"], row["ref"]))

    def test_every_item_has_one_mak_line(self):
        for it in self.d["items"]:
            self.assertEqual([r["ref"] for r in it["L"]], ["MAK-" + it["id"]])
            self.assertGreater(self.rates["MAK-" + it["id"]]["rate"], 0, it["id"])

    def test_ids_unique_and_units_known(self):
        ids = [it["id"] for it in self.d["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        for it in self.d["items"]:
            self.assertIn(it["unit"], self.units, it["id"])

    def test_rates_are_dated_or_flagged(self):
        """CLAUDE.md: '<source>, DD-Mon-YYYY — <details>' with the same effective date; else 0 + ASSUMPTION."""
        for r in self.d["rates"]:
            if not r["rate"]:
                self.assertTrue(r["src"].startswith("ASSUMPTION — no dated source"), r["code"])
                continue
            m = re.search(rf", (\d\d)-({MON})-(\d{{4}}) — ", r["src"])
            self.assertIsNotNone(m, r["code"])
            y, mo, dd = r["date"].split("-")
            self.assertEqual((m.group(1), m.group(2), m.group(3)), (dd, T.MON[int(mo) - 1], y), r["code"])

    def test_house_margins_and_wastage(self):
        for it in self.d["items"]:
            self.assertEqual((it["oh"], it["prof"]), (8, 10), it["id"])
            self.assertIn(it["wast"], (0, 3, 5), it["id"])

    def test_sample_build_up(self):
        """13 A socket DB-to-first-point: 80 ft 4 mm² + 40 ft CPC + 40 ft 1" conduit + box + socket."""
        it = next(i for i in self.d["items"] if i["id"] == "ME-307B")
        a = sum(m["qty"] * self.rates[m["ref"]]["rate"] for m in it["M"])
        self.assertAlmostEqual(a, 80 * 61.66 + 40 * 61.66 + 40 * 18.1 + 200 + 865, places=2)
        self.assertEqual(self.rates["MAK-ME-307B"]["rate"], 982.125)

    def test_price_list_lines(self):
        """Pakistan Cables 03-Jun-2026 coil prices less 30% trade discount ÷ 90 metres, flagged I."""
        for code, name, pcl, fast, gix in T.PRICE_LIST:
            r = self.rates[code]
            self.assertEqual(r["rate"], round(pcl * (1 - T.TRADE_DISC) / T.COIL_FT, 2), code)
            self.assertEqual((r["date"], r["vs"]), ("2026-06-03", "I"), code)
            self.assertIn("less 30% trade discount", r["src"], code)
        self.assertEqual(self.rates["MEP-W1C25"]["rate"], 41.29)      # 17,415 × 0.70 ÷ 295.276

    def test_previous_versions_kept_for_saved_libraries(self):
        self.assertIn([29.41, "2024-07-05"], self.d["prevRates"]["MEP-W1C25"])
        self.assertIn([58.98, "2026-06-03"], self.d["prevRates"]["MEP-W1C25"])
        self.assertIn("ME-504E", self.d["prevItems"])

    def test_no_script_breakout(self):
        raw = T.BLOCK_RE.search(self.html).group(2)
        self.assertNotIn("</", raw)


@unittest.skipUnless(os.environ.get("MAK_BILL"), "set MAK_BILL to rebuild from the bill")
class Rebuild(unittest.TestCase):
    def test_rebuild_matches_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "index.html"
            shutil.copy(HTML, html)
            subprocess.run([sys.executable, str(Path(T.__file__)), "--html", str(html), os.environ["MAK_BILL"]], check=True)
            new, old = block(html.read_text(encoding="utf-8")), block(HTML.read_text(encoding="utf-8"))
            self.assertEqual(new["items"], old["items"])
            self.assertEqual(new["rates"], old["rates"])


if __name__ == "__main__":
    unittest.main()
