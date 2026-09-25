"""Checks on the lab mix-design transcription (tools/lab_mix_data.py) and its data block."""
import json, os, re, sys, unittest

sys.path.insert(0, os.path.dirname(__file__))
import lab_mix_data as L

HTML = os.path.join(os.path.dirname(__file__), "..", "zameen-developments", "index.html")


class LabMixTest(unittest.TestCase):
    def test_register(self):
        self.assertTrue(L.check())
        self.assertEqual(len(L.PHOTOS), 15)
        self.assertEqual(len(L.RECS), 21)

    def test_same_psi_kept_separate(self):
        by = {}
        for r in L.RECS:
            by.setdefault(r["psi"], []).append(r["id"])
        self.assertEqual(sorted(by[4000]), ["LMX-ACI-4000", "LMX-J7-4000", "LMX-MUL-4000"])
        self.assertEqual(sorted(by[5000]), ["LMX-ACI5K-01", "LMX-J7-5000"])

    def test_printed_values(self):
        r = {x["id"]: x for x in L.RECS}
        kg = lambda i: [m["kg"] for m in r[i]["mats"]]
        self.assertEqual(kg("LMX-J7-4000"), [425, 192, 5.61, 105, 738, 211, 671])
        self.assertEqual(kg("LMX-ACI5K-01"), [550, 187, 418.60, 627.90, 647.70, 7.69])
        self.assertEqual(kg("LMX-MUL-6000"), [550, 628, 416, 590, 5.0, 212])
        self.assertEqual(kg("LMX-XL-04"), [530, 178, 5.3, 209, 839, 569])
        self.assertEqual(kg("LMX-ACI-6000"), [520, 660, 321, 588, 160, 6.2, 178])

    def test_every_record_flags_what_is_missing(self):
        for x in L.RECS:
            if x["lab"].startswith("Not shown"):
                self.assertTrue(any("name" in v for v in x["verify"]), x["id"])
            if x["psi"] is None:
                self.assertTrue(x["verify"], x["id"])

    def test_block_in_dashboard_is_current(self):
        html = open(HTML, encoding="utf-8").read()
        m = re.search(r'<script type="application/json" id="raLabMixData">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m, "run tools/lab_mix_data.py zameen-developments/index.html")
        d = json.loads(m.group(1).replace("<\\/", "</"))
        self.assertEqual(d["rev"], L.REV)
        self.assertEqual(d["recs"], json.loads(json.dumps(L.RECS)))


if __name__ == "__main__":
    unittest.main()
