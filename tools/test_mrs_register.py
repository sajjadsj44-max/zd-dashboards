"""Tests for tools/mrs_register.py -- run with: python3 -m unittest tools/test_mrs_register.py

Set MRS_PDF=/path/to/MRS.pdf to also run the end-to-end check against a real schedule."""
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
import mrs_register as T  # noqa: E402


def w(text, x0, x1=None, top=100.0):
    return {"text": text, "x0": x0, "x1": x1 if x1 is not None else x0 + 6 * len(text), "top": top}


def row(desc="", sr="", unit="", lab=None, comp=None, unit2="", lab2=None, comp2=None, page=1):
    return {"page": page, "sr": sr, "desc": desc, "unit": unit, "lab": lab, "comp": comp,
            "unit2": unit2, "lab2": lab2, "comp2": comp2}


class Units(unittest.TestCase):
    def check(self, raw, unit, k):
        u, f = T.norm_unit(raw)
        self.assertEqual(u, unit, raw)
        self.assertAlmostEqual(f, k, places=9, msg=raw)

    def test_quantity_units(self):
        self.check("Per Cft", "Cft", 1)
        self.check("100 Sft.", "Sft", 0.01)
        self.check("100Cft.", "Cft", 0.01)
        self.check("1000 Cft.", "Cft", 0.001)
        self.check("% Sft", "Sft", 0.01)
        self.check("P.Rft", "Rft", 1)
        self.check("100Lft.", "Rft", 0.01)
        self.check("Per foot", "Rft", 1)
        self.check("Each", "Nos", 1)
        self.check("Each No.", "Nos", 1)
        self.check("1000 Nos.", "Nos", 0.001)
        self.check("Per Tonne", "Ton", 1)

    def test_weight_conversions(self):
        self.check("Per Cwt.", "Kg", 1 / 50.80234544)
        self.check("100 Mds.", "Kg", 1 / (100 * 37.3242))
        self.check("100Kg", "Kg", 0.01)

    def test_qualified_and_other_units(self):
        self.check("100 Sft. Per Inch thickness", "Sft per inch thickness", 0.01)
        self.check("Per Rft per inch width", "Rft per inch width", 1)
        self.check("Each Cut", "Cut", 1)
        self.check("Each per inch bore", "Nos per inch bore", 1)
        self.check("P.KM", "Km", 1)
        self.check("Per Job", "Job", 1)
        self.assertEqual(T.norm_unit(""), (None, None))


class Numbers(unittest.TestCase):
    def test_clean_num(self):
        self.assertIsNone(T.clean_num("--"))
        self.assertIsNone(T.clean_num("-"))
        self.assertEqual(T.clean_num("6,090.50"), 6090.5)
        self.assertEqual(T.clean_num("1 02,068.75"), 102068.75)
        self.assertIsNone(T.clean_num("Chap-6"))

    def test_split_figures_are_rejoined(self):
        # "6" ".25" straddling a column boundary (Ch.6 item 9(e), p.39)
        got = T.join_fragments([w("6", 399.7, 404.1), w(".25", 403.7, 414.1), w("Per", 421.9, 432.5)])
        self.assertEqual([x["text"] for x in got], ["6.25", "Per"])
        got = T.join_fragments([w("1", 486.4, 490.9), w("5.30", 490.5, 505.2), w("2", 538.1, 542.6), w("6.85", 542.2, 556.9)])
        self.assertEqual([x["text"] for x in got], ["15.30", "26.85"])
        got = T.join_fragments([w("6", 334, 338.5), w(",090.50", 339, 364)])
        self.assertEqual(got[0]["text"], "6,090.50")
        # genuinely separate words keep their space
        got = T.join_fragments([w("3", 100, 104), w("cm", 106, 115), w("12", 130, 140), w("34", 145, 155)])
        self.assertEqual([x["text"] for x in got], ["3", "cm", "12", "34"])


