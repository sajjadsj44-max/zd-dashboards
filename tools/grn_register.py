#!/usr/bin/env python3
"""Merge material receiving (GRN) exports into the dashboard's GRN Price Register.

    tools/grn_register.py RECEIVING.xlsx [MORE.xlsx ...]
    tools/grn_register.py --html path/to/index.html RECEIVING.xlsx

Each workbook is the ERP "material receiving" export: first sheet, header row
`Site | RCPHSEQ | PO # | GRN # | GRN Date | Vendor Name | ... | Item Code |
LOCATION | Item Description | Category | HASCOMMENT | UOM | Rec.Qty | ... |
UNITCOST | Value | Main Category | Sub Category`. Columns are found by header
name, so extra or reordered columns are fine.

Receipts already in the register are kept. A receipt counts as already held when
site, GRN, item code, description, quantity and rate match one in the register
(compared by count, since a GRN can repeat a line), so re-running with an
updated, cumulative export only adds the new GRNs. Receipts added from a Sage PO
list (tools/po_register.py) are dated by their PO date until an export holds the
same GRN line (site, GRN, item code, quantity, rate); its GRN date then replaces
the PO date. The data lives in the
`<script type="application/json" id="raGrnData">` block of the dashboard.

Units are normalised to the house units (Nos, Rft, Sft, Cft, Kg, Ton, Ltr ...).
Metric GRN units are converted, and the original unit is kept for the remarks:
Cubic Mtr -> Cft (rate / 35.3147), Metre -> Rft (rate x 0.3048),
Sq.Mt -> Sft (rate x 0.09290304).
"""
import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "zameen-developments" / "index.html"
BLOCK_RE = re.compile(
    r'(<script type="application/json" id="raGrnData">)(.*?)(</script>)', re.S)

# GRN unit (lower-cased) -> (house unit, factor applied to the GRN rate)
UNIT_MAP = {
    "each": ("Nos", 1), "pcs": ("Nos", 1), "nos": ("Nos", 1), "no": ("Nos", 1),
    "rft": ("Rft", 1), "kgs": ("Kg", 1), "kg": ("Kg", 1),
    "cubic mtr": ("Cft", 1 / 35.3147), "cum": ("Cft", 1 / 35.3147),
    "metre": ("Rft", 0.3048), "meter": ("Rft", 0.3048), "mtr": ("Rft", 0.3048),
    "sq.mt": ("Sft", 0.09290304), "sqm": ("Sft", 0.09290304),
    "m.ton": ("Ton", 1), "ton": ("Ton", 1),
    "ltr": ("Ltr", 1), "litre": ("Ltr", 1), "sq.ft": ("Sft", 1), "sft": ("Sft", 1),
    "cft": ("Cft", 1), "coil": ("Coil", 1), "pack": ("Pack", 1),
    "bottle": ("Bottle", 1), "roll": ("Roll", 1), "bucket": ("Bucket", 1),
    "pair": ("Pair", 1), "gallon": ("Gallon", 1), "box": ("Box", 1),
    "length": ("Length", 1), "set": ("Set", 1), "bag": ("Bag", 1),
}

HEAD = {
    "site": "site", "grn": "grn #", "date": "grn date", "vendor": "vendor name",
    "code": "item code", "desc": "item description", "uom": "uom",
    "qty": "rec.qty", "rate": "unitcost", "main": "main category",
    "sub": "sub category",
}


def clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (int, float)):
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
    return dt.datetime.strptime(clean(v)[:10], "%Y-%m-%d").date().isoformat()


def grn_no(v):
    m = re.match(r"([A-Za-z]+)0*(\d+)$", clean(v))
    return f"{m.group(1).upper()}-{int(m.group(2))}" if m else clean(v)


def read_xlsx(path):
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [clean(h).lower() for h in next(rows)]
    col = {}
    for key, name in HEAD.items():
        if name not in header:
            sys.exit(f"{path}: column '{name}' not found")
        col[key] = header.index(name)
    out = []
    for r in rows:
        g = lambda k: r[col[k]] if col[k] < len(r) else None
        if not clean(g("site")) or g("rate") in (None, ""):
            continue
        out.append({
            "site": clean(g("site")), "grn": grn_no(g("grn")),
            "date": to_date(g("date")), "vendor": clean(g("vendor")),
            "code": clean(g("code")), "desc": clean(g("desc")),
            "uom": clean(g("uom")), "qty": round(float(g("qty") or 0), 3),
            "rate": round(float(g("rate")), 2), "main": clean(g("main")),
            "sub": clean(g("sub")),
        })
    return out


