#!/usr/bin/env python3
"""Link the GRN Price Register to Sage purchase orders, and add the receipts it does not hold yet.

    tools/po_register.py POPODET1.pdf [--site Phoenix] [--html path/to/index.html]

Input is the Sage 300 report "P/O Purchase Order List (POPODET1)" printed to PDF with
Include Purchase Order Information and Include Purchase Order Details set to Yes.
Zameen Omega's Sage company is the Phoenix site, hence the default --site.

Per PO the report gives Posted On, Purchase Order Date, Arrival Date, status, Last
Receipt Number and No. of Receipts; per line the item, Qty Ordered, Qty Received,
unit and Unit Cost. It does not give a receipt's own (GRN) date.

1. Link: each receipt of the site that came from a PO line gets that PO's number and
   dates. A PO received in one GRN links the lines of that GRN with the same item and
   rate; a PO received in several GRNs links the receipts of the same vendor, item and
   rate dated on or after the PO date, up to the quantity received.
2. Add: a PO received in one GRN that the register does not hold at all is added line
   by line (Qty Received at the Unit Cost) under that GRN, dated by the PO date and
   flagged "P", since the GRN date is not in this report. A later receiving export
   that holds the same GRN line replaces the PO date with the GRN date
   (tools/grn_register.py). A missing PO received in several GRNs is listed, not
   added: the report does not split its quantity by GRN.

Dates sit in fixed columns. Long vendor names overprint the Posted On date in the PDF
text ("(PRIVAT2E/)2 3L/I2M0I2T4ED"), so header dates and vendor names are read
character by character from their column positions.
"""
import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grn_register as GR  # noqa: E402

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber is required: pip install pdfplumber")

# left edge (pt) of each PO header date column, as printed by POPODET1
DATE_X = {"posted": 318.5, "date": 367.2, "arrival": 421.0}
VENDOR_END_X = 470            # vendor name ends before the Status column
STATUS_X = (470, 555)
RECEIPT_X = (600, 700)        # Last Receipt Number and No. of Receipts values
UNIT_X = (250, 350)           # unit of measure, printed under Qty Ordered
FLAG_X = 271.0                # Completed: Yes / No on the item line
NUM = r"-?[\d,]+\.\d+"
DETAIL_RE = re.compile(rf"^(\S+) (\S+) (\d+) ({NUM}) ({NUM}) ({NUM}) ({NUM}) ({NUM}) ({NUM}) ({NUM})$")
CODE_RE = re.compile(r"^[A-Z]{2,5}-[A-Z0-9]{2,6}-\d+$")
PO_RE = re.compile(r"^PO\d{6,}$")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
PAGE_HEAD_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2}\s?[AP]M Page \d+$")
UNSORTED = "Not categorised"


def num(s):
    return float(s.replace(",", ""))


def rows_of(page):
    """The page's words grouped into text lines, top to bottom."""
    rows = []
    for w in sorted(page.extract_words(), key=lambda w: w["top"]):
        if rows and w["top"] - rows[-1]["top"] < 2:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        r["text"] = " ".join(w["text"] for w in r["words"])
    return rows


def date_at(chars, x):
    """The m/d/yyyy whose first character starts at x, chained character by character."""
    run = [c for c in chars if c["text"] in "0123456789/"]
    cur = next((c for c in run if abs(c["x0"] - x) < 1.5), None)
    out = []
    while cur:
        out.append(cur)
        cur = next((c for c in run if all(c is not o for o in out) and abs(c["x0"] - cur["x1"]) < 0.6), None)
    m = DATE_RE.match("".join(c["text"] for c in out))
    if not m:
        return None, []
    return dt.date(int(m[3]), int(m[1]), int(m[2])).isoformat(), out


def item_text(row):
    """The item line without its Completed flag, which long descriptions run under."""
    line = sorted((c for c in row["chars"] if abs(c["top"] - row["top"]) < 2), key=lambda c: c["x0"])
    for flag in ("Yes", "No"):
        out, x = [], FLAG_X
        for ch in flag:
            c = next((c for c in line if c["text"] == ch and abs(c["x0"] - x) < (0.6 if out else 1.5)
                      and all(c is not o for o in out)), None)
            if not c:
                break
            out.append(c)
            x = c["x1"]
        if len(out) == len(flag):
            line = [c for c in line if all(c is not o for o in out)]
            break
    return GR.clean("".join(c["text"] for c in line))


