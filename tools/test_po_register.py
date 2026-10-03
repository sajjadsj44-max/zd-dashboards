"""Tests for tools/po_register.py -- run with: python3 -m unittest tools/test_po_register.py

Set POPODET1_PDF=/path/to/POPODET1.pdf to also parse a real Sage PO list."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grn_register as GR  # noqa: E402
import po_register as T  # noqa: E402


def chars(text, x0, top=100.0, w=4.4):
    """One char dict per character, laid side by side from x0."""
    out = []
    for ch in text:
        out.append({"text": ch, "x0": x0, "x1": x0 + w, "top": top})
        x0 += w
    return out


def rc(grn, date, code, rate, qty, vendor="Azmat Sons", desc=None, site="Phoenix", uom="Each", main="Grey", sub="Concrete Blocks"):
    return {"site": site, "grn": grn, "date": date, "vendor": vendor, "code": code, "desc": desc or code,
            "uom": uom, "qty": qty, "rate": rate, "main": main, "sub": sub}


def po(no, date, last, n, vendor, lines, status="Completed"):
    return {"po": no, "vcode": "ZOPL0001", "vendor": vendor, "posted": date, "date": date, "arrival": None,
            "status": status, "last": last, "n": n,
            "lines": [{"code": c, "desc": d, "loc": "PHO", "unit": u, "ordered": q, "received": q,
                       "outstanding": 0, "rate": r} for c, d, u, q, r in lines]}


class Columns(unittest.TestCase):
    def test_date_overprinted_by_vendor_name(self):
        # "(PRIVATE) LIMITED" runs over the Posted On date: read the digits chained from the column edge
        date = chars("2/23/2024", 318.5)
        name = [{"text": c, "x0": x, "x1": x + 4.4, "top": 100.0} for c, x in zip("E) LIMITED", (319.5, 324.8, 327.4, 329.6, 333.9, 336.1, 342.5, 344.7, 349.5, 354.8))]
        got, used = T.date_at(date + name, T.DATE_X["posted"])
        self.assertEqual(got, "2024-02-23")
        self.assertEqual(len(used), 9)

    def test_missing_column_is_none(self):
        self.assertEqual(T.date_at(chars("1/2/2024", 367.2), T.DATE_X["arrival"])[0], None)

    def test_completed_flag_taken_out_of_description(self):
        line = chars("INV-STR-1 power ba", 190.0, w=4.4)
        x = line[-1]["x1"]
        line += [{"text": c, "x0": x0, "x1": x0 + 4.4, "top": 100.0} for c, x0 in (("c", 273.3), ("k", 277.4), ("u", 281.5), ("p", 285.8))]
        line += [{"text": c, "x0": x0, "x1": x1, "top": 100.0} for c, x0, x1 in (("Y", 271.0, 276.2), ("e", 276.2, 280.6), ("s", 280.6, 284.5))]
        row = {"top": 100.0, "chars": line}
        self.assertTrue(x < 271)
        self.assertEqual(T.item_text(row), "INV-STR-1 power backup")


class Vendors(unittest.TestCase):
    def test_same_vendor(self):
        self.assertTrue(T.same_vendor("IMPORIENT CHEMICALS PVT LTD", "Imporient Chemicals"))
        self.assertTrue(T.same_vendor("M/S Hamza Steel", "Hamza Steel"))
        self.assertTrue(T.same_vendor("S.J Re-Rolling Steel Mills (Private) Limited", "S.J Re-Rolling Steel Mills"))
        self.assertFalse(T.same_vendor("Azmat Sons", "Askari Guards Pvt Ltd"))
        self.assertFalse(T.same_vendor("", "Azmat Sons"))


class Merge(unittest.TestCase):
    def setUp(self):
        self.receipts = [
            rc("RCP-300", "2026-08-02", "INV-STR-100033", 210, 1000, desc='Concrete Hollow Block 8"x8"x16"'),
            rc("RCP-301", "2026-08-03", "INV-STR-100001", 240000, 10, vendor="M/S Hamza Steel", uom="M.Ton", sub="Steel"),
            rc("RCP-305", "2026-08-20", "INV-STR-100001", 240000, 5, vendor="M/S Hamza Steel", uom="M.Ton", sub="Steel"),
            rc("RCP-12", "2023-02-01", "INV-STR-000001", 4767, 20, site="Quadrangle"),
        ]
        self.pos = [
            po("PO00000000000000000290", "2026-08-01", "RCP-300", 1, "Azmat Sons",
               [("INV-STR-100033", 'Concrete Hollow Block 8"x8"x16"', "Each", 1000, 210)]),
            po("PO00000000000000000292", "2026-08-01", "RCP-305", 2, "Hamza Steel",
               [("INV-STR-100001", "Deformed Steel Bars G-60 Dia #3", "M.Ton", 15, 240000)]),
            po("PO00000000000000000361", "2026-09-28", "RCP-328", 1, "Azmat Sons",
               [("INV-STR-100033", "concrete hollow block 8\"x8\"x16\"", "EACH", 2216, 210),
                ("INV-STR-100184", "Tarpauline 18'x24'", "Each", 4, 6000),
                ("INV-STR-100121", "Concrete Solid Blocks", "Each", 0, 215)]),
            po("PO00000000000000000362", "2026-09-29", "RCP-330", 2, "Azmat Sons",
               [("INV-STR-100033", "Concrete Hollow Block", "Each", 500, 210)]),
            po("PO00000000000000000363", "2026-09-30", None, 0, "Azmat Sons",
               [("INV-STR-100033", "Concrete Hollow Block", "Each", 0, 210)], status="Never Received"),
        ]
        self.res = T.merge(self.receipts, self.pos, "Phoenix")

    def test_single_grn_po_links_its_grn(self):
        r = self.receipts[0]
        self.assertEqual(r["po"], ["PO-290", "2026-08-01", "2026-08-01", None, "Completed", 1])
        self.assertNotIn("basis", r)

    def test_multi_grn_po_links_by_vendor_item_rate_and_quantity(self):
        self.assertEqual(self.receipts[1]["po"][0], "PO-292")
        self.assertEqual(self.receipts[2]["po"][0], "PO-292")
        self.assertEqual(self.res["unmatched"], [])

    def test_other_site_untouched(self):
        self.assertNotIn("po", self.receipts[3])

    def test_missing_single_grn_po_added_with_po_date(self):
        added = [r for r in self.receipts if r.get("basis") == "P"]
        self.assertEqual(len(added), 2)  # the 0-received line is left out
        blk, tarp = sorted(added, key=lambda r: r["code"])
        self.assertEqual((blk["grn"], blk["date"], blk["qty"], blk["rate"]), ("RCP-328", "2026-09-28", 2216, 210))
        # the register's own description, unit and category are kept for a known item
        self.assertEqual((blk["desc"], blk["uom"], blk["main"], blk["sub"]), ('Concrete Hollow Block 8"x8"x16"', "Each", "Grey", "Concrete Blocks"))
        self.assertEqual(blk["vendor"], "Azmat Sons")
        self.assertEqual(blk["po"][0], "PO-361")
        self.assertEqual((tarp["desc"], tarp["main"], tarp["sub"]), ("Tarpauline 18'x24'", T.UNSORTED, ""))

    def test_missing_multi_grn_po_listed_not_added(self):
        self.assertEqual([p["po"] for p in self.res["missing"]], ["PO00000000000000000362"])
        self.assertFalse(any(r["grn"] == "RCP-330" for r in self.receipts))

    def test_rerun_adds_nothing(self):
        before = len(self.receipts)
        res = T.merge(self.receipts, self.pos, "Phoenix")
        self.assertEqual(len(self.receipts), before)
        self.assertEqual(res["added"], [])

    def test_pack_round_trip_keeps_po_and_basis(self):
        data = GR.pack([dict(r) for r in self.receipts], ["test"])
        self.assertEqual(sorted(p[0] for p in data["pos"]), ["PO-290", "PO-292", "PO-361"])
        self.assertEqual(sum(1 for r in data["rc"] if r[7:] == ["P"]), 2)
        quad = {i for i, it in enumerate(data["items"]) if data["sites"][it[0]] == "Quadrangle"}
        self.assertTrue(all(len(r) == 6 for r in data["rc"] if r[0] in quad))  # unlinked rows keep the old shape
        back = GR.unpack(data)
        key = lambda r: (r["site"], r["grn"], r["code"], r["qty"])
        self.assertEqual(sorted((key(r), r.get("po"), r.get("basis")) for r in back),
                         sorted((key(r), r.get("po"), r.get("basis")) for r in self.receipts))

    def test_receiving_export_replaces_po_date(self):
        row = rc("RCP-328", "2026-10-01", "INV-STR-100033", 210, 2216, desc='Concrete Hollow Block 8"x8"x16"')
        self.assertEqual(GR.date_from_grn(self.receipts, [row]), 1)
        r = next(r for r in self.receipts if r["grn"] == "RCP-328" and r["code"] == "INV-STR-100033")
        self.assertEqual(r["date"], "2026-10-01")
        self.assertNotIn("basis", r)
        self.assertEqual(r["po"][0], "PO-361")


@unittest.skipUnless(os.environ.get("POPODET1_PDF"), "set POPODET1_PDF to parse a real Sage PO list")
class RealReport(unittest.TestCase):
    def test_parse(self):
        pos = T.read_pdf(os.environ["POPODET1_PDF"])
        self.assertTrue(pos)
        for p in pos:
            with self.subTest(po=p["po"]):
                self.assertTrue(p["date"])
                self.assertTrue(p["posted"] >= p["date"])
                self.assertNotRegex(p["vendor"], r"\d/\d")
                self.assertEqual(p["last"] is None, (p["n"] or 0) == 0)


if __name__ == "__main__":
    unittest.main()