def unpack(data):
    """Flatten the stored register back into receipt dicts.

    A receipt row is [item, date, rate, qty, grn, vendor] plus, when tools/po_register.py
    has linked it, the index of its PO in "pos" (-1 for none) and "P" when its date is
    that PO's date because the GRN date is not known yet."""
    if not data:
        return []
    items, pos, out = data["items"], data.get("pos", []), []
    for r in data["rc"]:
        ix, date, rate, qty, grn, vi = r[:6]
        s, code, desc, mi, si, uom = items[ix][:6]
        rec = {
            "site": data["sites"][s], "grn": grn, "date": date,
            "vendor": data["vendors"][vi], "code": code, "desc": desc,
            "uom": uom, "qty": qty, "rate": rate,
            "main": data["cats"][mi], "sub": data["cats"][si],
        }
        if len(r) > 6 and r[6] >= 0:
            rec["po"] = pos[r[6]]
        if len(r) > 7:
            rec["basis"] = r[7]
        out.append(rec)
    return out


def pack(receipts, sources):
    sites, vendors, cats, items, pos = [], [], [], [], []
    idx = lambda lst, v: lst.index(v) if v in lst else (lst.append(v) or len(lst) - 1)
    item_ix, po_ix = {}, {}
    receipts.sort(key=lambda r: (r["site"], r["desc"].lower(), r["code"], r["uom"], r["date"], r["grn"]))
    rc = []
    for r in receipts:
        key = (r["site"], r["code"], r["desc"], r["uom"])
        if key not in item_ix:
            unit, k = UNIT_MAP.get(r["uom"].lower(), (r["uom"].title() or "Nos", 1))
            item_ix[key] = len(items)
            items.append([idx(sites, r["site"]), r["code"], r["desc"],
                          idx(cats, r["main"]), idx(cats, r["sub"]), r["uom"],
                          unit, round(k, 8)])
        row = [item_ix[key], r["date"], r["rate"], r["qty"], r["grn"], idx(vendors, r["vendor"])]
        po = r.get("po")
        if po and po[0] not in po_ix:
            po_ix[po[0]] = len(pos)
            pos.append(po)
        if po or r.get("basis"):
            row.append(po_ix[po[0]] if po else -1)
        if r.get("basis"):
            row.append(r["basis"])
        rc.append(row)
    dates = [r["date"] for r in receipts]
    out = {
        "rev": dt.date.today().isoformat(), "sources": sources,
        "from": min(dates), "to": max(dates),
        "sites": sites, "vendors": vendors, "cats": cats, "items": items, "rc": rc,
    }
    if pos:
        out["pos"] = pos  # [PO no, PO date, posted on, arrival date, status, no. of receipts]
    return out


def save(path, html, m, data):
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path.write_text(html[:m.start(2)] + blob + html[m.end(2):], encoding="utf-8")


def date_from_grn(receipts, rows):
    """Give receipts added from a PO list (dated by PO date) the GRN date of the same receiving line."""
    waiting = {}
    for r in receipts:
        if r.get("basis") == "P":
            waiting.setdefault((r["site"], r["grn"], r["code"], r["qty"], r["rate"]), []).append(r)
    n = 0
    for row in rows:
        hit = waiting.get((row["site"], row["grn"], row["code"], row["qty"], row["rate"]))
        if hit:
            r = hit.pop(0)
            r.update({k: row[k] for k in ("date", "vendor", "desc", "uom", "main", "sub")})
            del r["basis"]
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("xlsx", nargs="+", type=Path)
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    a = ap.parse_args()

    html = a.html.read_text(encoding="utf-8")
    m = BLOCK_RE.search(html)
    if not m:
        sys.exit(f"{a.html}: no raGrnData block found")
    old = json.loads(m.group(2)) if m.group(2).strip() else None

    receipts = unpack(old)
    batches = [(p, read_xlsx(p)) for p in a.xlsx]
    dated = date_from_grn(receipts, [r for _, rows in batches for r in rows])
    key = lambda r: (r["site"], r["grn"], r["code"], r["desc"], r["qty"], r["rate"])
    # a GRN can list the same item twice, so compare counts rather than presence
    have = Counter(key(r) for r in receipts)
    sources = list(old["sources"]) if old else []
    added = 0
    for p, rows in batches:
        fresh = Counter()
        n = 0
        for r in rows:
            k = key(r)
            fresh[k] += 1
            if fresh[k] > have[k]:
                have[k] += 1
                receipts.append(r)
                n += 1
        if n:
            sources.append(f"{p.name} ({n} receipts, merged {dt.date.today().isoformat()})")
        added += n

    data = pack(receipts, sources)
    save(a.html, html, m, data)
    if dated:
        print(f"{dated} receipts dated by PO date now carry their GRN date")
    print(f"{added} new receipts added; register now {len(data['rc'])} receipts, "
          f"{len(data['items'])} items, {data['from']} to {data['to']}")


if __name__ == "__main__":
    main()