def header(row, chars):
    w = row["words"]
    line = [c for c in chars if abs(c["top"] - row["top"]) < 2]
    dates, used = {}, []
    for k, x in DATE_X.items():
        dates[k], cs = date_at(line, x)
        used += cs
    name = "".join(c["text"] for c in sorted(line, key=lambda c: c["x0"])
                   if w[1]["x1"] < c["x0"] < VENDOR_END_X and all(c is not u for u in used))
    return {
        "po": w[0]["text"], "vcode": w[1]["text"], "vendor": GR.clean(name),
        "posted": dates["posted"], "date": dates["date"], "arrival": dates["arrival"],
        "status": " ".join(x["text"] for x in w if STATUS_X[0] <= x["x0"] < STATUS_X[1]),
        "last": None, "n": None, "lines": [],
    }


def read_pdf(path):
    """Every PO of the report with its header fields and lines."""
    pos, rows = [], []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for r in rows_of(page):
                if PAGE_HEAD_RE.match(r["text"]):
                    continue
                w = r["words"]
                if PO_RE.match(w[0]["text"]) and w[0]["x0"] < 60 and len(w) > 2:
                    pos.append(header(r, page.chars))
                    r["po_start"] = True
                r["chars"] = page.chars
                rows.append(r)
    po, since = None, 0
    pos_iter = iter(pos)
    for i, r in enumerate(rows):
        if r.get("po_start"):
            po, since = next(pos_iter), 0
            continue
        if po is None:
            continue
        since += 1
        if since <= 3:
            for x in r["words"]:
                if RECEIPT_X[0] <= x["x0"] < RECEIPT_X[1]:
                    if re.match(r"^RCP\d+$", x["text"]) and po["last"] is None:
                        po["last"] = GR.grn_no(x["text"])
                    elif x["text"].isdigit() and po["n"] is None:
                        po["n"] = int(x["text"])
        m = DETAIL_RE.match(r["text"])
        if not m:
            continue
        item = item_text(rows[i - 1])
        code, _, desc = item.partition(" ")
        if not CODE_RE.match(code):
            code, desc = "", item
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        unit = ""
        if nxt and UNIT_X[0] <= nxt["words"][0]["x0"] < UNIT_X[1] and nxt["words"][-1]["x1"] < UNIT_X[1] + 5:
            unit = nxt["text"]
        po["lines"].append({
            "code": code, "desc": GR.clean(desc), "loc": m[1], "unit": unit,
            "ordered": num(m[4]), "received": num(m[5]), "outstanding": num(m[6]), "rate": num(m[7]),
        })
    return pos


def vkey(s):
    """Vendor name for comparison: case, punctuation, bracketed parts and company suffixes ignored."""
    s = re.sub(r"\(.*?\)", " ", s.lower())
    s = re.sub(r"\b(m/s|messrs|pvt|private|ltd|limited|smc|co|company|and)\b|&", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def same_vendor(a, b):
    a, b = vkey(a), vkey(b)
    return bool(a and b) and (a == b or (min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a))))


def rcp_no(grn):
    m = re.search(r"(\d+)$", grn or "")
    return int(m.group(1)) if m else 0


def tag(p):
    """What the register keeps of a PO: number, PO date, posted on, arrival, status, receipts."""
    return [GR.grn_no(p["po"]), p["date"], p["posted"], p["arrival"], p["status"], p["n"]]