class Markers(unittest.TestCase):
    def style(self, text, stack=()):
        m = T.marker(text, list(stack))
        return m and m[0]

    def test_styles(self):
        self.assertEqual(self.style("(i) 7000 PSI"), ("()", "roman", False))
        self.assertEqual(self.style("i) Ordinary"), (")", "roman", False))
        self.assertEqual(self.style("( c) Substructure"), ("()", "alpha", False))
        self.assertEqual(T.marker("( c) Substructure", [])[1], "(c) Substructure")
        self.assertEqual(self.style("a) Deodar wood Door"), (")", "alpha", False))
        self.assertEqual(self.style("A) By Manual"), (")", "alpha", True))
        self.assertEqual(self.style("II) Deodar Wood"), (")", "roman", True))
        self.assertEqual(self.style("1) Upto 5' depth"), (")", "num", False))
        self.assertEqual(self.style("i. PORTA HD 173N Toilet"), (".", "roman", False))
        self.assertEqual(self.style("A Two Piece"), ("sp", "alpha", True))

    def test_glued_number(self):
        m = T.marker("10Providing/fixing U-shape grab bar", [])
        self.assertEqual(m, ((")", "num", False), "10) Providing/fixing U-shape grab bar"))

    def test_not_markers(self):
        for text in ("mm) depth, with back", "i/c the cost of", "1st class teak", "cm2)", "P.C.C. flooring"):
            self.assertIsNone(T.marker(text, []), text)

    def test_letter_i_after_h(self):
        stack = [[(")", "alpha", False), "h) Something"]]
        self.assertEqual(self.style("i) Next letter", stack), (")", "alpha", False))

    def test_headings(self):
        self.assertTrue(T.is_heading("Replacement items"))
        self.assertTrue(T.is_heading("Brick Work"))
        self.assertFalse(T.is_heading("Engineer Incharge."))
        self.assertFalse(T.is_heading('M.S. flat 2"x¼" (50 mm x 6 mm)'))
        self.assertFalse(T.is_heading("girders and other structural members laid in situ"))


class Grouping(unittest.TestCase):
    def test_nested_sub_headings(self):
        rows = [
            row("Placing concrete ... Engineer Incharge.", sr="9"),
            row("(a) Reinforced cement concrete in roof slab,"),
            row("complete in all respects:-"),
            row("(i) 7000 PSI", unit="Per Cft", lab=172.35, comp=905.05),
            row("(ii) 6000 PSI", unit="Per Cft", lab=172.35, comp=870.35),
            row("(b) Retaining/ Shear walls"),
            row("i) 7000 PSI"),
            row('(i) Upto 9" thick', unit="Per Cft", lab=125.40, comp=822.00),
            row('(ii) More Than 9" Thick', unit="Per Cft", lab=112.00, comp=791.20),
            row("ii) 6000 PSI"),
            row('(i) Upto 9" thick', unit="Per Cft", lab=125.40, comp=787.30),
            row("(e) Extra for placing with boom pump", unit="Per Cft", comp=6.25),
            row("by the Engineer Incharge."),
        ]
        items = T.build_items(rows, 6)
        self.assertEqual([i["path"] for i in items], [
            "(a) Reinforced cement concrete in roof slab, complete in all respects:- (i) 7000 PSI",
            "(a) Reinforced cement concrete in roof slab, complete in all respects:- (ii) 6000 PSI",
            '(b) Retaining/ Shear walls i) 7000 PSI (i) Upto 9" thick',
            '(b) Retaining/ Shear walls i) 7000 PSI (ii) More Than 9" Thick',
            '(b) Retaining/ Shear walls ii) 6000 PSI (i) Upto 9" thick',
            "(e) Extra for placing with boom pump by the Engineer Incharge.",
        ])
        self.assertTrue(all(i["head"] == "Placing concrete ... Engineer Incharge." for i in items))
        self.assertEqual([(i["key"], i["n"]) for i in items][:2], [("9", 1), ("9", 2)])

    def test_single_line_item_with_wrap(self):
        items = T.build_items([
            row("Precast cement concrete solid blocks (1:2:4),", sr="13", unit="Per Cft", lab=226.6, comp=564.15),
            row("including cost of templates."),
            row("Next item", sr="14", unit="Per Cft", lab=1.0, comp=2.0),
        ], 6)
        self.assertEqual(items[0]["path"], "Precast cement concrete solid blocks (1:2:4), including cost of templates.")
        self.assertEqual(items[0]["head"], "")

    def test_heading_opens_new_section(self):
        items = T.build_items([
            row("Supply of water heaters:-", sr="57", page=118),
            row("(i) 06 Litre/min", unit="Each", lab=1094.55, comp=23032.05, page=118),
            row("Replacement items", page=118),
            row("1Providing and fixing waste coupling:-", page=118),
            row('i) 3 cm (1¼")', unit="Each", lab=132.0, comp=492.0, page=118),
        ], 19)
        self.assertEqual(items[1]["head"], "Replacement items")
        self.assertEqual(items[1]["path"], '1) Providing and fixing waste coupling:- i) 3 cm (1¼")')
        self.assertEqual((items[1]["key"], items[1]["n"]), ("P118", 1))

    def test_wrapped_units_and_ditto(self):
        items = T.build_items([
            row("Laying wooden paving:-", sr="32"),
            row("and asphalt:-", unit="100 Sft."),
            row("", unit="Per Inch"),
            row("(a) Shisham wood", unit="thickness", lab=7580.3, comp=88468.0),
            row("(b) Kikar wood", unit="ditto", lab=7580.3, comp=51429.4),
            row("Dismantling iron latrine.", sr="39", unit="Per Unit/", lab=3086.15),
            row("", unit="2 Seats"),
        ], 10)
        self.assertEqual([(i["unit"], i["k"]) for i in items[:2]], [("Sft per inch thickness", 0.01)] * 2)
        self.assertEqual(items[2]["mrs_unit"], "Per Unit/ 2 Seats")

    def test_footnotes_are_not_rates(self):
        items = T.build_items([
            row("Compaction of natural ground", sr="54", unit="1000 Sft.", lab=1000.0),
            row('** Specification number correspond to Book of "Building', unit="Specification Vol. II,", lab=1966.0),
        ], 3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["unit"], "Sft")


