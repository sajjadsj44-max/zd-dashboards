#!/usr/bin/env python3
"""Build the QS Rate Analysis Engine data block of the dashboard.

    tools/qs_engine_data.py                       # writes zameen-developments/index.html
    tools/qs_engine_data.py --html path/to/index.html --as-of 2026-09-26

The engine (the "QS Rate Analysis Engine" script in the dashboard) reads the
`<script type="application/json" id="raQsEngine">` block written here:

  cats        the 19 QS categories and their sub-categories
  rules       classifier: first rule whose code / old category / sub / description
              regexes all match gives an item its QS category and sub-category
              ("$sub" = keep the item's own sub-category)
  rates       purchase-unit rate lines the builders need. GRN lines are read from the
              GRN Price Register block (#raGrnData) of the same page and use the same
              codes as its "+ Rate DB" button (GRN-<SITE>-<code>), so a line the MEP
              analyses already carry is shared, not duplicated. Anything without a
              dated source is kept at 0 and marked "ASSUMPTION — no dated source".
  fixes       corrections of existing rate lines, applied only where the line still
              holds the seeded value (`from`), so a rate typed by the user is kept
  conv        seed items rebuilt as material-based builders, applied only where the
              item's material rows are still exactly as seeded (`guard`)
  items       new builder items
  composite   rate lines that are installed / lump rates used as if they were a
              material; any item using one is marked Review Required
  audit       findings on seed items, shown while the item still matches its seed
  prevRates   earlier published versions of this block's own rate lines

Every rate follows CLAUDE.md: `<source>, DD-Mon-YYYY — <details>` with the same date
in the effective date, or 0 / ASSUMPTION when there is no dated source.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "zameen-developments" / "index.html"
GRN_RE = re.compile(r'<script type="application/json" id="raGrnData">(.*?)</script>', re.S)
BLOCK_RE = re.compile(r'(<script type="application/json" id="raQsEngine">)(.*?)(</script>)', re.S)
ANCHOR = '<script type="application/json" id="calcData">'
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NOSRC = "ASSUMPTION — no dated source"


def dmy(d):
    y, m, dd = d.split("-")
    return f"{dd}-{MON[int(m) - 1]}-{y}"


def rs(v):
    return f"{v:,.2f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- GRN
class Grn:
    """Latest-receipt view of the GRN Price Register (same codes as its + Rate DB button)."""

    def __init__(self, html, as_of):
        m = GRN_RE.search(html)
        if not m:
            sys.exit("GRN Price Register block (#raGrnData) not found")
        d = json.loads(m.group(1))
        self.as_of = as_of
        self.items = []
        for ix, it in enumerate(d["items"]):
            self.items.append({"ix": ix, "site": d["sites"][it[0]], "code": it[1], "desc": it[2],
                               "uom": it[5], "unit": it[6], "k": it[7], "rc": []})
        for ix, date, rate, qty, grn, vi in d["rc"]:
            it = self.items[ix]
            it["rc"].append({"date": date, "grnRate": rate, "rate": round(rate * it["k"] + 1e-9, 2),
                             "grn": grn, "vendor": d["vendors"][vi]})
        seen = {}
        for it in self.items:
            seen[(it["site"], it["code"])] = seen.get((it["site"], it["code"]), 0) + 1
        for it in self.items:
            it["rc"].sort(key=lambda r: (r["date"], r["grn"]), reverse=True)
            it["last"] = it["rc"][0] if it["rc"] else None
            code = re.sub(r"^INV-", "", it["code"]) or "X"
            dup = seen[(it["site"], it["code"])] > 1 or not it["code"]
            it["db"] = "GRN-" + it["site"][:3].upper() + "-" + code + (f"-{it['ix']}" if dup else "")

    def find(self, site, desc):
        hits = [it for it in self.items if it["site"] == site and it["desc"] == desc and it["last"]]
        if len(hits) != 1:
            sys.exit(f"GRN item not found exactly once: {site} / {desc!r} ({len(hits)} hits)")
        return hits[0]

    def remark(self, it):
        l, rates = it["last"], [r["rate"] for r in it["rc"]]
        age = (self.as_of - dt.date.fromisoformat(l["date"])).days
        s = f"{it['site']} GRN {l['grn'] or '(no receipt no.)'}, {dmy(l['date'])} — {l['vendor'] or 'vendor not recorded'}"
        if it["k"] != 1:
            s += f"; billed {rs(l['grnRate'])} per {it['uom']}, converted to per {it['unit']}"
        if len(it["rc"]) > 1:
            s += f"; {len(it['rc'])} receipts, range {rs(min(rates))}–{rs(max(rates))}"
        if age > 365:
            s += f". Dated {l['date'][:4]} — reconfirm before use"
        return s

    def line(self, site, desc, unit=None):
        it = self.find(site, desc)
        l = it["last"]
        return {"code": it["db"], "kind": "M", "name": it["desc"], "unit": unit or it["unit"], "rate": l["rate"],
                "loc": "Lahore", "src": self.remark(it), "date": l["date"], "vs": "V" if l["vendor"] else "I"}

    def per(self, code, name, unit, site, desc, content, cunit, vs="V"):
        """A purchase-pack GRN converted to a per-unit line (e.g. 18 L bucket → per Ltr)."""
        it = self.find(site, desc)
        l = it["last"]
        rate = round(l["rate"] / content, 2)
        src = (self.remark(it) + f"; {rs(l['rate'])} per {it['uom']} of {rs(content)} {cunit} "
               f"= {rs(l['rate'])} ÷ {rs(content)} = {rs(rate)} per {unit}")
        return {"code": code, "kind": "M", "name": name, "unit": unit, "rate": rate, "loc": "Lahore",
                "src": src, "date": l["date"], "vs": vs}


def zero(code, name, unit, evidence):
    return {"code": code, "kind": "M", "name": name, "unit": unit, "rate": 0, "loc": "Lahore",
            "src": f"{NOSRC}. {evidence}", "date": "", "vs": "A"}


# ------------------------------------------------------------------ taxonomy
CATS = [
    ("C01", "Civil Works", ["Site preparation", "Earthwork", "Anti-termite", "Dismantling"]),
    ("C02", "Structural / Grey Structure", ["Formwork", "General"]),
    ("C03", "Concrete and Concrete Mix Designs", ["PCC", "RCC — nominal mix", "RCC — ready-mix", "RCC — lab design mix"]),
    ("C04", "Reinforcement and Structural Steel", ["Reinforcement", "Structural steel"]),
    ("C05", "Masonry and Blockwork", ["Brick masonry", "Block masonry"]),
    ("C06", "Plaster and Screed", ["Internal plaster", "External plaster", "Screed"]),
    ("C07", "Waterproofing and Insulation", ["Waterproofing", "DPC", "Insulation"]),
    ("C08", "Gypsum, False Ceiling and Partition", ["Gypsum board ceiling", "Tile / grid ceiling", "Drywall partition"]),
    ("C09", "Flooring and Wall Finishes", ["Porcelain / ceramic tiles", "Marble / granite", "Counter tops", "Skirting"]),
    ("C10", "Paint and Decorative Finishes", ["Putty and primer", "Emulsion", "Weather shield"]),
    ("C11", "Doors, Windows and Joinery", ["Doors", "Joinery"]),
    ("C12", "Glass, Aluminium and Façade", ["Aluminium windows", "Glass partitions", "Façade"]),
    ("C13", "Plumbing and Sanitary", ["Water supply", "Drainage", "Sanitary ware"]),
    ("C14", "Electrical Works", ["Containment", "Wiring", "Power cable", "Distribution", "Lighting", "Earthing"]),
    ("C15", "HVAC and Mechanical", ["Ductwork", "Equipment"]),
    ("C16", "Fire Fighting and Fire Alarm", ["Piping", "Sprinklers", "Fire alarm"]),
    ("C17", "External Development and Infrastructure", ["External drainage", "External works"]),
    ("C18", "Road Works and Landscaping", ["Paving", "Landscaping"]),
    ("C19", "Miscellaneous and Specialized Works", ["Metal work", "Other"]),
]

# first match wins; keys: code / cat / sub / desc (case-insensitive regexes), c = category, s = sub ("$sub" keeps own)
RULES = [
    {"code": r"^EX-100$", "c": "C01", "s": "Site preparation"},
    {"code": r"^EX-14", "c": "C01", "s": "Anti-termite"},
    {"code": r"^EX-", "c": "C01", "s": "Earthwork"},
    {"code": r"^(ST-|QS-STL)", "c": "C04", "s": "Reinforcement"},
    {"code": r"^(FW-|QS-FW)", "c": "C02", "s": "Formwork"},
    {"code": r"^WP-410", "c": "C07", "s": "DPC"},
    {"code": r"^(WP-|QS-WP)", "c": "C07", "s": "Waterproofing"},
    {"code": r"^(SC-|QS-SCR)", "c": "C06", "s": "Screed"},
    {"code": r"^PCC-", "c": "C03", "s": "PCC"},
    {"code": r"^RCC-RMC-", "c": "C03", "s": "RCC — ready-mix"},
    {"code": r"^RCC-DM-", "c": "C03", "s": "RCC — lab design mix"},
    {"code": r"^RCC-", "c": "C03", "s": "RCC — nominal mix"},
    {"code": r"^BLK-", "c": "C05", "s": "Block masonry"},
    {"code": r"^BRK-", "c": "C05", "s": "Brick masonry"},
    {"code": r"^PLS-E", "c": "C06", "s": "External plaster"},
    {"code": r"^PLS-I", "c": "C06", "s": "Internal plaster"},
    {"code": r"^(FN-50[05]|QS-TIL)", "c": "C09", "s": "Porcelain / ceramic tiles"},
    {"code": r"^FN-510", "c": "C09", "s": "Marble / granite"},
    {"code": r"^FN-515", "c": "C09", "s": "Counter tops"},
    {"code": r"^FN-520", "c": "C09", "s": "Skirting"},
    {"code": r"^FN-530", "c": "C10", "s": "Putty and primer"},
    {"code": r"^FN-535", "c": "C10", "s": "Emulsion"},
    {"code": r"^FN-540", "c": "C10", "s": "Weather shield"},
    {"code": r"^(FN-550|QS-GYP-C)", "c": "C08", "s": "Gypsum board ceiling"},
    {"code": r"^FN-555", "c": "C08", "s": "Tile / grid ceiling"},
    {"code": r"^QS-GYP-P", "c": "C08", "s": "Drywall partition"},
    {"code": r"^FN-560", "c": "C11", "s": "Doors"},
    {"code": r"^FN-570", "c": "C12", "s": "Aluminium windows"},
    {"code": r"^FN-575", "c": "C12", "s": "Glass partitions"},
    {"code": r"^FN-580", "c": "C19", "s": "Metal work"},
    {"code": r"^EW-950", "c": "C18", "s": "Paving"},
    {"code": r"^EW-96", "c": "C17", "s": "External drainage"},
    {"cat": r"^ELV$", "sub": r"fire alarm", "c": "C16", "s": "Fire alarm"},
    {"cat": r"^ELV$", "c": "C14", "s": "ELV — $sub"},
    {"cat": r"^Electrical$", "c": "C14", "s": "$sub"},
    {"cat": r"^Plumbing$", "c": "C13", "s": "$sub"},
    {"cat": r"^HVAC$", "c": "C15", "s": "$sub"},
    {"cat": r"^Fire Fighting$", "c": "C16", "s": "$sub"},
    {"cat": r"^External Works$", "c": "C17", "s": "External works"},
    {"desc": r"gypsum|false ceiling|drywall", "c": "C08", "s": "$sub"},
    {"desc": r"\btile|marble|granite", "c": "C09", "s": "$sub"},
    {"desc": r"paint|emulsion|putty", "c": "C10", "s": "$sub"},
    {"desc": r"door|wardrobe|cabinet|joinery", "c": "C11", "s": "$sub"},
    {"desc": r"alumin|glass|glazing|fa[cç]ade", "c": "C12", "s": "$sub"},
    {"desc": r"plaster|screed", "c": "C06", "s": "$sub"},
    {"desc": r"waterproof|membrane|insulation", "c": "C07", "s": "$sub"},
    {"desc": r"excavat|backfill|earth ?work", "c": "C01", "s": "$sub"},
    {"desc": r"masonry|brick|block", "c": "C05", "s": "$sub"},
    {"desc": r"concrete|pcc|rcc", "c": "C03", "s": "$sub"},
    {"desc": r"steel|reinforce|rebar", "c": "C04", "s": "$sub"},
    {"cat": r"^Civil / Structural$", "c": "C02", "s": "General"},
    {"cat": r"^Finishing$", "c": "C19", "s": "Other"},
    {"c": "C19", "s": "Other"},
]


# ------------------------------------------------------------------ rate lines
def rate_lines(g):
    Q, P = "Quadrangle", "Phoenix"
    L = [
        # gypsum ceiling / partition — no dated Pakistan price found for these (26-Sep-2026)
        zero("QE-GYP-BD12", "Gypsum board 12.5 mm (1/2\"), 8 ft × 4 ft = 32 Sft sheet, tapered edge", "Sheet",
             "Web search 26-Sep-2026 found only installed ceiling rates (Rs 220–350/Sft plain gypsum ceiling, "
             "elegantdesignpk.com 2026; 100–125/Sft material + 50–80/Sft installation, finishes.pk / aecinteriors.com.pk "
             "2026) and an undated 110/Sft 12 mm United Gypsum ceiling post — no board-only price. Supplier sites were "
             "not reachable from the build environment. Enter a quotation per sheet."),
        zero("QE-GYP-MC", "GI main (carrying) channel for suspended ceiling, approved gauge", "Rft",
             "No Pakistan price found (web search 26-Sep-2026 returned India / Philippines prices only)."),
        zero("QE-GYP-FC", "GI furring channel for suspended ceiling, approved gauge", "Rft",
             "No Pakistan price found (web search 26-Sep-2026)."),
        zero("QE-GYP-WA", "GI perimeter / wall angle for suspended ceiling", "Rft",
             "No Pakistan price found (web search 26-Sep-2026)."),
        zero("QE-GYP-CON", "Main-to-furring channel connector clip", "Nos", "No Pakistan price found."),
        zero("QE-GYP-HNG", "Hanger bracket / soffit cleat with nut (per hanger point)", "Nos", "No Pakistan price found."),
        zero("QE-GYP-TAPE", "Gypsum joint tape (paper / fibre mesh)", "Rft",
             "No Pakistan price found; web search 26-Sep-2026 returned India prices only (not usable)."),
        zero("QE-GYP-JC", "Gypsum jointing compound", "Kg",
             "No Pakistan price found; web search 26-Sep-2026 returned India prices only (not usable)."),
        zero("QE-GYP-STUD", "GI stud for drywall partition, approved width and gauge", "Rft", "No Pakistan price found."),
        zero("QE-GYP-TRK", "GI track (floor / ceiling runner) for drywall partition", "Rft", "No Pakistan price found."),
        zero("QE-INS-RW", "Mineral wool insulation infill for partitions, approved density and thickness", "Sft",
             "No Pakistan price found."),
        zero("QE-TSPACER", "Tile spacer (per piece)", "Nos",
             "Quadrangle GRN RCP-2632, 23-Jul-2025 (Faizan Traders) shows 'Tile Spacer 2mm' at 168 per pack but the pack count is not "
             "recorded, so no per-piece rate can be derived."),
        g.line(P, 'Self Tapping Screw 1-1/2" (8 No.)'),
        g.line(Q, "Drop in Anchor 8mm"),
        g.line(Q, "drop in anchor 10mm"),
        g.line(Q, "threaded rod 8mm"),
        g.line(Q, "Threaded Rod 10mm"),
        # paint
        g.per("QE-PNT-PRM", "Water-based interior wall primer (Berger), per litre", "Ltr",
              Q, "Water Based Primer 18 Ltr Interior", 18, "Ltr"),
        g.per("QE-PNT-PUT", "Wall putty (Berger), per kg", "Kg", Q, "Wall Putty - 30 Kg Bucket", 30, "kg"),
        {"code": "QE-PNT-EMU", "kind": "M", "name": "Matt emulsion paint, standard grade, per litre", "unit": "Ltr",
         "rate": 1300, "loc": "Lahore", "date": "2026-07-02", "vs": "I",
         "src": "nerdbot.com 'Paint Prices in Pakistan 2026', 02-Jul-2026 — emulsion 1,300–2,500 per litre, premium "
                "16–20 L drums 15,000–30,000 (web search 26-Sep-2026; page itself not reachable). icons.com.pk "
                "07-Jun-2026 gave 850–1,500/Ltr. 1,300 = where both ranges meet; set per approved brand and shade"},
        {"code": "QE-PNT-WS", "kind": "M", "name": "Weather shield exterior emulsion, per litre", "unit": "Ltr",
         "rate": 2000, "loc": "Lahore", "date": "2026-06-07", "vs": "A",
         "src": "ASSUMPTION — icons.com.pk paint prices, 07-Jun-2026 — weather shield range (web search 23-Sep-2026), "
                "taken at 2,000/Ltr; no named product price. Berger Weather Pro listed 4,485–17,865 by pack size "
                "(paintlo.com, pack sizes not shown). Replace with a dealer quotation"},
        # tiles
        g.line(Q, 'Bathroom Wall Tile OR 612040 Karara White Gloss 24"x48"'),
        g.line(Q, 'Bathroom Floor Tile IM 612002 Grey Matt 24"x48"'),
        # formwork
        {"code": "QE-PLY-SH", "kind": "M", "name": "Shuttering plywood 12 mm (1/2\"), 8 ft × 4 ft sheet", "unit": "Sheet",
         "rate": 4000, "loc": "Lahore", "date": "2026-08-09", "vs": "I",
         "src": "icons.com.pk, 09-Aug-2026 — 12 mm ply 3,500–4,500 per 8×4 sheet (web search 23-Sep-2026, same basis "
                "as the PLY line); mid-range 4,000"},
        {"code": "QE-TIMB-CFT", "kind": "M", "name": "Shuttering timber / battens (kail / partal), per cft", "unit": "Cft",
         "rate": 3000, "loc": "Lahore", "date": "", "vs": "A",
         "src": f"{NOSRC}. 3,000/cft is the figure the TIMB line was built on (23-Sep-2026); no dated Lahore timber rate found"},
        # plumbing — PPRC PN20 (Quadrangle GRNs)
        g.line(Q, "PPRC Pipe PN 20 25mm"), g.line(Q, "PPRC Elbow 90 Degree 25mm"),
        g.line(Q, "PPRC Tee 25mm"), g.line(Q, "PPRC Socket 25mm"),
        g.line(Q, "PPRC Pipe PN 20 32mm"), g.line(Q, "PPRC Elbow 90 Degree 32mm"),
        g.line(Q, "PPRC Tee 32mm"), g.line(Q, "PPRC Socket 32mm"),
        g.line(Q, "PPRC Pipe PN 20 40mm"), g.line(Q, "PPRC Elbow 90 Degree 40mm"),
        g.line(Q, "PPRC Tee 40mm"), g.line(Q, "PPRC Socket 40mm"),
        g.line(Q, "Isophonic Pipe Clamp M-28"), g.line(Q, "Isophonic Pipe Clamp M-35"),
        g.line(Q, "Isophonic Pipe Clamp M-40"),
        # uPVC Class B drainage
        g.line(Q, 'UPVC Pipe Class-B 4"'), g.line(Q, 'UPVC Elbow 90 Degree Class-B 4"'),
        g.line(Q, 'UPVC Yee Tee Class-B 4"'), g.line(Q, 'UPVC Socket Class-B 4"'), g.line(Q, 'Isophonic Clamps 4"'),
        g.line(Q, 'UPVC Pipe Class-B 2"'), g.line(Q, 'UPVC Elbow 90 Degree Class-B 2"'),
        g.line(Q, 'UPVC Yee tee Class-B 2"'), g.line(Q, 'UPVC Socket Class-B 2"'), g.line(Q, 'Isophonic Clamps 2"'),
        g.line(Q, "Gluing PVC Solution (Solvent Cement) 500ML"),
        # electrical
        g.line(Q, 'Pvc Pipe 3/4"'), g.line(Q, 'Pvc Bend 3/4"'),
        g.line(Q, 'GI Perforated Cable Tray 14 SWG 12"x3"'),
        g.line(Q, _coupling(g)),
        g.line(Q, 'GI C Channel 27x18 mm (Cable Tray 12"x3")'),
        g.line(Q, "bend 90D 12\" x 3\""),
        g.line(Q, "GI Cable Tray Equal Tee 12\"x3\""),
        g.line(Q, "Gland for Cable 4C x 50 sq.mm"),
        g.line(Q, "Lugs 35 mm.sq (O type)"),
    ]
    out = {}
    for r in L:
        if r["code"] in out:
            sys.exit(f"duplicate rate line {r['code']}")
        out[r["code"]] = r
    return out


def _coupling(g):
    hits = [it for it in g.items if it["site"] == "Quadrangle" and it["desc"].startswith("GI Joint/Coupling plates with mushroom")]
    if len(hits) != 1:
        sys.exit("coupling plate GRN not found exactly once")
    return hits[0]["desc"]


def code_of(g, site, desc):
    return g.find(site, desc)["db"]


# ------------------------------------------------------------------ fixes, conversions, items
def fixes(as_of):
    return [
        {"code": "NAILS", "from": [[400, "2026-09-23"]],
         "to": {"rate": 715, "date": "2026-05-21", "vs": "V", "name": "Nails — MS steel wire nails 2\"",
                "src": "Phoenix GRN RCP-273, 21-May-2026 — Taha International, MS Steel Nail 2\"×12 no, 715 per kg. "
                       f"Replaces the 400/kg assumption (QS engine audit, {dmy(as_of.isoformat())})"}},
    ]


def build(g, as_of):
    Q = "Quadrangle"
    c = lambda d: code_of(g, Q, d)
    screw = code_of(g, "Phoenix", 'Self Tapping Screw 1-1/2" (8 No.)')
    anc8, anc10 = c("Drop in Anchor 8mm"), c("drop in anchor 10mm")
    rod8, rod10 = c("threaded rod 8mm"), c("Threaded Rod 10mm")
    ppr = {s: {"pipe": c(f"PPRC Pipe PN 20 {s}mm"), "elbow": c(f"PPRC Elbow 90 Degree {s}mm"),
               "tee": c(f"PPRC Tee {s}mm"), "sock": c(f"PPRC Socket {s}mm"),
               "clamp": c({"25": "Isophonic Pipe Clamp M-28", "32": "Isophonic Pipe Clamp M-35",
                           "40": "Isophonic Pipe Clamp M-40"}[s])} for s in ("25", "32", "40")}
    upvc = {s: {"pipe": c(f'UPVC Pipe Class-B {s}"'), "elbow": c(f'UPVC Elbow 90 Degree Class-B {s}"'),
                "tee": c({"4": 'UPVC Yee Tee Class-B 4"', "2": 'UPVC Yee tee Class-B 2"'}[s]),
                "sock": c(f'UPVC Socket Class-B {s}"'), "clamp": c(f'Isophonic Clamps {s}"')} for s in ("4", "2")}
    solvent = c("Gluing PVC Solution (Solvent Cement) 500ML")
    gyp = {"board": "QE-GYP-BD12", "mc": "QE-GYP-MC", "fc": "QE-GYP-FC", "wa": "QE-GYP-WA", "con": "QE-GYP-CON",
           "hng": "QE-GYP-HNG", "rod": rod8, "anc": anc8, "scr": screw, "tape": "QE-GYP-TAPE", "jc": "QE-GYP-JC"}
    tray = {"tray": c('GI Perforated Cable Tray 14 SWG 12"x3"'), "cpl": c(_coupling(g)),
            "ch": c('GI C Channel 27x18 mm (Cable Tray 12"x3")'), "bend": c('bend 90D 12" x 3"'),
            "tee": c('GI Cable Tray Equal Tee 12"x3"'), "rod": rod10, "anc": anc10}
    cable = {"cable": "CABLE-LT", "gland": c("Gland for Cable 4C x 50 sq.mm"), "lug": c("Lugs 35 mm.sq (O type)")}
    cond = {"pipe": c('Pvc Pipe 3/4"'), "bend": c('Pvc Bend 3/4"')}
    wall_t = c('Bathroom Wall Tile OR 612040 Karara White Gloss 24"x48"')
    floor_t = c('Bathroom Floor Tile IM 612002 Grey Matt 24"x48"')

    fw = lambda carp, help_, props, nails, oil: {
        "k": "qe-fw", "p": {"ply": "QE-PLY-SH", "plyL": 8, "plyW": 4, "plyUses": 6, "plyWast": 10,
                            "timb": "QE-TIMB-CFT", "timbCft": 0.03, "timbUses": 8, "props": "PROPS", "propsQty": props,
                            "oil": "MOULD", "oilCov": round(1 / oil), "nails": "NAILS", "nailKg": nails,
                            "lc": carp, "lh": help_}}
    conv = [
        {"id": "FN-550", "guard": [["GYPBD", 1]],
         "gen": {"k": "qe-gypc", "p": dict(gyp, bL=8, bW=4, bWast=5, mcSp=4, fcSp=2, hSp=4, drop=2, rmL=20, rmW=15,
                                          pWast=5, scrIn=8, sWast=10, tWast=10, jcKg=0.028, lc=0.024, lh=0.02)},
         "why": "GYPBD was an installed ceiling rate (200/Sft) entered as a material; board, framing, hangers, "
                "screws, tape and compound are now calculated from spacing and sheet size"},
        {"id": "FN-500", "guard": [["TILE-POR", 1.05], ["TILEADH", 0.6], ["GROUT", 0.08]],
         "gen": {"k": "qe-tile", "p": {"tile": "TILE-POR", "tL": 24, "tW": 24, "jw": 0.0625, "jd": 0.375, "tWast": 5,
                                       "bed": "adh", "adh": "TILEADH", "adhKg": 0.45, "gr": "GROUT", "grDen": 48,
                                       "gWast": 10, "spc": "QE-TSPACER", "lc": 0.022, "lh": 0.018, "cut": 0.003}},
         "why": "grout 0.08 kg/Sft was about 10× the joint volume of 24\"×24\" tiles with 1/16\" joints; adhesive and "
                "grout are now taken from tile size, joint width / depth and the TDS consumption"},
        {"id": "FN-505", "guard": [["TILE-CER", 1.05], ["TILEADH", 0.55], ["GROUT", 0.08]],
         "gen": {"k": "qe-tile", "p": {"tile": "TILE-CER", "tL": 24, "tW": 12, "jw": 0.0625, "jd": 0.3125, "tWast": 7,
                                       "bed": "adh", "adh": "TILEADH", "adhKg": 0.4, "gr": "GROUT", "grDen": 48,
                                       "gWast": 10, "spc": "QE-TSPACER", "lc": 0.026, "lh": 0.02, "cut": 0.003}},
         "why": "grout 0.08 kg/Sft overstated; now calculated from joint geometry"},
        {"id": "FN-530", "guard": [["PUTTY", 1]],
         "gen": {"k": "qe-paint", "p": {"coats": [{"ref": "QE-PNT-PUT", "n": 2, "cov": 0, "kg": 0.045, "lbl": "Wall putty"}],
                                        "wast": 5, "lp": 0.006, "lh": 0.004, "cr": 0}},
         "why": "PUTTY was a per-Sft composite; putty is now priced per kg from the Berger 30 kg bucket GRN"},
        {"id": "FN-535", "guard": [["PRIMER", 1], ["EMUL", 1]],
         "gen": {"k": "qe-paint", "p": {"coats": [{"ref": "QE-PNT-PRM", "n": 1, "cov": 100, "lbl": "Primer / sealer"},
                                                  {"ref": "QE-PNT-EMU", "n": 3, "cov": 110, "lbl": "Emulsion"}],
                                        "wast": 5, "lp": 0.007, "lh": 0.004, "cr": 0}},
         "why": "PRIMER and EMUL were per-Sft composites; paint is now priced per litre × coats ÷ coverage"},
        {"id": "FN-540", "guard": [["PRIMER", 1], ["WSHIELD", 1]],
         "gen": {"k": "qe-paint", "p": {"coats": [{"ref": "QE-PNT-PRM", "n": 1, "cov": 100, "lbl": "Primer / sealer"},
                                                  {"ref": "QE-PNT-WS", "n": 3, "cov": 90, "lbl": "Weather shield"}],
                                        "wast": 5, "lp": 0.009, "lh": 0.005, "cr": 0.0015}},
         "why": "PRIMER and WSHIELD were per-Sft composites"},
        {"id": "PL-700", "guard": [["PPRC", 1.05]],
         "gen": {"k": "qe-pipe", "p": dict(ppr["25"], sys="PPRC PN20 25 mm", len=13.12, pWast=5, elbow10=2, tee10=1,
                                           sock10=1, clampSp=4, joint="", jointPer=0, lp=0.025, lh=0.02)},
         "why": "PPRC was a composite 'pipe with fittings' at 200/Rft; pipe, elbows, tees, sockets and clamps are now "
                "counted per 10 Rft and priced from Quadrangle GRNs"},
        {"id": "PL-710", "guard": [["UPVC-D", 1.05]],
         "gen": {"k": "qe-pipe", "p": dict(upvc["4"], sys="uPVC Class B 4\"", len=13.12, pWast=5, elbow10=1, tee10=1,
                                           sock10=0.5, clampSp=4, joint=solvent, jointPer=40, lp=0.022, lh=0.02)},
         "why": "UPVC-D was a composite 'pipe with fittings' at 250/Rft"},
        {"id": "EL-600", "guard": [["COND-PVC", 1.05]],
         "gen": {"k": "qe-cond", "p": dict(cond, pWast=5, bend10=2, lc=0.01, lh=0.01)},
         "why": "COND-PVC was conduit + 20% accessories; conduit and bends are now priced from GRNs"},
        {"id": "EL-650", "guard": [["CTRAY", 1.05]],
         "gen": {"k": "qe-tray", "p": dict(tray, tWast=3, len=8, supSp=5, chLen=1.5, drop=2, bend100=3, tee100=1.5,
                                           lc=0.03, lh=0.03)},
         "why": "CTRAY was tray + 20% supports; tray, couplers, supports, rods and anchors are now counted"},
        {"id": "EL-670", "guard": [["CABLE-LT", 1.03]],
         "gen": {"k": "qe-cable", "p": dict(cable, cWast=3, run=100, cores=4, lc=0.018, lh=0.022)},
         "why": "glands and lugs were not priced; they are now allocated per run"},
        {"id": "SC-420", "guard": [["CEM", 0.0217], ["SAND-CH", 0.1083], ["WATER", 0.008]],
         "gen": {"k": "qe-screed", "p": {"th": 1, "mix": "1:4", "sand": "SAND-CH", "wast": 5, "lc": 0.01, "lh": 0.01}},
         "why": "cement 0.0217 was the cement VOLUME in cft, not bags (÷ 1.25 cft/bag omitted, +25 %); sand 0.1083 was "
                "the whole dry mortar volume, not the 4/5 sand share (+25 %). Correct: 1\"/12 × 1.30 = 0.1083 cft dry; "
                "cement 0.1083 ÷ 5 ÷ 1.25 = 0.01733 bag; sand 0.1083 × 4/5 = 0.08667 cft"},
        {"id": "FW-300", "guard": [["PLY", 1], ["TIMB", 1], ["PROPS", 1], ["MOULD", 0.01], ["NAILS", 0.02]],
         "gen": fw(0.022, 0.02, 1, 0.02, 0.01), "why": "PLY / TIMB were amortised per-Sft lines; sheet price, uses and batten volume are now explicit"},
        {"id": "FW-310", "guard": [["PLY", 1], ["TIMB", 1], ["PROPS", 1], ["MOULD", 0.01], ["NAILS", 0.02]],
         "gen": fw(0.025, 0.024, 1, 0.02, 0.01), "why": "as FW-300"},
        {"id": "FW-320", "guard": [["PLY", 1], ["TIMB", 1], ["PROPS", 1], ["MOULD", 0.01], ["NAILS", 0.02]],
         "gen": fw(0.018, 0.018, 1, 0.02, 0.01), "why": "as FW-300"},
        {"id": "FW-330", "guard": [["PLY", 1], ["TIMB", 1], ["PROPS", 1], ["MOULD", 0.01], ["NAILS", 0.025]],
         "gen": fw(0.024, 0.022, 1, 0.025, 0.01), "why": "as FW-300"},
        {"id": "FW-340", "guard": [["PLY", 1], ["TIMB", 1], ["PROPS", 1], ["MOULD", 0.012], ["NAILS", 0.03]],
         "gen": fw(0.034, 0.03, 1, 0.03, 0.012), "why": "as FW-300"},
        {"id": "FW-350", "guard": [["PLY", 1], ["TIMB", 1], ["MOULD", 0.01], ["NAILS", 0.02]],
         "gen": fw(0.016, 0.016, 0, 0.02, 0.01), "why": "as FW-300"},
    ]
    for cv in conv:
        cv["gen"]["ok"] = False

    item = lambda iid, desc, spec, unit, gen: {"id": iid, "code": iid, "desc": desc, "spec": spec, "unit": unit,
                                               "gen": dict(gen, ok=False)}
    items = [
        item("QS-GYP-P01", "Supply and fix drywall partition, GI studs and tracks, one layer 12.5 mm gypsum board each side, "
             "joints taped and filled, ready for paint", "Studs @ 2 ft c/c, height 10 ft, board 8×4 ft, tracks anchored @ 2 ft",
             "Sft", {"k": "qe-gypp", "p": {"board": "QE-GYP-BD12", "stud": "QE-GYP-STUD", "trk": "QE-GYP-TRK",
                                           "anc": anc8, "scr": screw, "tape": "QE-GYP-TAPE", "jc": "QE-GYP-JC",
                                           "ins": "QE-INS-RW", "insOn": 0, "H": 10, "studSp": 2, "sides": 2, "layers": 1,
                                           "bL": 8, "bW": 4, "bWast": 7, "pWast": 5, "ancSp": 2, "scrIn": 10, "sWast": 10,
                                           "tWast": 10, "jcKg": 0.028, "lc": 0.03, "lh": 0.025}}),
        item("QS-TIL-W2448", "Supply and fix 24\"×48\" glazed wall tile (Karara White Gloss) on tile adhesive, joints "
             "grouted, spacers, cutting and cleaning", "Tile 24\"×48\", 1/16\" joint, adhesive to TDS", "Sft",
             {"k": "qe-tile", "p": {"tile": wall_t, "tL": 48, "tW": 24, "jw": 0.0625, "jd": 0.375, "tWast": 7,
                                    "bed": "adh", "adh": "TILEADH", "adhKg": 0.5, "gr": "GROUT", "grDen": 48, "gWast": 10,
                                    "spc": "QE-TSPACER", "lc": 0.028, "lh": 0.022, "cut": 0.004}}),
        item("QS-TIL-F2448", "Supply and fix 24\"×48\" matt floor tile (Grey Matt) on tile adhesive, joints grouted, "
             "spacers, cutting and cleaning", "Tile 24\"×48\", 1/16\" joint, adhesive to TDS", "Sft",
             {"k": "qe-tile", "p": {"tile": floor_t, "tL": 48, "tW": 24, "jw": 0.0625, "jd": 0.375, "tWast": 5,
                                    "bed": "adh", "adh": "TILEADH", "adhKg": 0.55, "gr": "GROUT", "grDen": 48, "gWast": 10,
                                    "spc": "QE-TSPACER", "lc": 0.024, "lh": 0.02, "cut": 0.004}}),
        item("QS-PPR-32", "Supply, fix and pressure-test PPRC PN20 32 mm pipe with fittings and clamps", "PPRC PN20 32 mm",
             "Rft", {"k": "qe-pipe", "p": dict(ppr["32"], sys="PPRC PN20 32 mm", len=13.12, pWast=5, elbow10=2, tee10=1,
                                               sock10=1, clampSp=4, joint="", jointPer=0, lp=0.028, lh=0.022)}),
        item("QS-PPR-40", "Supply, fix and pressure-test PPRC PN20 40 mm pipe with fittings and clamps", "PPRC PN20 40 mm",
             "Rft", {"k": "qe-pipe", "p": dict(ppr["40"], sys="PPRC PN20 40 mm", len=13.12, pWast=5, elbow10=1.5, tee10=1,
                                               sock10=1, clampSp=4, joint="", jointPer=0, lp=0.032, lh=0.025)}),
        item("QS-UPVC-2", "Supply, fix and test uPVC Class B 2\" drainage pipe with fittings, solvent joints and clamps",
             "uPVC Class B 2\"", "Rft", {"k": "qe-pipe", "p": dict(upvc["2"], sys="uPVC Class B 2\"", len=13.12, pWast=5,
                                                                   elbow10=2, tee10=1, sock10=0.5, clampSp=4, joint=solvent,
                                                                   jointPer=60, lp=0.018, lh=0.016)}),
        item("QS-SCR-2", "Cement sand screed 1:4, 2\" average thickness, laid to levels / falls and cured",
             "Screed 1:4, 2\" thick, dry-volume factor from Settings", "Sft",
             {"k": "qe-screed", "p": {"th": 2, "mix": "1:4", "sand": "SAND-CH", "wast": 5, "lc": 0.014, "lh": 0.014}}),
    ]

    composite = {
        "GYPBD": "installed ceiling rate (board + GI framing) used as a material",
        "MINCEIL": "installed tile + T-grid rate used as a material",
        "EMUL": "3-coat emulsion system per Sft, not a purchase unit",
        "WSHIELD": "3-coat weather shield system per Sft, not a purchase unit",
        "PRIMER": "primer per Sft, not a purchase unit",
        "PUTTY": "putty per Sft, not a purchase unit",
        "DOOR-W": "door shutter per Sft; frame, lipping and finish not itemised",
        "DOOR-HW": "hardware set not itemised (lock, hinges, stopper, handle)",
        "ALU-WIN": "installed aluminium window system per Sft",
        "GLASS-12": "glass + patch fittings per Sft",
        "SS-RAIL": "installed railing per Rft",
        "COND-PVC": "conduit + 20 % accessories",
        "PPRC": "pipe + 30 % fittings",
        "UPVC-D": "pipe + 25 % fittings",
        "CTRAY": "tray + 20 % supports",
        "EARTH": "earthing kit",
        "DB-BOARD": "DB enclosure + MCBs as one price",
        "FIRE-PIPE": "pipe + fittings per Rft",
        "DUCT-GI": "duct + insulation + hangers per Sft",
        "SAN-WC": "WC suite set (pan, cistern, seat, connectors) as one price",
        "SAN-WB": "basin + mixer + waste set as one price",
        "PLY": "plywood amortised per Sft",
        "TIMB": "timber amortised per Sft",
        "PROPS": "props hire per Sft",
    }

    audit = [
        {"id": "FN-510", "guard": [["MARBLE", 1.05], ["CEM", 0.015], ["SAND-CH", 0.075]], "sev": "med",
         "t": "Bed thickness not stated: cement 0.015 bag and sand 0.075 cft per Sft match a 1:4 bed about 7/8\" thick "
              "(t/12 × 1.30 ÷ 5 ÷ 1.25 = 0.015 → t = 0.87\"). The description includes grinding and polishing but no "
              "polishing consumables or machine are priced."},
        {"id": "FN-515", "guard": [["GRANITE", 1.08]], "sev": "med",
         "t": "No fixing adhesive / epoxy, sealant or edge-polishing consumables in the build-up."},
        {"id": "FN-520", "guard": [["MARBLE", 0.36]], "sev": "low",
         "t": "0.36 Sft per Rft = 4\" × 12\" ÷ 144 × 1.08 wastage — correct; no fixing mortar or adhesive priced."},
        {"id": "FN-560", "guard": [["DOOR-W", 1], ["DOOR-HW", 0.055]], "sev": "high",
         "t": "Description includes the frame and finish, but only the shutter (DOOR-W per Sft) and 0.055 hardware set "
              "per Sft (one set per 18.2 Sft) are priced. Frame, architrave, lipping and polish are missing."},
        {"id": "EW-950", "guard": [["SAND-CH", 0.12]], "sev": "high",
         "t": "The paver block itself is not in the build-up — only the 1.44\" sand bed (0.12 cft/Sft). Edge restraint "
              "is also unpriced."},
        {"id": "EW-960", "guard": [], "sev": "high",
         "t": "No materials at all: bricks, mortar, RCC cover, plaster, benching and step irons are missing. Labour only."},
        {"id": "EX-130", "guard": [["SAND-RV", 1.1], ["WATER", 0.02]], "sev": "med",
         "t": "1.10 cft loose sand per cft compacted is low for sand fill (a compaction / bulking factor of about "
              "1.2–1.3 is usual). Confirm from a site trial."},
        {"id": "EL-615", "guard": [["COND-PVC", 26], ["WIRE-CU", 78], ["SWITCH", 1]], "sev": "med",
         "t": "One switch per light point and no back box, conduit bends or connectors. 78 Rft wire = 3 conductors × 26 Rft."},
        {"id": "FW-300", "guard": None, "sev": "low",
         "t": "Props are priced on column sides; column formwork normally uses clamps and push-pull braces, not props."},
    ]
    return conv, items, composite, audit


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--as-of", default=dt.date.today().isoformat(), help="date the build is made (YYYY-MM-DD)")
    a = ap.parse_args()
    as_of = dt.date.fromisoformat(a.as_of)
    html = a.html.read_text(encoding="utf-8")
    g = Grn(html, as_of)
    rates = rate_lines(g)
    conv, items, composite, audit = build(g, as_of)
    refs = set(rates) | {"TILE-POR", "TILE-CER", "TILEADH", "GROUT", "CABLE-LT", "SAND-CH", "PROPS", "MOULD", "NAILS"}
    for cv in conv + items:
        for k, v in cv["gen"]["p"].items():
            if isinstance(v, str) and (v.startswith("GRN-") or v.startswith("QE-")) and v not in refs:
                sys.exit(f"{cv['id']}: parameter {k} points at {v}, which is not a rate line")
    data = {"cats": [{"id": i, "name": n, "subs": s} for i, n, s in CATS], "rules": RULES,
            "rates": sorted(rates.values(), key=lambda r: r["code"]), "fixes": fixes(as_of),
            "conv": conv, "items": items, "composite": composite, "audit": audit}
    body = json.dumps(data, sort_keys=True, ensure_ascii=False)
    data = {"rev": a.as_of + "-" + hashlib.sha1(body.encode()).hexdigest()[:8], "asOf": a.as_of, **data}
    m = BLOCK_RE.search(html)
    prev = {}
    if m:
        old = json.loads(m.group(2))
        prev = dict(old.get("prevRates", {}))
        new = {r["code"]: r for r in data["rates"]}
        for r in old.get("rates", []):
            n = new.get(r["code"])
            if n and (n["rate"], n["date"]) != (r["rate"], r["date"]):
                prev.setdefault(r["code"], [])
                if [r["rate"], r["date"]] not in prev[r["code"]]:
                    prev[r["code"]].append([r["rate"], r["date"]])
    data["prevRates"] = prev
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if m:
        html = BLOCK_RE.sub(lambda mm: mm.group(1) + blob + mm.group(3), html)
    else:
        if ANCHOR not in html:
            sys.exit("anchor for the data block not found")
        html = html.replace(ANCHOR, f'<script type="application/json" id="raQsEngine">{blob}</script>\n' + ANCHOR, 1)
    a.html.write_text(html, encoding="utf-8")
    zero_n = sum(1 for r in data["rates"] if not r["rate"])
    print(f"QS engine data {data['rev']}: {len(data['cats'])} categories, {len(data['rates'])} rate lines "
          f"({zero_n} unpriced), {len(conv)} conversions, {len(items)} new items → {a.html}")


if __name__ == "__main__":
    main()
