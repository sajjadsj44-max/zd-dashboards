#!/usr/bin/env python3
"""Load the KPK Market Rate System PDF into the dashboard's KPK MRS tab.

    tools/kpk_mrs.py "KPK Market Rate System 2025 (1st Bi Annual).pdf"
    tools/kpk_mrs.py --html path/to/index.html --edition "MRS-2025 (1st Bi-Annual)" \
        --notified 2025-10-07 --notification "No.MRS/FD/4-2/NOTIFICATION/2025" MRS.pdf

Reads every item page of the Finance Department (MRS Cell) schedule: item code,
description, British unit / labour / composite rate, metric unit / labour /
composite rate, specification reference and remarks. Columns are located on each
page from its own header row, and numbers are read exactly as printed - nothing
is recalculated. The district location factors (the "Area Factor" page and the
merged-area sub-zone table) are read from the front matter.

The whole schedule replaces the `<script type="application/json" id="raMrsData">`
block of the dashboard, so re-running with a newer bi-annual edition simply
swaps it in. The PDF itself is not committed.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import pymupdf
except ImportError:
    sys.exit("PyMuPDF is required: pip install pymupdf")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "zameen-developments" / "index.html"
BLOCK_RE = re.compile(
    r'(<script type="application/json" id="raMrsData">)(.*?)(</script>)', re.S)
CODE = re.compile(r"^\d{2}-\d{2,3}(-[A-Za-z0-9]+)*$")
SPEC_TOK = re.compile(r"^(\d+(\.\d+)*[A-Za-z]?,?|,|&)$")
NAMES = ["code", "desc", "ubr", "lbr", "cbr", "umt", "lmt", "cmt", "spec"]


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def num(s):
    s = s.replace(",", "").replace(" ", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def factors(doc):
    """District factors and merged-area sub-zone averages from the front matter."""
    dist, merged = [], []
    for pg in doc[:12]:
        t = [clean(x) for x in pg.get_text().split("\n") if clean(x)]
        j = " ".join(t)
        if "Area Factor For Khyber Pakhtunkhwa Districts" in j:
            for i in range(len(t) - 2):
                if t[i].isdigit() and re.match(r"^[A-Z .]+$", t[i + 1]) and re.match(r"^\d\.\d\d$", t[i + 2]):
                    dist.append([t[i + 1].title(), float(t[i + 2])])
        if "LOCATION FACTOR FOR MERGED AREAS" in j:
            for i in range(len(t) - 5):
                if t[i].isdigit() and re.search(r"[A-Za-z]", t[i + 1]) and all(
                        re.match(r"^\d\.\d\d$", t[i + k]) for k in range(2, 6)):
                    merged.append([t[i + 1], [float(t[i + k]) for k in range(2, 6)]])
    return dist, merged


def parse(doc):
    items = []
    for pn in range(len(doc)):
        pg = doc[pn]
        W = pg.get_text("words")
        hdr = defaultdict(list)
        for w in W:
            if w[1] < 135 and w[4] in ("Labour", "Composite", "Unit", "Spec."):
                hdr[w[4]].append(w[0])
                hdr[w[4] + "_r"].append(w[2])
        if len(hdr["Labour"]) < 2 or len(hdr["Composite"]) < 2 or len(hdr["Unit"]) < 2:
            continue  # front matter, not an item page
        lb, cp, un = sorted(hdr["Labour"]), sorted(hdr["Composite"]), sorted(hdr["Unit"])
        cpr = sorted(hdr["Composite_r"])
        spec = hdr["Spec."][0] if hdr["Spec."] else 578
        b = [0, 88, un[0] - 6, lb[0] - 4, cp[0] - 6, un[1] - 6, lb[1] - 8, cp[1] - 8, spec - 4, spec + 30]
        body = [w for w in W if 135 < w[1] < 580]
        starts = sorted((w for w in body if w[0] < 88 and CODE.match(w[4])), key=lambda w: w[1])
        if not starts:
            continue

        # remarks: whole paragraphs, each given to the item row it starts in
        lines = []
        for w in sorted((w for w in body if w[0] >= b[-1]), key=lambda w: (w[1], w[0])):
            if lines and abs(lines[-1][0] - w[1]) < 2.5:
                lines[-1][1].append(w)
            else:
                lines.append([w[1], [w]])
        paras = []
        for y, ws in lines:
            t = " ".join(x[4] for x in sorted(ws, key=lambda w: w[0]))
            if paras and y - paras[-1][2] < 13:
                paras[-1][1] += " " + t
                paras[-1][2] = y
            else:
                paras.append([y, t, y])
        prem = defaultdict(list)
        for y, t, _ in paras:
            k = max([j for j, s in enumerate(starts) if s[1] - 3 <= y] or [0])
            if not re.fullmatch(r"[\d.,\s]+", t):
                prem[k].append(t)

        for i, s in enumerate(starts):
            y0 = s[1] - 3
            y1 = starts[i + 1][1] - 3 if i + 1 < len(starts) else 9999
            cols = defaultdict(list)
            for w in body:
                if w is s or not (y0 <= w[1] < y1) or w[0] >= b[-1]:
                    continue
                for k in range(len(NAMES)):
                    if b[k] <= w[0] < b[k + 1]:
                        nm = NAMES[k]
                        if nm == "cmt" and w[2] > cpr[-1] + 4:
                            nm = "spec"
                        if nm == "cbr" and w[2] > cpr[0] + 6:
                            nm = "umt"
                        cols[nm].append(w)
                        break
            txt = lambda k: clean(" ".join(x[4] for x in sorted(cols[k], key=lambda w: (round(w[1]), w[0]))))
            sp = " ".join(x[4] for x in sorted(cols["spec"], key=lambda w: (round(w[1]), w[0]))
                          if SPEC_TOK.match(x[4]))
            sp = re.sub(r"\s*,\s*", ", ", sp).strip(" ,")
            items.append(dict(code=s[4], page=pn + 1, desc=txt("desc"),
                              ubr=txt("ubr"), lbr=num(txt("lbr")), cbr=num(txt("cbr")),
                              umt=txt("umt"), lmt=num(txt("lmt")), cmt=num(txt("cmt")),
                              spec=sp, rem=clean(" ".join(prem.get(i, [])))))
    return items


def chapters(doc):
    """Chapter number -> name, from the page headers ("<NAME> Chapter # : NN")."""
    names = defaultdict(Counter)
    for pg in doc:
        for b in pg.get_text("blocks"):
            parts = [clean(x) for x in b[4].split("\n")]
            if len(parts) >= 3 and parts[1].startswith("Chapter #") and parts[2].isdigit():
                names[parts[2].zfill(2)][parts[0]] += 1
    return {k: v.most_common(1)[0][0] for k, v in names.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--edition", default="MRS-2025 (1st Bi-Annual)")
    ap.add_argument("--notified", default="2025-10-07", help="notification date, YYYY-MM-DD")
    ap.add_argument("--notification", default="No.MRS/FD/4-2/NOTIFICATION/2025")
    a = ap.parse_args()

    html = a.html.read_text(encoding="utf-8")
    m = BLOCK_RE.search(html)
    if not m:
        sys.exit(f"{a.html}: no raMrsData block found")

    doc = pymupdf.open(a.pdf)
    items = parse(doc)
    chaps = chapters(doc)
    dist, merged = factors(doc)
    seen = Counter(x["code"] for x in items)
    dupes = [c for c, n in seen.items() if n > 1]
    if dupes:
        print("warning: repeated item codes:", ", ".join(dupes[:20]))

    data = {
        "edition": a.edition,
        "notified": a.notified,
        "notification": a.notification,
        "issuer": "MRS Cell, Finance Department, Government of Khyber Pakhtunkhwa",
        "base": "Peshawar",
        "note": "Composite rates include 23.5% (4% KP sales tax, 2% overheads, 7.5% income tax, 10% contractor's profit).",
        "source": a.pdf.name,
        "chapters": [[k, chaps[k]] for k in sorted(chaps)],
        "districts": dist,
        "merged": merged,
        # code, chapter, description, British unit, labour, composite, metric unit, labour, composite, spec, remarks, page
        "items": [[x["code"], x["code"][:2], x["desc"], x["ubr"], x["lbr"], x["cbr"],
                   x["umt"], x["lmt"], x["cmt"], x["spec"], x["rem"], x["page"]] for x in items],
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html[:m.start(2)] + blob + html[m.end(2):]
    a.html.write_text(html, encoding="utf-8")
    zero = sum(1 for x in items if not x["cbr"] and not x["cmt"])
    print(f"{len(items)} items in {len(chaps)} chapters ({zero} without a rate), "
          f"{len(dist)} district and {len(merged)} merged-area factors")


if __name__ == "__main__":
    main()