class CrossCheck(unittest.TestCase):
    def one(self, **kw):
        return T.build_items([row("Item", sr="1", **kw)], 1)[0]

    def test_confirmed(self):
        it = self.one(unit="Per Cft", lab=93.70, comp=661.20, unit2="Per Cum", lab2=3309.0, comp2=23350.05)
        self.assertEqual(it["xc"], 1)

    def test_disagreement_is_flagged(self):
        it = self.one(unit="1000 Cft.", lab=4515.15, comp=7676.95, unit2="Per Cum", lab2=159.5, comp2=235.9)
        self.assertEqual(it["xc"], -1)
        self.assertIn("composite 235.90 per Cum = 6.68 per Cft", it["xnote"])

    def test_long_ton_beside_tonne(self):
        it = self.one(unit="P.Ton", lab=360.9, unit2="P.Tonne", lab2=355.2)
        self.assertAlmostEqual(it["k"], 1000 / 1016.0469088)
        self.assertEqual(it["xc"], 1)
        it = self.one(unit="Per Ton", lab=161.55, comp=1705.0, unit2="Per Ton", lab2=161.55, comp2=1705.0)
        self.assertEqual((it["k"], it["xc"]), (1, 1))

    def test_imperial_and_us_gallons(self):
        self.assertEqual(self.one(unit="Per Gallon", lab=21.25, comp=839.5, unit2="Per Ltr.", lab2=4.65, comp2=184.65)["xc"], 1)
        self.assertEqual(self.one(unit="Per Gallon", lab=9.35, comp=123.0, unit2="Per Ltr.", lab2=2.45, comp2=32.5)["xc"], 1)

    def test_not_comparable(self):
        self.assertEqual(self.one(unit="Per Job", lab=440.0, comp=830.5, unit2="Job", lab2=440.0, comp2=830.5)["xc"], 0)


class Document(unittest.TestCase):
    def test_title_line(self):
        m = T.TITLE_RE.search("MARKET RATES SYSTEM (MRS), 1st BI-ANNUAL-2026 (01.01.2026 to 30.06.2026) DISTRICT RAWALPINDI")
        self.assertEqual(m.groups(), ("1st", "2026", "01", "01", "2026", "30", "06", "2026", "RAWALPINDI"))

    def test_contents_and_chapters(self):
        class P:
            def extract_text(self):
                return "Ch.No. Chapter\n1 Carriage 3 to 19\n2 Loading, Unloading & Stacking 20 to 21\n" \
                       "3 Earthwork (Excavation & Embankment) 22 to 28\n5 Mortar. 33 to 34\n6 Concrete 35 to 44\n"

        class D:
            pages = [P()]
        self.assertEqual(T.contents(D())[3], (5, "Mortar", 33, 34))
        self.assertEqual(T.parse_chapters("2-4,19"), {2, 3, 4, 19})


@unittest.skipUnless(os.environ.get("MRS_PDF"), "set MRS_PDF to run against a real schedule")
class EndToEnd(unittest.TestCase):
    def test_load_into_a_copy_of_the_dashboard(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            html = tmp / "index.html"
            shutil.copy(T.DEFAULT_HTML, html)
            cmd = [sys.executable, str(Path(T.__file__)), os.environ["MRS_PDF"], "--html", str(html)]
            out1 = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
            first = html.read_text(encoding="utf-8")
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.assertEqual(first, html.read_text(encoding="utf-8"), "re-running must not change the page")
            data = json.loads(T.BLOCK_RE.search(first).group(2))
            self.assertGreater(len(data["items"]), 1000)
            self.assertIn("metric cross-check", out1)
            self.assertFalse([ln for ln in out1.splitlines() if ln.startswith("  check:")], "column collisions reported")
            self.assertTrue(all(len(i) == 13 for i in data["items"]))
            self.assertFalse([i for i in data["items"] if re.search(r"chap-?\d", i[5] + i[6], re.I)])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