def merge(receipts, pos, site):
    """Link the site's receipts to their POs and add the single-GRN POs the register does not hold."""
    mine = [r for r in receipts if r["site"] == site]
    by_grn = defaultdict(list)
    for r in mine:
        by_grn[r["grn"]].append(r)
    linked, linked_pos, added, missing, unmatched = set(), set(), [], [], []

    def link(r, p):
        r["po"] = tag(p)
        linked.add(id(r))
        linked_pos.add(p["po"])

    def base(line):
        """The register's own item for this code, so descriptions, units and categories stay as they are."""
        same = [r for r in mine if line["code"] and r["code"] == line["code"]]
        unit = [r for r in same if r["uom"].lower() == line["unit"].lower()]
        desc = [r for r in unit if r["desc"].lower() == line["desc"].lower()]
        return (desc or unit or [None])[0], (same or [None])[0]

    def vendor(name):
        return next((r["vendor"] for r in mine if same_vendor(r["vendor"], name)), name)

    received = lambda p: [l for l in p["lines"] if l["received"] > 0]
    # a PO received in one GRN: that GRN's lines with the same item and rate are this PO's
    for p in (p for p in pos if p["last"] and p["n"] == 1):
        if p["last"] in by_grn:
            for l in received(p):
                hits = [r for r in by_grn[p["last"]] if r["code"] == l["code"] and abs(r["rate"] - l["rate"]) < 0.005]
                for r in hits:
                    link(r, p)
                if not hits:
                    unmatched.append((p, l))
            continue
        if not p["date"]:
            missing.append(p)
            continue
        for l in received(p):
            item, any_unit = base(l)
            info = item or any_unit
            added.append({
                "site": site, "grn": p["last"], "date": p["date"], "vendor": vendor(p["vendor"]),
                "code": l["code"], "desc": info["desc"] if info else l["desc"],
                "uom": item["uom"] if item else l["unit"], "qty": round(l["received"], 3),
                "rate": round(l["rate"], 2), "main": info["main"] if info else UNSORTED,
                "sub": info["sub"] if info else "", "po": tag(p), "basis": "P",
            })
    # a PO received in several GRNs: same vendor, item and rate, on or after the PO date
    # (a GRN is at most a day before its PO), up to the GRN it was last received on
    for p in (p for p in pos if p["last"] and (p["n"] or 0) > 1):
        if p["last"] not in by_grn:
            missing.append(p)
            continue
        since = (dt.date.fromisoformat(p["date"]) - dt.timedelta(days=1)).isoformat() if p["date"] else ""
        for l in received(p):
            left = l["received"]
            for r in sorted((r for r in mine if id(r) not in linked and r["code"] == l["code"]
                             and abs(r["rate"] - l["rate"]) < 0.005 and r["date"] >= since
                             and rcp_no(r["grn"]) <= rcp_no(p["last"]) and same_vendor(r["vendor"], p["vendor"])),
                            key=lambda r: (r["date"], rcp_no(r["grn"]))):
                if r["qty"] <= left + 1e-6:
                    link(r, p)
                    left -= r["qty"]
            if left > 1e-6:
                unmatched.append((p, l))
    receipts.extend(added)
    return {"linked": len(linked), "pos": len(linked_pos), "added": added,
            "missing": missing, "unmatched": unmatched}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--site", default="Phoenix")
    ap.add_argument("--html", type=Path, default=GR.DEFAULT_HTML)
    a = ap.parse_args()

    html = a.html.read_text(encoding="utf-8")
    m = GR.BLOCK_RE.search(html)
    if not m or not m.group(2).strip():
        sys.exit(f"{a.html}: no GRN register data (raGrnData) found")
    old = json.loads(m.group(2))
    if a.site not in old["sites"]:
        sys.exit(f"site '{a.site}' is not in the register ({', '.join(old['sites'])})")
    receipts = GR.unpack(old)
    pos = read_pdf(a.pdf)
    res = merge(receipts, pos, a.site)

    waiting = sum(1 for r in receipts if r.get("basis") == "P")
    with_po = [r for r in receipts if r["site"] == a.site and r.get("po")]
    today = dt.date.today().isoformat()
    sources = [s for s in old["sources"] if not s.startswith(a.pdf.name + " ")]
    sources.append(f"{a.pdf.name} (Sage PO list, {len(pos)} POs: {len(with_po)} {a.site} receipts carry their PO, "
                   f"{len({r['po'][0] for r in with_po})} POs; {waiting} receipts dated by PO date until a receiving "
                   f"export gives their GRN date; merged {today})")
    data = GR.pack(receipts, sources)
    GR.save(a.html, html, m, data)

    print(f"{len(pos)} POs read. {res['linked']} receipts linked to {res['pos']} POs; "
          f"{len(res['added'])} receipts added, dated by PO date:")
    for r in res["added"]:
        print(f"  {r['grn']:>8}  {r['po'][0]:>7}  PO date {r['date']}  {r['qty']:>10,.3f} {r['uom']:<9} "
              f"@ {r['rate']:>10,.2f}  {r['desc'][:50]}")
    for p in res["missing"]:
        print(f"  not added: {GR.grn_no(p['po'])} last received on {p['last']} in {p['n']} GRNs "
              f"(quantity per GRN not in the report)")
    for p, l in res["unmatched"]:
        print(f"  not matched: {GR.grn_no(p['po'])} {l['code']} {l['desc'][:40]} — {l['received']:,.3f} "
              f"received @ {l['rate']:,.2f}, no register receipt with that item and rate")
    print(f"Register now {len(data['rc'])} receipts, {len(data['items'])} items, {data['from']} to {data['to']}")


if __name__ == "__main__":
    main()
