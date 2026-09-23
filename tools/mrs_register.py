#!/usr/bin/env python3
"""Load a Punjab Market Rates System (MRS) PDF into the dashboard's MRS Rate Register.

    tools/mrs_register.py MRS.pdf
    tools/mrs_register.py MRS.pdf --chapters 2-13,19,24,25,26 --html path/to/index.html
    tools/mrs_register.py MRS.pdf --dump rows.json --no-write      # inspect only

Edition, district and period are read from the title line printed on every page
("MARKET RATES SYSTEM (MRS), 1st BI-ANNUAL-2026 (01.01.2026 to 30.06.2026)
DISTRICT RAWALPINDI") and chapter page ranges from the contents page, so a new
edition or another district loads the same way. The register replaces the
previous one; the data lives in the `<script type="application/json"
id="raMrsData">` block of the dashboard.

Rates are taken from the British-system columns (Labour and Composite, as
printed). Quantity units are normalised to house units -- per 100 Sft, "% Sft",
per 1000 Cft, per Cwt (to Kg) and so on -- with the printed unit and figure kept
alongside so every line can be checked against the PDF page it cites. Other
units (Job, Acre, Km, Letter per inch height ...) are kept as printed.

Needs pdfplumber (pip install pdfplumber).
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber is required: pip install pdfplumber")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "zameen-developments" / "index.html"
BLOCK_RE = re.compile(r'(<script type="application/json" id="raMrsData">)(.*?)(</script>)', re.S)

# building-construction chapters of the MRS; pass --chapters to change. Left out:
# canals, sheet piling, diversion, outlets, roads, drainage, sewerage, wells,
# tubewells, electrical and HVAC (not building-trade work), and Ch.1 Carriage,
# whose mile and km bands are printed over each other in the source PDF so its
# rows cannot be read back reliably.
DEFAULT_CHAPTERS = "2-13,19,25,26"

CWT_KG = 50.80234544          # 1 long hundredweight (112 lb)
LONG_TON_KG = 1016.0469088    # MRS British "Ton" is the long ton (its metric twin is per tonne)
MAUND_KG = 37.3242            # 1 maund (40 seer)
ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
         "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"}
DITTO = {"ditto", "-ditto-", "do", "-do-"}


# ---------------------------------------------------------------- page layout
def clean_num(s):
    s = (s or "").replace(" ", "").replace(",", "")
    if not s or set(s) <= set("-–—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def row_groups(words, tol=2.2):
    rows, cur, top = [], [], None
    for w in sorted(words, key=lambda w: w["top"]):
        if top is None or abs(w["top"] - top) <= tol:
            cur.append(w)
            top = w["top"] if top is None else top
        else:
            rows.append(cur)
            cur, top = [w], w["top"]
    if cur:
        rows.append(cur)
    return rows


def text_of(words, numeric=False):
    words = sorted(words, key=lambda w: w["x0"])
    if numeric:
        return "".join(w["text"] for w in words)
    t = " ".join(w["text"] for w in words)
    return re.sub(r"(?<=[\d,.\-])\s+(?=[,.\d])", "", t).strip()


def header_cols(rows):
    """Column extents from the page's own header lines:
    'Sr. Description Rate (British System) Rate (Metric System) Spec. Remarks'
    then 'Unit (of M/ment) Labour Composite' twice (British, metric).
    Returns ([(name, left, right)], header bottom, right edge of the description column)."""
    h1 = h_unit = h_lc = None
    for r in rows:
        t = [w["text"] for w in r]
        if h1 is None:
            if "Sr." in t and "Description" in t and "Rate" in t:
                h1 = r
            continue
        if h_lc is None and "Labour" in t and "Composite" in t:
            h_lc = r
            if h_unit is None and "Unit" in t:
                h_unit = r
        elif h_unit is None and "Unit" in t:
            h_unit = r
    if not h1 or not h_lc:
        return None, None, None
    ext = lambda row, word: [(w["x0"], w["x1"]) for w in sorted(row or [], key=lambda w: w["x0"]) if w["text"] == word]
    lab, comp = ext(h_lc, "Labour"), ext(h_lc, "Composite")
    spec, rem = ext(h1, "Spec."), ext(h1, "Remarks")
    unit = [x0 for x0, _ in (ext(h_unit, "Unit") or ext(h_lc, "M/ment"))]
    if len(unit) == 1 and len(lab) >= 2 and comp:
        # some chapters print no "Unit" heading over the metric unit column; it sits
        # a little past halfway between the British composite and metric labour columns
        unit.append(comp[0][0] + 0.55 * (lab[1][0] - comp[0][0]))
    if len(unit) < 2 or len(lab) < 2 or len(comp) < 2 or not spec or not rem:
        return None, None, None
    head = [w for row in (h_unit or [], h_lc) for w in row]

    def unit_ext(x):   # "Unit" / "of" / "M/ment" stacked over one column
        right = [w["x1"] for w in head if w["text"] in ("Unit", "of", "M/ment") and x - 6 <= w["x0"] <= x + 30]
        return (x, max(right) if right else x + 25)

    cols = [("unit1", *unit_ext(unit[0])), ("lab1", *lab[0]), ("comp1", *comp[0]),
            ("unit2", *unit_ext(unit[1])), ("lab2", *lab[1]), ("comp2", *comp[1]),
            ("spec", *spec[0]), ("rem", *rem[0])]
    return cols, h_lc[0]["top"], unit[0] - 15


NUMERIC = re.compile(r"^[\d,.\-–—]+$")
FOOTER = re.compile(r"^chap(ter)?\s*-?\s*\d", re.I)


def join_fragments(words):
    """The PDF sets many figures as touching fragments ("6" ".25", "1" "5.30",
    "6" ",090.50"); glue them back so a figure is never split between columns."""
    out = []
    for w in sorted(words, key=lambda w: w["x0"]):
        p = out[-1] if out else None
        if p and re.search(r"\d$", p["text"]) and re.match(r"^[.,]?\d", w["text"]) and w["x0"] - p["x1"] <= 1.0:
            out[-1] = dict(p, text=p["text"] + w["text"], x1=w["x1"])
        else:
            out.append(dict(w))
    return out


def page_rows(page, pno, warn=None):
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    rows = row_groups(words)
    cols, hdr_top, desc_right = header_cols(rows)
    if not cols:
        return []
    # text is left-aligned under its heading and only ever belongs to a text column (unit,
    # spec, remarks); figures are right-aligned, so they go to the column whose heading ends
    # nearest their right edge
    text_cols = [c for c in cols if c[0] in ("unit1", "unit2", "spec", "rem")]

    def text_col(x0):
        # distance from the column's heading span; a word far from every text column
        # (a full-width banner such as "BARBED WIRE FENCING") belongs to none of them
        dist = lambda c: max(c[1] - 12 - x0, 0, x0 - c[2]) if c[0] != "rem" else max(c[1] - 12 - x0, 0)
        best = min(text_cols, key=lambda c: (dist(c), c[1]))
        return best[0] if dist(best) <= 15 else None
    out = []
    for r in rows:
        if r[0]["top"] <= hdr_top + 2:
            continue
        if any(FOOTER.match(w["text"]) for w in r) and all(w["x0"] >= desc_right for w in r):
            continue                                  # page footer "Chap-6 (Concrete) ... Page 38"
        col = {name: [] for name in ["sr", "desc"] + [c[0] for c in cols]}
        left_words = [w for w in r if w["x0"] < desc_right]
        for w in left_words:
            col["sr" if w["x0"] < 30 else "desc"].append(w)
        for w in join_fragments([w for w in r if w["x0"] >= desc_right]):
            if NUMERIC.match(w["text"]):
                name = min(cols, key=lambda c: abs(w["x1"] - c[2]))[0]
            else:
                name = text_col(w["x0"])
            if name:
                col[name].append(w)
        for name in ("lab1", "comp1"):
            if len(col[name]) > 1 and warn is not None:
                warn.append(f"p.{pno}: two figures in one {name} cell: {[w['text'] for w in col[name]]}")
        # only a bare number (optionally with a letter) at the far left is a Sr. No.;
        # anything else that landed there is the start of the description
        srw = sorted(col["sr"], key=lambda w: w["x0"])
        m = re.match(r"^(\d+)([a-zA-Z]?)\)?\.?$", srw[0]["text"]) if srw else None
        sr = ""
        if m and int(m.group(1)) <= 100:
            sr = m.group(1) + m.group(2).lower()
            srw = srw[1:]
        out.append({
            "page": pno, "sr": sr,
            "desc": text_of(srw + sorted(col["desc"], key=lambda w: w["x0"])),
            "unit": text_of(col["unit1"]), "lab": clean_num(text_of(col["lab1"], True)),
            "comp": clean_num(text_of(col["comp1"], True)),
            "unit2": text_of(col["unit2"]), "lab2": clean_num(text_of(col["lab2"], True)),
            "comp2": clean_num(text_of(col["comp2"], True)),
        })
    return out


# ---------------------------------------------------------------- units
def norm_unit(raw):
    """MRS British unit -> (house unit, factor applied to the MRS rate)."""
    u = re.sub(r"\s+", " ", raw or "").strip()
    mult = 1
    m = re.match(r"^(?:per\b\.?|p\.)\s*", u, re.I)
    if m:
        u = u[m.end():]
    m = re.match(r"^(%|[\d,]+)\s*(.*)$", u)
    if m and (m.group(1) == "%" or m.group(1).replace(",", "").isdigit()):
        mult = 100 if m.group(1) == "%" else int(m.group(1).replace(",", ""))
        u = m.group(2)
    b = u.strip().strip(".").strip()
    table = {"sft": ("Sft", 1), "cft": ("Cft", 1), "rft": ("Rft", 1), "lft": ("Rft", 1),
             "foot": ("Rft", 1), "feet": ("Rft", 1),          # "Per foot" of pipe = running foot
             "no": ("Nos", 1), "nos": ("Nos", 1), "each": ("Nos", 1), "kg": ("Kg", 1),
             "ton": ("Ton", 1), "tons": ("Ton", 1), "tonne": ("Ton", 1), "cwt": ("Kg", 1 / CWT_KG),
             "mds": ("Kg", 1 / MAUND_KG), "maund": ("Kg", 1 / MAUND_KG)}
    first, _, rest = b.partition(" ")
    key = first.lower().replace(".", "")
    rest_key = rest.strip().strip(".").lower()
    if key == "each" and rest_key in ("no", "nos"):
        rest = ""                                       # "Each No."
    elif key == "each" and rest_key and not rest_key.startswith("per"):
        b, key, rest = rest.strip().strip("."), "", ""   # "Each Cut" -> per cut
    if key in table:
        # plain quantity unit, or one with a qualifier: "Sft per inch thickness"
        unit, k = table[key]
        rest = rest.strip().strip(".").lower()
        return unit + (" " + rest if rest else ""), k / mult
    if not b:
        return None, None
    # not a quantity unit (Job, Acre, Km, Chain, 1000 ft of lead ...): keep as printed
    if b.lower() == "km":
        b = "Km"
    label = (f"{mult} " if mult != 1 else "") + (b[:1].upper() + b[1:])
    return label, 1.0


# ---------------------------------------------------------------- nesting
MARK_RE = re.compile(r"^(\(\s*([A-Za-z]{1,5}|\d{1,2})\s*\)|([A-Za-z]{1,5}|\d{1,2})\))")


def marker(text, stack):
    """List marker at the start of a description line -> (style, cleaned text) or None.
    Style = bracket form + numbering kind + case, so "(i)" and "i)" nest separately."""
    g = re.match(r"^(\d{1,2})(?=[A-Z][a-z])", text)      # "1Providing ..." (number glued on)
    if g:
        return (")", "num", False), f"{g.group(1)}) {text[g.end():].strip()}"
    g = re.match(r"^(\d{1,2}|[A-Za-z]{1,5})\.\s+", text)  # "i. PORTA ...", "2. ..."
    if g and (g.group(1).isdigit() or g.group(1).lower() in ROMAN or len(g.group(1)) == 1):
        tok = g.group(1)
        kind = "num" if tok.isdigit() else "roman" if tok.lower() in ROMAN else "alpha"
        return (".", kind, tok.isupper()), f"{tok}. {text[g.end():].strip()}"
    g = re.match(r"^([A-H])\s+(?=[A-Z])", text)           # "A Two Piece" / "B One Piece"
    if g and len(text.split()) <= 5:
        return ("sp", "alpha", True), text
    m = MARK_RE.match(text)
    if not m:
        return None
    tok = m.group(2) or m.group(3)
    paren = "()" if m.group(2) else ")"
    low = tok.lower()
    if tok.isdigit():
        kind = "num"
    elif low in ROMAN:
        kind = "roman"
        # a lone i / v / x straight after h / u / w in an open letter list is a letter
        prev = {"i": "h", "v": "u", "x": "w"}.get(low)
        if prev:
            for st, t in stack:
                if st[0] == paren and st[1] == "alpha" and st[2] == tok.isupper() and \
                        re.match(r"^\(?\s*" + prev + r"\s*\)", t, re.I):
                    kind = "alpha"
    elif len(tok) == 1:
        kind = "alpha"
    else:
        return None                     # "mm)", "etc)" ... not a list marker
    style = (paren, kind, tok.isupper())
    rest = text[m.end():].strip()
    return style, (f"({tok})" if paren == "()" else f"{tok})") + (" " + rest if rest else "")


HEADING = ("hd", "hd", False)


def is_heading(text):
    """Short section line such as 'Brick Work' or 'Replacement items' -- no digits, no
    closing punctuation -- as opposed to wrapped text like 'Engineer Incharge.'"""
    return len(text.split()) <= 4 and not re.search(r"\d", text) and not re.search(r"[.,;:)\-]$", text) \
        and not text[:1].islower()


def build_items(rows, ch):
    """Group rows into Sr. blocks and give each rate line its full description:
    block header + open sub-headers + its own text + wrapped continuation lines.
    A wrapped unit cell ('100 Sft.' / 'Per Inch' / 'thickness') is joined up the
    same way: fragments before a block's first rate line lead its unit, fragments
    after a rate line trail it."""
    items, block_idx = [], {}
    header, stack, last, sr, sec_page = [], [], None, "", None
    unit_pre, prev_unit = [], None

    def flush_text(parts):
        return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()

    for r in rows:
        desc = r["desc"]
        if re.match(r"^(note|n\.b)\b|^\*", desc, re.I):
            # notes and "* Specification numbers correspond to ..." footnotes after a table
            header, stack, last, sr, unit_pre = [], [], None, "", []
            continue
        if r["sr"]:
            sr, header, stack, last, unit_pre = r["sr"], [], [], None, []
        rate_lab, rate_comp, unit_raw = r["lab"], r["comp"], r["unit"]
        metric = (r["unit2"], r["lab2"], r["comp2"])
        if rate_lab is None and rate_comp is None and re.match(r"^(per\s*)?k\.?m\.?$", r["unit2"], re.I) \
                and (r["lab2"] is not None or r["comp2"] is not None):
            rate_lab, rate_comp, unit_raw = r["lab2"], r["comp2"], "Km"   # carriage by the km
            metric = ("", None, None)
        is_leaf = rate_lab is not None or rate_comp is not None
        mk = marker(desc, stack) if desc else None
        if mk:
            desc = mk[1]
            depth = next((i for i, (st, _) in enumerate(stack) if st == mk[0]), None)
            if depth is not None:
                del stack[depth:]
        if is_leaf:
            key = sr or f"P{sec_page or r['page']}"
            n = block_idx[key] = block_idx.get(key, 0) + 1
            item = {"ch": ch, "sr": sr, "key": key, "n": n, "page": r["page"],
                    "head": flush_text(header), "parts": [t for _, t in stack] + [desc],
                    "unit_parts": unit_pre + [unit_raw], "lab": rate_lab, "comp": rate_comp,
                    "metric": metric}
            items.append(item)
            last, unit_pre = ("leaf", item), []
            continue
        if r["unit"]:
            if last and last[0] == "leaf":
                last[1]["unit_parts"].append(r["unit"])
            else:
                unit_pre.append(r["unit"])
        if not desc:
            continue
        if mk:
            stack.append([mk[0], desc])
            last = ("stack", len(stack) - 1)
        elif last is None:
            header.append(desc)
        elif last[0] == "leaf" and is_heading(desc):
            # an unnumbered heading after rate lines ("Replacement items") opens a new
            # section: the numbered item above no longer describes what follows
            sr, header, stack, last, sec_page = "", [desc], [], None, r["page"]
        elif last[0] == "leaf":
            last[1]["parts"][-1] += " " + desc
        elif last[1] < len(stack):
            stack[last[1]][1] += " " + desc
        else:
            header.append(desc)

    out, prev_metric = [], None
    for it in items:
        raw = re.sub(r"-\s+(?=[a-z])", "", " ".join(u for u in it.pop("unit_parts") if u))  # "Char- coal"
        raw = re.sub(r"\s+", " ", raw).strip()
        if raw.strip(".").lower() in DITTO or not raw:
            if not prev_unit:
                continue
            unit, k, raw = prev_unit
        else:
            unit, k = norm_unit(raw)
            if unit is None:
                continue
        prev_unit = (unit, k, raw)
        m_raw, m_lab, m_comp = it.pop("metric")
        m = metric_unit(m_raw)
        if m is None and m_raw.strip(". ").lower() in DITTO | {"", "per"}:
            m = prev_metric
        prev_metric = m or prev_metric
        if unit == "Ton" and re.match(r"^(per\s*|p\.\s*)?tons?\.?$", raw, re.I) and m_raw and re.search(r"tonne", m_raw, re.I):
            k = 1000 / LONG_TON_KG      # British "Ton" beside a metric "Tonne" figure is the long ton
        it.update(path=flush_text(it.pop("parts")), mrs_unit=raw, unit=unit, k=k)
        it["xc"], it["xnote"] = cross_check(it, m, m_lab, m_comp)
        out.append(it)
    return out


def metric_unit(raw):
    """Metric unit printed beside a rate -> (house base unit, metric-per-house factor, multiplier)."""
    u = re.sub(r"^(?:-+|\.\d+)\s+", "", re.sub(r"\s+", " ", raw or "").strip())   # stray "--" / ".25"
    u = re.sub(r"^(per|p)\b\.?\s*", "", u, flags=re.I).strip()
    mult = 1
    g = re.match(r"^([\d,]+)\s*(.*)$", u)
    if g:
        mult, u = int(g.group(1).replace(",", "")), g.group(2).strip()
    key = u.lower().replace(".", "").replace(" ", "")
    table = {"sqm": ("Sft", 10.7639104), "cum": ("Cft", 35.3146667), "metre": ("Rft", 3.2808399),
             "meter": ("Rft", 3.2808399), "mtr": ("Rft", 3.2808399), "m": ("Rft", 3.2808399),
             "each": ("Nos", 1), "no": ("Nos", 1), "nos": ("Nos", 1), "kg": ("Kg", 1),
             "ton": ("Ton", 1), "tonne": ("Ton", 1), "km": ("Km", 1), "hect": ("Acre", 2.4710538),
             "ltr": ("Gallon", None)}   # MRS uses both imperial and US gallons; see cross_check
    return (table[key][0], table[key][1], mult) if key in table else None


def cross_check(it, m, m_lab, m_comp):
    """MRS prints every rate twice, British and metric, on the same row. Converted, they
    must agree: 1 = they do (the line is confirmed), -1 = the schedule's own two figures
    disagree (flagged, with the metric figure for comparison), 0 = cannot be compared."""
    if not m:
        return 0, ""
    base, factor, mult = m
    if it["unit"].split(" ")[0] != base:
        return 0, ""
    best = None
    # per litre vs per gallon: the schedule uses imperial (4.546 L) and US (3.785 L)
    # gallons in different items, so accept whichever one both columns agree on
    for f in ([1 / 4.54609, 1 / 3.78541] if factor is None else [factor]):
        res, notes = [], []
        for name, b, mv in (("labour", it["lab"], m_lab), ("composite", it["comp"], m_comp)):
            if b is None or mv is None:
                continue
            exp, got = b * it["k"] * f, mv / mult
            ok = abs(got - exp) <= max(0.015 * exp, 0.06)
            res.append(ok)
            if not ok:
                notes.append(f"{name} {mv:,.2f} per {m_unit_label(base)} = {got / f:,.2f} per {base}")
        if res and all(res):
            return 1, ""
        best = best or (res, notes)
    if not best or not best[0]:
        return 0, ""
    return -1, "MRS metric column gives " + "; ".join(best[1])


def m_unit_label(base):
    return {"Sft": "Sqm", "Cft": "Cum", "Rft": "metre", "Gallon": "litre", "Acre": "hectare"}.get(base, base)


# ---------------------------------------------------------------- document
TITLE_RE = re.compile(
    r"MARKET RATES SYSTEM \(MRS\),?\s*(\w+)\s*BI-?\s*ANNUAL-?\s*(\d{4})\s*"
    r"\((\d{2})\.(\d{2})\.(\d{4})\s*to\s*(\d{2})\.(\d{2})\.(\d{4})\)\s*DISTRICT\s+([A-Za-z .]+?)\s*$", re.I)


def doc_meta(pdf):
    for p in pdf.pages[:5]:
        for line in (p.extract_text() or "").splitlines():
            m = TITLE_RE.search(re.sub(r"\s+", " ", line).strip())
            if m:
                return {"edition": f"{m.group(1)} Bi-Annual {m.group(2)}",
                        "from": f"{m.group(5)}-{m.group(4)}-{m.group(3)}",
                        "to": f"{m.group(8)}-{m.group(7)}-{m.group(6)}",
                        "district": m.group(9).strip().title()}
    return {}


def contents(pdf):
    for p in pdf.pages[:5]:
        rows = re.findall(r"^\s*(\d{1,2})\s+(.+?)\s+(\d{1,3})\s+to\s+(\d{1,3})\s*$",
                          p.extract_text() or "", re.M)
        if len(rows) >= 5:
            return [(int(c), n.strip().rstrip("."), int(a), int(b)) for c, n, a, b in rows]
    sys.exit("contents page not found -- chapter page ranges unknown")


def parse_chapters(spec):
    out = set()
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--chapters", default=DEFAULT_CHAPTERS, help="e.g. 1-13,19,25,26 or 'all'")
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--source", help="source file name to cite (default: the PDF's own name)")
    ap.add_argument("--dump", type=Path, help="also write the parsed lines here as JSON")
    ap.add_argument("--no-write", action="store_true", help="parse only, leave the dashboard alone")
    a = ap.parse_args()
    if not a.pdf.is_file():
        sys.exit(f"{a.pdf}: file not found")

    with pdfplumber.open(a.pdf) as pdf:
        meta = doc_meta(pdf)
        if not meta:
            sys.exit("title line (edition / period / district) not found")
        toc = contents(pdf)
        want = {c for c, *_ in toc} if a.chapters == "all" else parse_chapters(a.chapters)
        chapters, items, warn = [], [], []
        for ch, name, p1, p2 in toc:
            if ch not in want:
                continue
            rows = []
            for pno in range(p1, min(p2, len(pdf.pages)) + 1):
                rows.extend(page_rows(pdf.pages[pno - 1], pno, warn))
            got = build_items(rows, ch)
            chapters.append([ch, name, p1, p2, len(got)])
            items.extend(got)
            print(f"  Ch.{ch:<2} {name:<48} p.{p1}-{p2}: {len(got)} rate lines")
    for w in warn:
        print("  check:", w)

    heads, head_ix = [], {}
    for i in items:
        if i["head"] not in head_ix:
            head_ix[i["head"]] = len(heads)
            heads.append(i["head"])
    data = dict(meta)
    data.update({
        "source": a.source or a.pdf.name, "loaded": dt.date.today().isoformat(),
        "chapters": chapters,
        "heads": heads,
        # [chapter, item (Sr. No., or P<page> for an unnumbered section), line in item, page,
        #  item heading (index into heads), the line's own sub-heads + text,
        #  MRS unit as printed, house unit, factor to house unit, labour, composite,
        #  metric cross-check (1 confirmed, 0 not comparable, -1 MRS's two columns disagree), note]
        "items": [[i["ch"], i["key"], i["n"], i["page"], head_ix[i["head"]], i["path"], i["mrs_unit"],
                   i["unit"], round(i["k"], 10), i["lab"], i["comp"], i["xc"], i["xnote"]] for i in items],
    })
    xc = [i["xc"] for i in items]
    print(f"metric cross-check: {xc.count(1)} lines confirmed by the MRS metric column, "
          f"{xc.count(-1)} where the MRS's own two columns disagree (flagged), {xc.count(0)} not comparable")
    print(f"{meta['edition']}, District {meta['district']} ({meta['from']} to {meta['to']}): "
          f"{len(items)} rate lines from {len(chapters)} chapters")
    if a.dump:
        a.dump.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.no_write:
        return
    html = a.html.read_text(encoding="utf-8")
    m = BLOCK_RE.search(html)
    if not m:
        sys.exit(f"{a.html}: no raMrsData block found")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    a.html.write_text(html[:m.start(2)] + blob + html[m.end(2):], encoding="utf-8")
    print(f"written to {a.html}")


if __name__ == "__main__":
    main()
