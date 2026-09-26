#!/usr/bin/env python3
"""Build the Civil gap-analysis data block of the dashboard (#raCivilData).

    tools/civil_gap_data.py                      # writes zameen-developments/index.html
    tools/civil_gap_data.py --as-of 2026-09-26 --html path/to/index.html

Adds the civil rate analyses the Item Library was missing (grey structure, finishes,
external works and repair: CV-001 ... CV-130, CV-R01 ... CV-R03) and repairs three seed
items (FN-560 door frame, EW-950 paver block, EW-960 manhole materials). Built on
26-Sep-2026 from Sajjad's list "QS_Rate_Analysis_Lahore_2026_All_Missing.txt", checked
line by line (see docs/civil-gap-rate-review.md).

Each item is a full A–H build-up, never a bare lump, wherever the inputs exist:

  materials   quantity × rate line; lines are the library's own (CEM, SAND-CH, BRK-1 …),
              the GRN Price Register (same GRN-<SITE>-<code> as its + Rate DB button),
              or a dated web price (Web search 26-Sep-2026 — site …, status I)
  labour      the Punjab MRS 1st Bi-Annual 2026 labour-only rate for the same operation
              (same MRS-C<ch>-<item>-<line>[-L] codes as the MRS register's + Rate DB
              button, status I), or trade day-rates × output
  composite   where no current material price exists but the MRS prints a composite
              rate for the same item, that composite is used as one line (status I)
  assumption  where nothing dated exists, the figure from Sajjad's benchmark file is kept
              as one line marked "ASSUMPTION — no dated source" (status A), so the item
              shows as Assumed until a quotation replaces it

Rates follow CLAUDE.md: every line names its source and date; no rate is invented.
The dashboard merges this block like the MEP block: missing lines and items are added,
a line or item still at a version listed in prevRates / prevItems is moved to the new
one, anything edited by hand is left alone.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qs_engine_data import Grn, dmy, rs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "zameen-developments" / "index.html"
BLOCK_RE = re.compile(r'(<script type="application/json" id="raCivilData">)(.*?)(</script>)', re.S)
MRS_RE = re.compile(r'<script type="application/json" id="raMrsData">(.*?)</script>', re.S)
ANCHOR = '<script type="application/json" id="calcData">'
NOSRC = "ASSUMPTION — no dated source"
SEARCH = "2026-09-26"                       # date of the web search behind the "Web search" lines
FILE = "Sajjad's benchmark file QS_Rate_Analysis_Lahore_2026_All_Missing, 26-Sep-2026"

# library constants (raDefaults): dry-volume factors and cement bag volume
DRY_C, DRY_M, BAG = 1.54, 1.3, 1.25
# 9" × 4.5" × 3" brick with 1/4" joint (raGenBrick)
BRICK_CFT = (9.25 * 4.75 * 3.25) / 1728
BRICK_VOL = 9 * 4.5 * 3 / 1728


def r5(v):
    return round(v + 0.0, 6)


def fmt(v):
    s = f"{v:.5f}".rstrip("0").rstrip(".")
    return s if s else "0"


# --------------------------------------------------------------------------- MRS
class Mrs:
    """Lines of the Punjab MRS register (#raMrsData), coded like its + Rate DB button."""

    def __init__(self, html):
        m = MRS_RE.search(html)
        if not m:
            sys.exit("MRS register block (#raMrsData) not found")
        d = json.loads(m.group(1))
        self.meta = d
        self.ch = {c[0]: c[1] for c in d["chapters"]}
        self.items = {}
        for a in d["items"]:
            it = {"ch": a[0], "item": a[1], "line": a[2], "page": a[3], "head": d["heads"][a[4]], "path": a[5],
                  "mrsUnit": a[6], "unit": a[7], "k": a[8], "labP": a[9], "compP": a[10], "xc": a[11] or 0,
                  "xnote": a[12] or ""}
            it["code"] = f"MRS-C{it['ch']}-{it['item']}-{it['line']}"
            it["ref"] = f"Ch.{it['ch']} " + (f"section on p.{it['item'][1:]}" if re.match(r"^P\d", str(it["item"]))
                                             else f"item {it['item']}") + f", line {it['line']}"
            self.items[it["code"]] = it

    def edition(self):
        return f"Punjab MRS {self.meta['edition']} ({self.meta['district']})"

    def line(self, key, which="lab"):
        it = self.items.get("MRS-" + key)
        if not it:
            sys.exit(f"MRS line {key} not found")
        v = it["labP"] if which == "lab" else it["compP"]
        if v is None:
            sys.exit(f"MRS line {key} has no {which} rate")
        d = self.meta
        kind = "composite " if which != "lab" else (
            "labour rate (MRS gives no composite) " if it["compP"] is None else "labour share ")
        per = re.sub(r"^(per|p)\.?\s*", "", it["mrsUnit"], flags=re.I)
        src = (f"{self.edition()}, {dmy(d['from'])} — {it['ref']} ({self.ch[it['ch']]}), p.{it['page']}; "
               f"{kind}{v:,.2f} per {per} as printed"
               + (f", converted to per {it['unit']}" if it["k"] != 1 else "")
               + f"; valid {dmy(d['from'])} to {dmy(d['to'])} — edition lapsed, reconfirm before use")
        if it["xc"] == -1:
            src += f". MRS British and metric figures disagree for this line — verify on p.{it['page']}"
        code = it["code"] + ("-L" if which == "lab" and it["compP"] is not None else "")
        return {"code": code, "kind": "L" if which == "lab" else "M",
                "name": ((it["head"] + " ") if it["head"] else "") + it["path"], "unit": it["unit"],
                "rate": round(v * it["k"] + 1e-12, 4), "loc": d["district"], "src": src, "date": d["from"], "vs": "I"}


# --------------------------------------------------------------------------- build context
class Ctx:
    def __init__(self, html, as_of):
        self.grn = Grn(html, as_of)
        self.mrs = Mrs(html)
        self.rates = {}
        self.items = []

    def add(self, line):
        old = self.rates.get(line["code"])
        if old and old != line:
            sys.exit(f"rate line {line['code']} defined twice with different content")
        self.rates[line["code"]] = line
        return line["code"]

    # line makers — each returns the code
    def M(self, key, which="lab"):
        return self.add(self.mrs.line(key, which))

    def G(self, site, desc, unit=None):
        return self.add(self.grn.line(site, desc, unit))

    def Gper(self, code, name, unit, site, desc, content, cunit):
        return self.add(self.grn.per(code, name, unit, site, desc, content, cunit))

    def W(self, code, kind, name, unit, rate, evidence, vs="I"):
        """A dated web price found in the 26-Sep-2026 search (site and figures in the remarks)."""
        return self.add({"code": code, "kind": kind, "name": name, "unit": unit, "rate": rate, "loc": "Lahore",
                         "src": f"Web search {dmy(SEARCH)} — {evidence}", "date": SEARCH, "vs": vs})

    def A(self, code, kind, name, unit, rate, evidence):
        """No dated source: Sajjad's benchmark figure kept as an assumption (or 0 when there is none)."""
        return self.add({"code": code, "kind": kind, "name": name, "unit": unit, "rate": rate, "loc": "Lahore",
                         "src": f"{NOSRC}. {evidence}", "date": "", "vs": "A"})

    def item(self, code, qc, qs, desc, spec, unit, M=(), L=(), P=(), wast=5, note="", cat=None):
        legacy = cat or {"C01": "Civil / Structural", "C02": "Civil / Structural", "C03": "Civil / Structural",
                         "C04": "Civil / Structural", "C05": "Civil / Structural", "C06": "Finishing",
                         "C07": "Civil / Structural", "C08": "Finishing", "C09": "Finishing", "C10": "Finishing",
                         "C11": "Finishing", "C12": "Finishing", "C13": "Plumbing", "C17": "External Works",
                         "C18": "External Works", "C19": "Miscellaneous"}[qc]
        for rows in (M, L, P):
            for r in rows:
                if r["ref"] not in self.rates and r["ref"] not in LIB:
                    sys.exit(f"{code}: rate line {r['ref']} is neither new nor a library line")
        self.items.append({"id": code, "code": code, "cat": legacy, "sub": qs, "qc": qc, "qs": qs, "desc": desc,
                           "spec": spec, "unit": unit, "M": list(M), "L": list(L), "P": list(P), "wast": wast,
                           "oh": 8, "prof": 10, "acc": 0, "trans": 0, "gen": None, "note": note})


def row(ref, qty, note=""):
    """A build-up row; qty is a number or a working string evaluated here ("0.125*1.54/7/1.25")."""
    if isinstance(qty, str):
        v = eval(qty, {"__builtins__": {}}, {})  # noqa: S307 — literal arithmetic written in this file
        w = qty.replace("*", " × ").replace("/", " ÷ ")
        note = (note + ": " if note else "") + f"{w} = {fmt(v)}"
        qty = v
    r = {"ref": ref, "qty": r5(qty)}
    if note:
        r["note"] = note
    return r


# library lines referenced by code (checked to exist in the page by the tests)
LIB = {"CEM", "SAND-CH", "SAND-RV", "CRSH-SG", "GRAVEL-SB", "WATER", "STL60", "BWIRE", "BRK-1", "BRK-2", "RMC-LEAN",
       "RMC-4000", "ADMIX-WP", "SBR", "WSTOP", "SEALANT", "WPROOF", "MARBLE", "TILE-POR", "TILEADH", "GROUT",
       "DOOR-HW", "L-MASON", "L-OPER", "L-PLMASON", "L-HELPER", "L-CARP", "L-TILE", "L-PAINT", "P-MIXER", "P-VIBR", "P-COMP",
       "P-PUMP", "P-CRADLE", "P-CUTTER", "QE-PLY-SH", "QE-TIMB-CFT", "PROPS", "MOULD", "NAILS", "DOOR-W",
       "GRN-PHO-MEP-100089"}


def conc(mix, cft, sand="SAND-CH", agg="CRSH-SG", what="concrete"):
    """Nominal-mix concrete materials for `cft` of wet concrete (raGenConc)."""
    p = [float(x) for x in mix.split(":")]
    n = sum(p)
    return [row("CEM", f"{cft}*{DRY_C}*{fmt(p[0])}/{fmt(n)}/{BAG}", f"{what} {fmt(cft)} cft × dry {DRY_C} × cement share ÷ cft per bag"),
            row(sand, f"{cft}*{DRY_C}*{fmt(p[1])}/{fmt(n)}", f"{what} × dry × sand share"),
            row(agg, f"{cft}*{DRY_C}*{fmt(p[2])}/{fmt(n)}", f"{what} × dry × crush share")]


def mortar(ratio, wet, sand="SAND-CH", what="mortar"):
    """Cement-sand mortar materials for `wet` cft of mortar (dry factor 1.3, as the library)."""
    c, s = [float(x) for x in ratio.split(":")]
    n = c + s
    return [row("CEM", f"{fmt(wet)}*{DRY_M}*{fmt(c)}/{fmt(n)}/{BAG}", f"{what} {fmt(wet)} cft wet × dry {DRY_M} × cement share ÷ cft per bag"),
            row(sand, f"{fmt(wet)}*{DRY_M}*{fmt(s)}/{fmt(n)}", f"{what} × dry × sand share")]


def brick_cft():
    """Bricks and wet mortar in 1 cft of brickwork (9"×4½"×3" brick, ¼" joint — raGenBrick)."""
    n = 1 / BRICK_CFT
    return n, 1 - n * BRICK_VOL


def file_note(rate, unit, status, extra=""):
    return f"{FILE}: PKR {rate:,} / {unit} ({status}). " + extra


# =========================================================================== items
def build(c):
    X = c  # shorthand
    nb, mw = brick_cft()

    # ---------------- rate lines that are not MRS / GRN / library -----------------------------
    X.add({"code": "L-HELPER", "kind": "L", "name": "Helper / unskilled labourer", "unit": "Day", "rate": 1538,
           "loc": "Lahore",
           "src": "Punjab Minimum Wages notification, 01-May-2026 — unskilled adult worker PKR 40,000 per month "
                  "÷ 26 working days = 1,538.46 per day (statutory floor; found by web search 26-Sep-2026, "
                  "legalpk.com / labourlawhelp.com / SGCMS regulatory updates). Replaces the 1,300 assumption, which "
                  "was below the legal minimum", "date": "2026-05-01", "vs": "I"})
    X.add({"code": "BRK-2", "kind": "M", "name": "Brick — 2nd class", "unit": "Nos", "rate": 12.5, "loc": "Lahore",
           "src": f"Web search {dmy(SEARCH)} — Lahore B-class bricks PKR 11,000–14,000 per 1,000, September 2026 "
                  "(themsquare.com.pk / woodenboxtrading.com; one Lahore list gives 11,500); mid 12,500 ÷ 1,000",
           "date": SEARCH, "vs": "I"})
    bit = X.W("BITUMEN", "M", "Bitumen 60/70 penetration grade, bulk / drum", "Kg", 197.5,
              "60/70 bitumen PKR 185,000–210,000 per ton in Pakistan (lakhwa.com, 2026); mid 197,500 ÷ 1,000 kg")
    fab = X.W("BRK-FLYASH", "M", "Fly-ash brick 9\"×4½\"×3\"", "Nos", 15.5,
              "fly-ash bricks Rs 13–18 each (pricedata.pk / brieflyshort.com, 2026; priceinfo.pk June-2026 gives "
              "12–17); mid 15.5")
    dist = X.W("DISTEMPER", "M", "Oil-bound / emulsion distemper, 20 L bucket, per litre", "Ltr", 282.5,
               "distemper 20 L bucket Rs 4,800–6,500 (berger.com.pk distemper guide / paintshop.pk, 2026); "
               "mid 5,650 ÷ 20 L")
    paver = X.W("PAVER-60", "M", "Concrete paver block (tuff tile) 2⅜\" thick, 7000 psi", "Sft", 150,
                "Lahore tuff tiles PKR 150–190 per Sft coloured, plain grey slightly lower (priceit.pk, 06-May-2026; "
                "niazibricks.com.pk); bottom of the coloured band used")
    grass = X.W("GRASS-DHAKA", "M", "Fine Dhaka lawn grass", "Sft", 9,
                "fine Dhaka grass PKR 8–10 per Sft (zameen.com blog, lawn grass types in Pakistan); mid 9")
    spc_s = X.W("SPC-SUP", "M", "SPC vinyl flooring plank, standard grade, with underlay", "Sft", 365,
                "Lahore standard SPC PKR 280–450 per Sft, premium 450–650 (eurospcflooring.com, Lahore cost "
                "breakdown 2026); standard mid 365")
    spc_i = X.W("SPC-INST", "L", "SPC / laminate floor installation, contractor rate", "Sft", 100,
                "floor contractor installation PKR 50–150 per Sft in Lahore (eurospcflooring.com, 2026); mid 100")
    lam_s = X.W("LAM-SUP", "M", "Laminate flooring 5/16\" HDF, AC3, with underlay", "Sft", 350,
                "laminate PKR 200–500+ per Sft by thickness and origin (cdcdevelopers.com.pk / milano.pk, 2026); "
                "mid 350")
    lam_i = X.W("LAM-INST", "L", "Laminate floor installation, contractor rate", "Sft", 110,
                "laminate installation in Lahore PKR 70–150 per Sft (milano.pk / cdcdevelopers.com.pk, 2026); "
                "mid 110")
    upvc_w = X.W("UPVC-WIN", "M", "uPVC sliding window, single glazed, supplied and installed", "Sft", 2850,
                 "Lahore uPVC sliding windows Rs 2,300–3,400 per Sft (almunir.pk / almunirwindows.com uPVC price "
                 "2026); mid 2,850 — installed rate (composite)")
    alu_d = X.W("ALU-DOOR", "M", "Aluminium sliding door, powder coated, glazed, supplied and installed", "Sft", 1400,
                "Lahore aluminium doors: basic 500–800, sliding 1,200–1,600, custom glass up to 2,000 per Sft "
                "(hocmaterial.com, aluminium doors in Lahore); sliding mid 1,400 — installed rate (composite)")
    rail = X.W("GLASS-RAIL", "M", "Toughened glass balustrade ½\" with fittings, supplied and installed", "Rft", 6000,
               "Lahore staircase glass railing PKR 3,500–8,500 per Rft by glass type and system "
               "(greenglassdesigner.com, 2026); mid 6,000 — installed rate (composite)")
    shower = X.W("SHOWER-ENC", "M", "Framed glass shower enclosure, standard size, supplied and installed", "Nos",
                 36500, "Lahore framed single-sliding standard enclosure Rs 28,000–45,000 (ahmadglass.online, "
                 "shower enclosure cost Lahore 2026); mid 36,500 — installed rate (composite)")
    pop = X.W("POP-CEIL", "M", "Plain POP false ceiling, supplied and installed", "Sft", 150,
              "plain POP ceiling Rs 150 per Sft, designed/cove Rs 220 (elegantdesignpk.com, false ceiling rates "
              "Rawalpindi & Islamabad 2026 — nearest published; no Lahore figure found) — installed rate (composite)")
    pvc = X.W("PVC-CEIL", "M", "PVC panel ceiling, supplied and installed with trims", "Sft", 117,
              "Lahore PVC ceiling PKR 18,000–24,000 for a 12×15 ft room (180 Sft) installed "
              "(advancelam.com / finishes.pk PVC panels, 2026) = 100–133 per Sft; mid 117 — installed rate (composite)")
    epx = X.W("EPOXY-FLR", "M", "Epoxy floor coating, basic 2-coat, supplied and applied", "Sft", 200,
              "basic epoxy coating PKR 150–250 per Sft in Pakistan; self-levelling 200–500 "
              "(aqsonsgroupofcompanies.com epoxy flooring price 2026); basic mid 200 — installed rate (composite)")
    fdoor = X.W("FIRE-DOOR", "M", "Steel fire-rated door 60 min, 3'-0\"×7'-0\", with frame, door only", "Nos", 59000,
                "Adams Fire Tech standard steel fire-rated door 60 min 3'×7' PKR 59,000 without panic bar / trim "
                "(adamsfiretech.com via search; karachifire.com gives steel fire doors 40,000–100,000+)")

    # assumption lines — Sajjad's figures, kept visible as assumptions
    def bm(no, name, unit, rate, why):
        return X.A(f"BM-CV-{no}", "M", name + " — benchmark, all-in", unit, rate,
                   f"{FILE}, item {no} (tagged there {why}). No dated Lahore source found in the 26-Sep-2026 search; "
                   "replace with a quotation or GRN")

    topsoil = X.A("TOPSOIL", "M", "Topsoil / sweet earth for lawns", "Cft", 0,
                  "No Lahore price found in the 26-Sep-2026 search. Enter a quotation")

    # GRN lines
    poly = X.G("Phoenix", "Polythene Sheet (250 Microns)")
    enam = X.Gper("GRN-PHO-ENAMEL-L", "Enamel paint (Phoenix GRN, beige), per litre", "Ltr", "Phoenix",
                  "Enamel Paint Beige 3.64LTR", 3.64, "Ltr")
    redox = X.Gper("GRN-QUA-REDOX-L", "Red oxide primer (MS pipe paint), per litre", "Ltr", "Quadrangle",
                   "MS pipe paint Red Oxide", 3.64, "Ltr")
    backer = X.G("Quadrangle", 'Backer Rod 1"')
    aquafin = X.Gper("GRN-QUA-AQUAFIN-KG", "Aquafin IC crystalline waterproofing slurry, per kg", "Kg", "Quadrangle",
                     "Aquafin IC (Crystalline Waterproofing Slurry) 25Kg", 25, "Kg")
    sika105 = X.G("Quadrangle", "Cementitious Coating Sika Seal 105")
    gran = X.G("Quadrangle", 'Window Sill 3/4" Thick 12" Width (Black Granite)')
    giframe = X.G("Quadrangle", "Galvanized steel door frame 9\" thick wall, 3'-0\"x7'-0\"")
    mcover = X.M("C19-40-3", "comp")

    # ======================================================= 1 Site preparation and demolition
    X.item("CV-001", "C01", "Dismantling", "Dismantling brick masonry in cement or lime mortar, including sorting and "
           "stacking serviceable bricks within 100 ft lead, complete in all respects", "Labour only; carriage "
           "off site measured separately (CV-005)", "Cft",
           L=[row(X.M("C4-13-1"), 1, "MRS labour per cft of brickwork dismantled")], wast=0,
           note=file_note(55, "Cft", "CALC-2026 — its own working 0.055 mason-day × 2,400 + 0.020 helper-day × 1,400 "
                          "= 160, not 55: arithmetic error") + "MRS 2026 labour is 69.03 per cft.")
    X.item("CV-002", "C01", "Dismantling", "Dismantling reinforced cement concrete, separating reinforcement from "
           "concrete, cleaning and straightening the bars, complete in all respects", "Manual with hand breakers; "
           "debris carriage measured separately (CV-005)", "Cft",
           L=[row(X.M("C4-20-1"), 1, "MRS labour per cft")], wast=0,
           note=file_note(180, "Cft", "CALC-2026") + "MRS 2026 labour alone is 292.34 per cft; the file's 180 "
           "understates it. Hired breaker plant, if used, is extra.")
    X.item("CV-003", "C01", "Dismantling", "Hacking and removing existing cement or lime plaster from walls and "
           "ceilings, complete in all respects", "Surface left rough for new plaster", "Sft",
           L=[row(X.M("C4-48-1"), 1, "MRS labour per Sft")], wast=0,
           note=file_note(35, "Sft", "CALC-2026") + "MRS 2026 labour is 6.77 per Sft (removing cement plaster).")
    X.item("CV-004", "C01", "Dismantling", "Dismantling glazed, ceramic or encaustic floor / wall tiles including "
           "bedding, complete in all respects", "Debris stacked within site", "Sft",
           L=[row(X.M("C4-50-1"), 1, "MRS labour per Sft")], wast=0,
           note=file_note(45, "Sft", "CALC-2026") + "MRS 2026 labour is 37.36 per Sft.")
    X.item("CV-005", "C01", "Site preparation", "Loading, carting away and disposing of malba / debris off site to an "
           "approved dumping point within Lahore, complete in all respects", "Measured on the dismantled volume",
           "Cft", M=[row(bm("005", "Carting away debris, loading + tractor-trolley / dumper", "Cft", 55,
                               "ASSUMP-2026"), 1)], wast=0,
           note="No dated Lahore haulage rate found (MRS carriage chapter is not loaded). Rate depends on lead and "
                "tipping point — get a transporter quote.")
    X.item("CV-006", "C01", "Site preparation", "Providing, erecting and later removing temporary site hoarding 8 ft "
           "high of GI / ply sheet on steel frame, complete in all respects", "Rft of hoarding", "Rft",
           M=[row(bm("006", "Temporary hoarding 8 ft high", "Rft", 900, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-007", "C01", "Site preparation", "Setting out and survey with total station / auto-level, fixing "
           "benchmarks and grid lines, complete in all respects", "Lump sum per building", "Job",
           M=[row(bm("007", "Setting out and survey", "Job", 25000, "ASSUMP-2026"), 1)], wast=0)

    # ======================================================= 2 Earthwork
    X.item("CV-008", "C01", "Earthwork", "Bulk excavation for basement by excavator in ordinary soil, depth 5 to 15 ft, "
           "including trimming and stacking within 50 ft lead, complete in all respects",
           "Disposal off site measured separately (CV-009)", "Cft",
           M=[row(X.M("C3-21-8", "comp"), 1, "MRS composite (excavator + labour) per cft")], wast=0,
           note=file_note(60, "Cft", "CALC-2026 — excavator 55,000/day at 1,000 cft/day") + "1,000 cft/day is far "
           "below a PC200-class machine; MRS 2026 composite for machine excavation 5–15 ft ordinary soil is 13.02 per "
           "cft.")
    X.item("CV-009", "C01", "Earthwork", "Loading and disposal of surplus excavated earth off site, complete in all "
           "respects", "Lead and tipping charges as per transporter quote", "Cft",
           M=[row(bm("009", "Disposal of surplus earth off site", "Cft", 45, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-010", "C01", "Earthwork", "Dewatering excavation by diesel pump sets including operator, fuel and "
           "discharge lines, complete in all respects", "Per pump-day", "Day",
           M=[row(bm("010", "Dewatering pump set with operator and fuel", "Day", 22000, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-011", "C01", "Earthwork", "Shoring / sheet piling to excavation sides including walers and struts, "
           "provisional, complete in all respects", "Designed against the soil report; specialist quotation",
           "Sft", M=[row(bm("011", "Shoring / sheet piling, provisional", "Sft", 2500, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-012", "C01", "Earthwork", "Compaction of natural sub-grade in 6\" depth, watering and ramming to "
           "specified density, complete in all respects", "Measured on plan area", "Sft",
           M=[row("WATER", "0.5*0.04", "0.5 ft depth × 0.04 cft water per cft")],
           L=[row(X.M("C3-24-3"), "0.5", "MRS compaction labour per cft × 0.5 ft depth")],
           P=[row("P-COMP", 0.0015, "plate compactor, as EW-950")], wast=0,
           note=file_note(35, "Sft", "CALC-2026"))
    X.item("CV-013", "C01", "Earthwork", "Supplying and filling Ravi sand under floors in 6\" layers, watering and "
           "compacting, complete in all respects", "Measured compacted", "Cft",
           M=[row("SAND-RV", 1.2, "1 cft compacted + 20% compaction / bulking"), row("WATER", 0.04)],
           L=[row(X.M("C10-3-1"), 1, "MRS labour per cft (sand filling under floor)")],
           P=[row("P-COMP", 0.0025, "as EX-130")], wast=0, note=file_note(95, "Cft", "CALC-2026"))
    X.item("CV-014", "C01", "Earthwork", "Dry brick soling of 1st class bricks laid flat on ½\" sand bed, sand "
           "grouted, watered and rammed to camber, complete in all respects", "9\"×4½\"×3\" bricks", "Sft",
           M=[row("BRK-1", "144/(9.25*4.75)", "Nos per Sft, bricks laid flat with ¼\" joint"),
              row("SAND-RV", "0.5/12+0.02", "½\" bed + joint grouting")],
           L=[row(X.M("C10-6-1"), 1, "MRS labour per Sft (dry brick paving laid flat)")],
           note=file_note(105, "Sft", "CALC-2026"))
    X.item("CV-015", "C07", "DPC", "Providing and laying polythene sheet 1000 gauge (0.01\" thick) under PCC / "
           "floors, lapped 6\" and taped, complete in all respects", "Phoenix GRN polythene sheet", "Sft",
           M=[row(poly, "0.00984/12*57.4*0.4536*1.15", "0.01\" ÷ 12 ft × 57.4 lb/cft × 0.4536 kg/lb × 1.15 laps")],
           L=[row(X.M("C26-38-2"), 1, "MRS labour per Sft (polythene over DPC / floors)")], wast=0,
           note=file_note(25, "Sft", "ASSUMP-2026"))

    # ======================================================= 3–4 Concrete
    place = [row("L-MASON", 0.01345, "MRS 2026 Ch.6 item 9(c) placing labour 93.70 per cft — mason share, as RCC-RMC"),
             row("L-HELPER", 0.049315, "MRS 2026 Ch.6 item 9(c) — helper share, as RCC-RMC")]
    X.item("CV-016", "C03", "RCC — ready-mix", "Providing and laying ready-mix lean concrete (≈1:4:8) in blinding / "
           "sub-base under foundations, placed, levelled and cured, complete in all respects",
           "Phoenix GRN lean RMC", "Cft", M=[row("RMC-LEAN", 1.02, "1 cft placed + 2%")], L=place,
           note=file_note(520, "Cft", "CALC-2026") + "Delivered lean RMC is 270.03 per cft on Phoenix GRN RCP-209.")
    X.item("CV-017", "C03", "RCC — ready-mix", "Providing and laying reinforced cement concrete 4000 psi ready-mix in "
           "sub-structure (raft, footings, pile caps, plinth beams), pumped, vibrated and cured, excluding "
           "reinforcement and formwork measured separately, complete in all respects",
           "Sub-structure item, kept separate from super-structure for cost per Sft", "Cft",
           M=[row("RMC-4000", 1.02, "1 cft placed + 2%")], L=place,
           P=[row("P-VIBR", 0.008), row("P-PUMP", 1)],
           note=file_note(850, "Cft", "CALC-2026") + "Same build-up as RCC-RMC-4000; MRS 2026 composite for 4000 psi "
           "RCC including formwork is 805.85, so 850 excluding steel and formwork is high.")
    X.item("CV-018", "C03", "RCC — ready-mix", "Providing and laying reinforced cement concrete 4000 psi ready-mix in "
           "super-structure (columns, beams, slabs, stairs), pumped, vibrated and cured, excluding reinforcement and "
           "formwork measured separately, complete in all respects", "Super-structure item", "Cft",
           M=[row("RMC-4000", 1.02, "1 cft placed + 2%")], L=place,
           P=[row("P-VIBR", 0.008), row("P-PUMP", 1)], note=file_note(880, "Cft", "CALC-2026"))
    small = [row("L-MASON", 0.014), row("L-HELPER", 0.055), row("L-OPER", 0.007)]
    X.item("CV-019", "C03", "RCC — nominal mix", "Providing and laying reinforced cement concrete 1:2:4 site-mixed in "
           "lintels, bond beams, sills and chajjas, vibrated and cured, excluding reinforcement and formwork, "
           "complete in all respects", "Small-section pours, site mixed", "Cft",
           M=conc("1:2:4", 1), L=small, P=[row("P-MIXER", 0.012), row("P-VIBR", 0.011)],
           note=file_note(900, "Cft", "CALC-2026") + "Build-up as RCC-124.")
    X.item("CV-020", "C03", "RCC — ready-mix", "Providing and laying water-resisting reinforced cement concrete 4000 "
           "psi ready-mix with integral waterproofing admixture in basement walls / water tanks, excluding "
           "reinforcement and formwork, complete in all respects", "FosPak WP-400 or approved equal", "Cft",
           M=[row("RMC-4000", 1.02, "1 cft placed + 2%"),
              row("ADMIX-WP", "9.911/50*0.2*1.02", "≈9.911 kg cement per cft of 4000 psi mix ÷ 50 kg bag × 0.2 Ltr per bag × 1.02")],
           L=place, P=[row("P-VIBR", 0.008), row("P-PUMP", 1)],
           note=file_note(1020, "Cft", "CALC-2026") + "Admixture dose 0.2 Ltr per 50 kg bag and 9.9 kg cement per cft are "
           "typical values — confirm against the admixture TDS and the mix design.")
    X.item("CV-021", "C03", "RCC — nominal mix", "Providing and laying reinforced cement concrete 1:2:4 in coping, "
           "vibrated and cured, excluding reinforcement and formwork, complete in all respects", "Site mixed",
           "Cft", M=conc("1:2:4", 1), L=small, P=[row("P-MIXER", 0.012), row("P-VIBR", 0.011)],
           note=file_note(900, "Cft", "CALC-2026"))
    X.item("CV-022", "C03", "RCC — nominal mix", "Providing, casting and fixing precast RCC 1:2:4 slabs / covers 3\" "
           "thick including reinforcement, moulds, curing, lifting and fixing in position, complete in all respects",
           "Steel ≈1% of volume", "Sft",
           M=conc("1:2:4", 0.25) + [row("STL60", "0.25*0.01*490*0.4536*1.03", "0.25 cft × 1% × 490 lb/cft × 0.4536 × 1.03")],
           L=[row(X.M("C6-6-13"), 0.25, "MRS precast labour per cft × 0.25 cft"),
              row(X.M("C6-6-16"), 0.25, "MRS erecting and fixing precast per cft × 0.25 cft")],
           note=file_note(300, "Sft", "CALC-2026"))
    X.item("CV-023", "C03", "PCC", "Providing and laying cement concrete 1:2:4 floor topping 2\" thick, finished and "
           "divided into panels, cured, complete in all respects", "MRS Ch.10 item 16(e)", "Sft",
           M=conc("1:2:4", round(2 / 12, 6)), L=[row(X.M("C10-16-5"), 1, "MRS labour per Sft")],
           note=file_note(155, "Sft", "CALC-2026"))
    X.item("CV-024", "C03", "PCC", "Power-trowel finishing of concrete floor with dry-shake metallic / quartz "
           "hardener, complete in all respects", "Hardener dose per TDS", "Sft",
           M=[row(bm("024", "Power-trowel floor with dry-shake hardener", "Sft", 240, "ASSUMP-2026"), 1)], wast=0)

    # ======================================================= 5 Formwork
    def fw(nails, lc, lh, props=1, k=1.0, what=""):
        out = [row("QE-PLY-SH", 1 / 32 * 1.1 / 6 * k, f"1 sheet ÷ 32 Sft × 1.1 ÷ 6 uses{what}"),
               row("QE-TIMB-CFT", 0.03 / 8 * k, f"0.03 cft battens ÷ 8 uses{what}")]
        if props:
            out.append(row("PROPS", 1 * k, f"props hire per Sft{what}"))
        out += [row("MOULD", 0.01 * k, f"1 ÷ 100 Sft per Ltr{what}"), row("NAILS", nails * k, f"nails per Sft{what}")]
        return out, [row("L-CARP", lc * k), row("L-HELPER", lh * k)]

    m, l = fw(0.02, 0.03, 0.028)
    X.item("CV-025", "C02", "Formwork", "Formwork to lintels, chajjas and sunshades including props, erection, oiling "
           "and stripping, complete in all respects", "Contact area; build-up as FW-310 with more carpenter time for "
           "small sections", "Sft", M=m, L=l, wast=0, note=file_note(75, "Sft", "CALC-2026"))
    m, l = fw(0.025, 0.024, 0.022, props=0)
    X.item("CV-026", "C02", "Formwork", "Formwork to water-tank walls including through-ties, bracing, oiling and "
           "stripping, complete in all respects", "Contact area; build-up as FW-330", "Sft", M=m, L=l, wast=0,
           note=file_note(90, "Sft", "CALC-2026"))
    m, l = fw(0.02, 0.016, 0.016, props=0, k=0.75, what=" × 0.75 Sft per Rft")
    X.item("CV-027", "C02", "Formwork", "Formwork to slab edges up to 9\" deep, fixed, braced and stripped, complete in "
           "all respects", "Rft of edge (0.75 Sft contact per Rft); build-up as FW-350", "Rft", M=m, L=l, wast=0,
           note=file_note(100, "Rft", "CALC-2026"))
    X.item("CV-028", "C02", "Formwork", "Formwork to circular columns with purpose-made curved shutters, complete in "
           "all respects", "Specialist system", "Sft",
           M=[row(bm("028", "Circular column formwork", "Sft", 130, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-029", "C02", "Formwork", "Steel panel formwork including hire / depreciation, fixing and stripping, "
           "complete in all respects", "Repetitions per supplier", "Sft",
           M=[row(bm("029", "Steel panel formwork", "Sft", 105, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-030", "C02", "Formwork", "Fair-face formwork with film-faced plywood for exposed concrete, complete in "
           "all respects", "Fewer uses than plain shuttering", "Sft",
           M=[row(bm("030", "Fair-face formwork", "Sft", 110, "CALC-2026"), 1)], wast=0)

    # ======================================================= 6 Reinforcement
    X.item("CV-031", "C04", "Reinforcement", "Supplying and fixing welded wire mesh / reinforcement fabric including "
           "laps, chairs and tying, complete in all respects", "Measured by weight", "Kg",
           M=[row(bm("031", "Welded wire mesh supplied and fixed", "Kg", 285, "CALC-2026 — priced at the rebar rate"), 1)],
           wast=0, note="The file prices mesh at the Grade 60 rebar rate; fabric is a different product (only "
                        "per-roll figures were found). Get a supplier quote.")
    X.item("CV-032", "C04", "Reinforcement", "Supplying and installing mechanical rebar couplers including threading "
           "and checking, complete in all respects", "Size dependent", "Nos",
           M=[row(bm("032", "Mechanical rebar coupler, installed", "Nos", 900, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-033", "C04", "Reinforcement", "Drilling and chemically anchoring rebar dowels with injection epoxy, "
           "including cleaning holes, complete in all respects", "Bar and depth dependent", "Nos",
           M=[row(bm("033", "Chemical rebar dowel, installed", "Nos", 750, "ASSUMP-2026"), 1)], wast=0)

    # ======================================================= 7 Masonry
    def brick(ref, ratio, lab):
        return ([row(ref, 1 / BRICK_CFT, "1 ÷ (9.25 × 4.75 × 3.25 ÷ 1728) Nos per cft")] + mortar(ratio, mw),
                [row(X.M(lab), 1, "MRS labour per cft")])

    for code, desc, ratio, lab, fr in [
            ("CV-034", "in ground-floor walls 9\" and thicker", "1:6", "C7-5-5", 350),
            ("CV-035", "in foundation and plinth, below DPC", "1:6", "C7-4-5", 340),
            ("CV-036", "in walls, cement sand mortar 1:3", "1:3", "C7-5-2", 410),
            ("CV-037", "in walls, cement sand mortar 1:5", "1:5", "C7-5-4", 370),
            ("CV-038", "in parapet walls (separate item)", "1:6", "C7-5-5", 350),
            ("CV-039", "in ledge / low walls (separate item)", "1:6", "C7-5-5", 360)]:
        m, l = brick("BRK-1", ratio, lab)
        X.item(code, "C05", "Brick masonry", f"Providing and laying 1st class brick masonry {desc} in cement sand "
               f"mortar {ratio}, jointed and cured, complete in all respects", "Measured in cft (9\" and thicker)",
               "Cft", M=m, L=l, note=file_note(fr, "Cft", "CALC-2026"))
    X.item("CV-040", "C05", "Block masonry", "Providing and laying AAC / lightweight block masonry in thin-bed adhesive, "
           "complete in all respects", "Block brand and size to be confirmed", "Cft",
           M=[row(bm("040", "AAC block masonry in thin-bed adhesive", "Cft", 520, "ASSUMP-2026"), 1)], wast=0,
           note="No Pakistan AAC block price found (only a Sheikhupura-road manufacturer, no rates).")
    m, l = brick(fab, "1:6", "C7-5-5")
    X.item("CV-041", "C05", "Brick masonry", "Providing and laying fly-ash brick masonry in cement sand mortar 1:6, "
           "jointed and cured, complete in all respects", "9\"×4½\"×3\" fly-ash bricks", "Cft", M=m, L=l,
           note=file_note(300, "Cft", "CALC-2026"))
    m, l = brick("BRK-2", "1:6", "C7-5-5")
    X.item("CV-042", "C05", "Brick masonry", "Providing and laying 2nd class brick masonry in cement sand mortar 1:6, "
           "jointed and cured, complete in all respects", "Boundary / non-load-bearing use", "Cft", M=m, L=l,
           note=file_note(245, "Cft", "CALC-2026"))
    X.item("CV-043", "C05", "Brick masonry", "Providing and laying perforated (honeycomb) 1st class brick walling half "
           "brick thick in cement sand mortar 1:6, complete in all respects", "Measured in Sft of wall face", "Sft",
           M=[row(X.M("C7-16-6", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(270, "Cft", "ASSUMP-2026 — per cft") + "Honeycomb walling is measured by wall face; MRS 2026 "
           "composite used (material at Jan-2026 prices).")
    X.item("CV-044", "C05", "Brick masonry", "Providing and laying brick-on-edge work in cement sand mortar 1:6 over "
           "¾\" bed of 1:6 mortar, complete in all respects", "Flooring / coping, measured in Sft", "Sft",
           M=[row("BRK-1", "144/(9.25*3.25)", "Nos per Sft, bricks on edge with ¼\" joint")]
           + mortar("1:6", round(0.75 / 12 + (4.5 / 12 - 144 / (9.25 * 3.25) * BRICK_VOL), 6),
                    what="bed ¾\" + joints"),
           L=[row(X.M("C10-10-1"), 1, "MRS labour per Sft")],
           note=file_note(290, "Cft", "CALC-2026 — per cft") + "Brick-on-edge work is measured by area.")
    X.item("CV-045", "C05", "Stone masonry", "Providing and laying random rubble stone masonry (uncoursed) in cement "
           "sand mortar 1:6 in ground floor, complete in all respects", "Stone source per approval", "Cft",
           M=[row(X.M("C8-3-6", "comp"), 1, "MRS composite per cft")], wast=0,
           note=file_note(650, "Cft", "ASSUMP-2026") + "No current Lahore stone price found; MRS 2026 composite 351.33.")
    X.item("CV-046", "C06", "Pointing", "Cement pointing struck joints 1:3 on brick walls up to 20 ft height including "
           "raking joints, complete in all respects", "Tuck / struck pointing", "Sft",
           M=[row(X.M("C11-18-2", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(80, "Sft", "ASSUMP-2026"))

    # ======================================================= 8 Damp proofing and waterproofing
    X.item("CV-047", "C07", "DPC", "Providing and laying damp proof course 1½\" thick cement concrete 1:2:4 with two "
           "coats of hot bitumen, complete in all respects", "MRS Ch.6 item 37(b)(i)", "Sft",
           M=conc("1:2:4", 0.125) + [row(bit, "34/100*0.4536", "34 lb per 100 Sft for two coats (MRS roofing basis) × 0.4536")],
           L=[row(X.M("C6-37-4"), 1, "MRS labour per Sft")],
           note=file_note(145, "Sft", "CALC-2026") + "MRS 2026 composite 125.03.")
    X.item("CV-048", "C07", "Waterproofing", "Providing and applying two-coat cementitious waterproofing coating to "
           "wet areas and tanks, complete in all respects", "Sika Seal 105 or approved equal", "Sft",
           M=[row(sika105, 1.1, "per Sft of GRN + 10% turn-ups / laps")],
           L=[row("L-PLMASON", 0.005), row("L-HELPER", 0.005)], wast=0,
           note=file_note(95, "Sft", "CALC-2026") + "Labour output as WP-410 (200 Sft per day).")
    X.item("CV-049", "C07", "Waterproofing", "Providing and applying liquid PU waterproofing membrane with primer and "
           "detailing, complete in all respects", "Brand system", "Sft",
           M=[row(bm("049", "PU liquid membrane, applied", "Sft", 140, "CALC-2026"), 1)], wast=0,
           note="Web search 26-Sep-2026: Lahore PU coating from PKR 70 per Sft, polyurea from 150 "
                "(waterseal.com.pk) — a starting price, not a system rate.")
    X.item("CV-050", "C07", "Waterproofing", "Basement tanking with bituminous membrane, primer and protection board, "
           "complete in all respects", "System brand dependent", "Sft",
           M=[row(bm("050", "Basement tanking with protection board", "Sft", 280, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-051", "C07", "Waterproofing", "Mud phuska roof treatment: 4\" earth, 1\" mud plaster with gobri leeping "
           "and 1st class brick tile terrace grouted in cement mortar, complete in all respects",
           "MRS Ch.9 item 1", "Sft", M=[row(X.M("C9-1-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(280, "Sft", "ASSUMP-2026"))
    X.item("CV-052", "C07", "Insulation", "Roof insulation with 1\" thermopore sheet under a single layer of brick "
           "tiles grouted in cement mortar, complete in all respects", "MRS Ch.9 item 35(iii)", "Sft",
           M=[row(X.M("C9-35-3", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(240, "Sft", "ASSUMP-2026 — 2\" board") + "Web search: 1\" 4×4 ft thermopore sheet "
           "Rs 240–280 (insulationsystem.pk / ikthermopore.com, 2026) ≈ 16 per Sft per inch extra thickness.")
    X.item("CV-053", "C07", "Waterproofing", "Providing and fixing PVC water stopper 8\" wide in construction joints "
           "including welding joints and fixing to reinforcement, complete in all respects", "Marflex or equal",
           "Rft", M=[row("WSTOP", 1.05, "+5% laps / welds")],
           L=[row("L-CARP", 0.01), row("L-HELPER", 0.01)],
           note=file_note(450, "Rft", "ASSUMP-2026") + "The library already holds WSTOP at 170 per Rft (Phoenix GRN). "
           "Fixing output 100 Rft per day is an assumption.")
    X.item("CV-054", "C07", "Waterproofing", "Filling expansion joints ½\"–1\" wide with backer rod and sealant, "
           "complete in all respects", "Polysulphide / silicone per approval", "Rft",
           M=[row(backer, 1.05), row("SEALANT", 1)],
           L=[row(X.M("C6-34-1"), 1, "MRS labour per Rft (filling expansion joints)")],
           note=file_note(250, "Rft", "ASSUMP-2026"))
    X.item("CV-055", "C07", "Waterproofing", "Providing and applying crystalline waterproofing slurry two coats to "
           "concrete, complete in all respects", "Aquafin IC or equal", "Sft",
           M=[row(aquafin, 0.149, "two coats ≈0.149 kg per Sft (typical TDS)")],
           L=[row("L-PLMASON", 0.005), row("L-HELPER", 0.005)],
           note=file_note(180, "Sft", "ASSUMP-2026") + "Coverage from typical TDS — confirm.")
    X.item("CV-056", "C07", "Waterproofing", "Crack / leakage injection grouting with PU or epoxy resin through ports, "
           "complete in all respects", "Consumption varies", "Rft",
           M=[row(bm("056", "Injection grouting", "Rft", 1200, "ASSUMP-2026"), 1)], wast=0)

    # ======================================================= 9 Plaster and rendering
    X.item("CV-057", "C06", "Internal plaster", "Cement sand plaster 1:4, 3/8\" thick under soffit of RCC slabs up to "
           "20 ft height, complete in all respects", "Ceiling plaster", "Sft",
           M=mortar("1:4", round(0.375 / 12, 6), what="plaster"),
           L=[row(X.M("C11-12-3", "lab"), 1, "MRS labour per Sft (soffit plaster)")],
           note=file_note(75, "Sft", "CALC-2026"))
    for code, ratio, lab, fr in [("CV-058", "1:5", "C11-10-3", 78), ("CV-059", "1:6", "C11-11-3", 72)]:
        X.item(code, "C06", "External plaster", f"External cement sand plaster {ratio}, ¾\" thick on external faces, "
               "finished true and cured, complete in all respects", "Cradle access included", "Sft",
               M=mortar(ratio, 0.0625, what="plaster"), L=[row(X.M(lab), 1, "MRS labour per Sft")],
               P=[row("P-CRADLE", 0.0015, "as PLS-E")], note=file_note(fr, "Sft", "CALC-2026"))
    X.item("CV-060", "C06", "Internal plaster", "Cement sand plaster 1:4, ½\" thick to jambs, reveals and soffits of "
           "openings up to 9\" wide, complete in all respects", "Rft of opening edge (0.75 Sft per Rft)", "Rft",
           M=mortar("1:4", round(0.75 * 0.5 / 12, 6), what="plaster 0.75 Sft × ½\""),
           L=[row(X.M("C11-9-2"), 0.75, "MRS labour per Sft × 0.75")], note=file_note(55, "Rft", "CALC-2026"))
    X.item("CV-061", "C06", "Internal plaster", "Providing and fixing MS diamond wire mesh 6\" wide over RCC / masonry "
           "junctions with nails and washers, complete in all respects", "MRS Ch.11 item 43", "Rft",
           M=[row(X.M("C11-43-1", "comp"), 1, "MRS composite per Rft")], wast=0,
           note=file_note(55, "Rft", "ASSUMP-2026"))
    X.item("CV-062", "C06", "External plaster", "Making grooves in plaster with ½\"×½\" aluminium trim, complete in "
           "all respects", "MRS Ch.11 item 45", "Rft",
           M=[row(X.M("C11-45-1", "comp"), 1, "MRS composite per Rft")], wast=0,
           note=file_note(80, "Rft", "ASSUMP-2026"))
    X.item("CV-063", "C06", "External plaster", "Providing and applying textured silica-sand coating / colorcrete to "
           "external walls with fungicide and water sealant, complete in all respects", "MRS Ch.11 item 44", "Sft",
           M=[row(X.M("C11-44-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(120, "Sft", "WEB-2026 — no site named"))
    X.item("CV-064", "C06", "Internal plaster", "Applying SBR bonding coat (SBR-cement slurry) on concrete before "
           "plaster, complete in all respects", "SBR 1 : water 1 slurry", "Sft",
           M=[row("SBR", 0.012, "≈0.012 Ltr per Sft (typical TDS)"), row("CEM", 0.005, "cement for slurry")],
           L=[row("L-PLMASON", 0.003), row("L-HELPER", 0.003)],
           note=file_note(55, "Sft", "ASSUMP-2026") + "SBR 600 per Ltr is Phoenix GRN RCP-229. Dose from typical "
           "TDS — confirm.")
    X.item("CV-065", "C06", "Internal plaster", "Ready-mix gypsum plaster ½\" thick, smooth finish, complete in all "
           "respects", "Brand system", "Sft",
           M=[row(bm("065", "Gypsum plaster ½\"", "Sft", 120, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-066", "C06", "External plaster", "Double scaffolding for external elevation work including erection, "
           "hire and striking, measured on elevation area, complete in all respects", "Per Sft of elevation", "Sft",
           M=[row(bm("066", "Scaffolding on elevation", "Sft", 75, "CALC-2026"), 1)], wast=0,
           note="House standard §5 E: scaffolding as its own item.")
    for code, th, lab, fr in [("CV-067", 1.5, "C10-16-3", 110), ("CV-068", 3, "C10-16-9", 170)]:
        X.item(code, "C06", "Screed", f"Cement sand screed 1:4, {fmt(th)}\" average thickness, to falls, floated "
               "finish and cured, complete in all respects", "Labour as MRS floor topping of the same thickness",
               "Sft", M=mortar("1:4", round(th / 12, 6), what="screed"),
               L=[row(X.M(lab), 1, "MRS labour per Sft")], note=file_note(fr, "Sft", "CALC-2026"))
    X.item("CV-069", "C06", "Screed", "Providing and laying foam concrete 3\" thick on roof to falls, complete in all "
           "respects", "MRS Ch.6 item 26", "Sft",
           M=[row(X.M("C6-26-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(220, "Sft", "ASSUMP-2026"))
    X.item("CV-070", "C06", "Screed", "Self-levelling underlayment ⅛\"–3/16\" with primer, complete in all respects",
           "Brand system", "Sft", M=[row(bm("070", "Self-levelling screed", "Sft", 250, "ASSUMP-2026"), 1)], wast=0)

    # ======================================================= 10 Flooring and skirting
    X.item("CV-071", "C09", "Terrazzo", "Providing and laying in-situ terrazzo / mosaic flooring 1½\" thick with ½\" "
           "mosaic topping in grey cement, ground and polished, complete in all respects", "MRS Ch.10 item 22(a)(i)",
           "Sft", M=[row(X.M("C10-22-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(500, "Sft", "ASSUMP-2026"))
    X.item("CV-072", "C09", "Terrazzo", "Providing and laying terrazzo tiles 12\"×12\"×1\" grey, full body, in cement "
           "mortar, ground and polished, complete in all respects", "MRS Ch.10 item 39", "Sft",
           M=[row(X.M("C10-39-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(400, "Sft", "ASSUMP-2026"))
    X.item("CV-073", "C09", "Terrazzo", "Providing and laying chips / grit flooring 1½\" thick (grey cement, marble "
           "chips), ground and polished, complete in all respects", "MRS Ch.10 item 22(b)(i)", "Sft",
           M=[row(X.M("C10-22-3", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(380, "Sft", "ASSUMP-2026"))
    bed = mortar("1:4", round(1 / 12, 6), what="bed 1\"")
    X.item("CV-074", "C09", "Marble / granite", "Providing and laying ¾\" granite flooring on 1\" cement sand bed 1:4, "
           "jointed, cleaned and polished, complete in all respects", "Quadrangle GRN black granite", "Sft",
           M=[row(gran, 1.08, "+8% cutting")] + bed, L=[row(X.M("C10-47-2", "lab"), 1, "MRS labour per Sft (¾\" stone)")],
           P=[row("P-CUTTER", 0.003)], wast=0, note=file_note(750, "Sft", "CALC-2026"))
    X.item("CV-075", "C09", "Marble / granite", "Providing and laying ¾\" marble to stair treads and risers on cement "
           "sand bed, edges rounded and polished, complete in all respects", "Ziarat White or approved", "Sft",
           M=[row("MARBLE", 1.1, "+10% cutting")] + bed, L=[row(X.M("C10-48-1", "lab"), 1, "MRS labour per Sft")],
           P=[row("P-CUTTER", 0.004)], wast=0, note=file_note(700, "Sft", "CALC-2026"))
    X.item("CV-076", "C09", "Marble / granite", "Providing and fixing ¾\" marble threshold / window sill 6\" wide on "
           "cement sand bed, edges polished, complete in all respects", "0.5 Sft per Rft", "Rft",
           M=[row("MARBLE", "0.5*1.1", "0.5 Sft × 1.1")] + mortar("1:4", round(0.5 / 12, 6), what="bed 1\" × 0.5 Sft"),
           L=[row(X.M("C10-48-1", "lab"), 0.5, "MRS labour per Sft × 0.5")], wast=0,
           note=file_note(450, "Rft", "ASSUMP-2026"))
    X.item("CV-077", "C09", "Porcelain / ceramic tiles", "Providing and laying non-skid chequered porcelain tiles "
           "12\"×12\" to bathrooms / roof, jointed and cleaned, complete in all respects", "MRS Ch.10 item 46(c)",
           "Sft", M=[row(X.M("C10-46-7", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(240, "Sft", "WEB-2026 — no site named"))
    X.item("CV-078", "C09", "Porcelain / ceramic tiles", "Providing and laying terracotta floor tiles on cement mortar, "
           "grouted, complete in all respects", "Size / finish per approval", "Sft",
           M=[row(bm("078", "Terracotta tile flooring", "Sft", 420, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-079", "C09", "Porcelain / ceramic tiles", "Providing and laying full-body homogeneous / vitrified tiles "
           "24\"×24\" on adhesive, grouted, complete in all respects", "MRS Ch.10 item 46(a)(iii)", "Sft",
           M=[row(X.M("C10-46-3", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(400, "Sft", "WEB-2026 — no site named"))
    X.item("CV-080", "C09", "Resin flooring", "Epoxy floor coating, basic industrial two-coat system including surface "
           "preparation, complete in all respects", "Self-levelling / decorative systems cost more", "Sft",
           M=[row(epx, 1)], wast=0, note=file_note(250, "Sft", "WEB-2026"))
    X.item("CV-081", "C09", "Resilient flooring", "Supplying and installing SPC vinyl plank flooring with underlay and "
           "trims, complete in all respects", "Standard residential grade", "Sft",
           M=[row(spc_s, 1.05, "+5% cutting")], L=[row(spc_i, 1)], wast=0, note=file_note(300, "Sft", "WEB-2026"))
    X.item("CV-082", "C09", "Resilient flooring", "Supplying and installing laminate wooden flooring 5/16\" thick AC3 with "
           "underlay and skirting trims, complete in all respects", "Standard grade", "Sft",
           M=[row(lam_s, 1.05, "+5% cutting")], L=[row(lam_i, 1)], wast=0, note=file_note(360, "Sft", "WEB-2026"))
    X.item("CV-083", "C09", "Skirting", "Providing and fixing 4\" porcelain tile skirting on adhesive, grouted, "
           "complete in all respects", "0.333 Sft per Rft", "Rft",
           M=[row("TILE-POR", "4/12*1.1", "4\" ÷ 12 × 1.1"), row("TILEADH", "4/12*0.45", "0.45 kg/Sft × 4/12"),
              row("GROUT", "4/12*0.02", "grout per Sft × 4/12")],
           L=[row(X.M("C10-33-1", "lab"), "4/12", "MRS skirting labour per Sft × 4/12")], wast=0,
           note=file_note(150, "Rft", "CALC-2026"))
    X.item("CV-084", "C09", "Skirting", "Providing and fixing MS angle 1½\"×1½\"×¼\" edge-protector nosing to stair "
           "steps with holdfasts, complete in all respects", "MRS Ch.25 item 42", "Rft",
           M=[row(X.M("C25-42-1", "comp"), 1, "MRS composite per Rft")], wast=0,
           note=file_note(500, "Rft", "ASSUMP-2026 — tile / stone profile") + "An aluminium or stone nosing profile "
           "needs a supplier price.")

    # ======================================================= 11 Doors, windows and joinery
    X.item("CV-085", "C11", "Doors", "Providing and fixing deodar wood chowkat 4½\"×3\" wrought, framed and fixed with "
           "holdfasts, complete in all respects", "0.0938 cft per Rft + 10% waste", "Rft",
           M=[row(X.M("C12-1-1", "comp"), "4.5*3/144*1.1", "4.5\" × 3\" ÷ 144 × 1.1 cft per Rft")], wast=0,
           note=file_note(520, "Rft", "CALC-2026") + "MRS 2026 deodar plain wood work composite 13,041.35 per cft "
           "gives ≈1,345 per Rft; the file's 520 implies deodar well below market.")
    X.item("CV-086", "C11", "Doors", "Providing and fixing 1st class deodar wood panelled door 1¾\" thick with "
           "fittings, complete in all respects", "MRS Ch.12 item 5(a)(ii)", "Sft",
           M=[row(X.M("C12-5-2", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(2500, "Sft", "ASSUMP-2026"))
    X.item("CV-087", "C11", "Doors", "Supplying and fixing steel fire-rated door 60 min 3'-0\"×7'-0\" with frame and "
           "hardware, complete in all respects", "Certified supplier", "Sft",
           M=[row(fdoor, "1/21", "1 door ÷ 21 Sft"), row("DOOR-HW", "1/21", "1 set ÷ 21 Sft")],
           L=[row("L-CARP", 0.04), row("L-HELPER", 0.025)], wast=0,
           note=file_note(4500, "Sft", "ASSUMP-2026") + "Panic bar / closer extra.")
    X.item("CV-088", "C11", "Doors", "Providing and fixing MS single-leaf door of angle-iron frame and MS sheet, "
           "primed and painted, complete in all respects", "MRS Ch.25 item 61(i)", "Sft",
           M=[row(X.M("C25-61-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(1300, "Sft", "CALC-2026"))
    X.item("CV-089", "C12", "uPVC windows", "Supplying and installing uPVC sliding window with clear glass and "
           "hardware, complete in all respects", "Single glazed", "Sft", M=[row(upvc_w, 1)], wast=0,
           note=file_note(2800, "Sft", "WEB-2026"))
    X.item("CV-090", "C11", "Doors", "Providing and fixing premium uPVC door with uPVC chowkat and hardware, complete "
           "in all respects", "MRS Ch.26 item 48", "Sft",
           M=[row(X.M("C26-48-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(3800, "Sft", "WEB-2026 — no site named"))
    X.item("CV-091", "C12", "Aluminium doors", "Supplying and installing powder-coated aluminium sliding door with "
           "glazing and hardware, complete in all respects", "Standard section", "Sft", M=[row(alu_d, 1)], wast=0,
           note=file_note(3000, "Sft", "WEB-2026"))
    X.item("CV-092", "C11", "Doors", "Providing and fixing 24 SWG GI sheet rolling shutter with MS channel guides, "
           "box and spring, complete in all respects", "MRS Ch.25 item 41; motor extra", "Sft",
           M=[row(X.M("C25-41-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(1900, "Sft", "ASSUMP-2026"))
    X.item("CV-093", "C19", "Metal work", "Providing and fixing MS window grill of ⅜\" square bars with frame, "
           "primed and painted, complete in all respects", "MRS Ch.25 item 58(i); measured by area", "Sft",
           M=[row(X.M("C25-58-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(320, "Kg", "CALC-2026 — per kg") + "Grills are measured by area in the MRS.")
    X.item("CV-094", "C11", "Joinery", "Built-in wardrobe in MDF / laminate with hardware, complete in all respects",
           "Per Rft of front, 7 ft high", "Rft",
           M=[row(bm("094", "Built-in wardrobe", "Rft", 5500, "WEB-2026 — no Pakistan source found"), 1)], wast=0)
    X.item("CV-095", "C11", "Joinery", "Kitchen cabinets base and wall units in MDF / laminate with hardware, complete "
           "in all respects", "Per Rft of run", "Rft",
           M=[row(bm("095", "Kitchen cabinets", "Rft", 6500, "WEB-2026 — no Pakistan source found"), 1)], wast=0)
    X.item("CV-096", "C11", "Joinery", "Bathroom vanity cabinet with top and basin cut-out, sanitary fixture excluded, "
           "complete in all respects", "Standard size", "Nos",
           M=[row(bm("096", "Bathroom vanity", "Nos", 45000, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-097", "C12", "Glass partitions", "Supplying and installing ½\" toughened glass balustrade with fittings, "
           "complete in all respects", "Frameless / SS system", "Rft", M=[row(rail, 1)], wast=0,
           note=file_note(4500, "Rft", "WEB-2026"))
    X.item("CV-098", "C12", "Façade", "Aluminium and glass curtain wall system with anchors and gaskets, complete in "
           "all respects", "System quotation required", "Sft",
           M=[row(bm("098", "Curtain wall", "Sft", 4500, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-099", "C12", "Façade", "ACP external cladding on aluminium framing, complete in all respects",
           "PE / PVDF mid-range", "Sft",
           M=[row(bm("099", "ACP cladding", "Sft", 750, "WEB-2026 — only Indian rates found"), 1)], wast=0)
    X.item("CV-100", "C12", "Glass partitions", "Supplying and installing framed toughened glass shower enclosure, "
           "standard size, complete in all respects", "Single sliding door", "Nos", M=[row(shower, 1)], wast=0,
           note=file_note(40000, "Nos", "WEB-2026"))

    # ======================================================= 12 Painting and ceilings
    X.item("CV-101", "C10", "Enamel", "Preparing surface and painting wood / steel with one priming coat and two coats "
           "of enamel paint, complete in all respects", "Coverage ≈110 Sft per Ltr per coat (typical TDS)", "Sft",
           M=[row(redox, "1/110", "primer 1 coat ÷ 110 Sft/Ltr"), row(enam, "2/110", "enamel 2 coats ÷ 110 Sft/Ltr")],
           L=[row(X.M("C13-5-5", "lab"), 1, "MRS priming coat labour"),
              row(X.M("C13-5-6", "lab"), 2, "MRS subsequent coat labour × 2")],
           note=file_note(60, "Sft", "WEB-2026"))
    X.item("CV-102", "C10", "Enamel", "Preparing steel surface and applying one coat of red-oxide anti-rust primer, "
           "complete in all respects", "Grills, railings, steel work", "Sft",
           M=[row(redox, "1/110", "1 coat ÷ 110 Sft/Ltr")], L=[row(X.M("C13-5-7", "lab"), 1, "MRS priming coat labour")],
           note=file_note(35, "Sft", "WEB-2026"))
    X.item("CV-103", "C10", "Polish", "PU lacquer / wood polish, sealer and multi-coat, rubbed and polished, complete "
           "in all respects", "Per Sft of surface", "Sft",
           M=[row(bm("103", "PU wood polish", "Sft", 120, "ASSUMP-2026"), 1)], wast=0,
           note="MRS 2026 French polishing on new work: 81.98 per Sft composite (Ch.13 item 7).")
    X.item("CV-104", "C10", "Distemper", "Distempering new surface two coats over chalk priming coat, complete in all "
           "respects", "Coverage ≈107 Sft per Ltr per coat", "Sft",
           M=[row(dist, "2/107", "2 coats ÷ 107 Sft/Ltr")],
           L=[row(X.M("C11-23-1", "lab"), 1, "MRS chalk priming coat labour"),
              row(X.M("C11-24-2", "lab"), 1, "MRS distemper two coats labour")],
           note=file_note(30, "Sft", "CALC-2026"))
    X.item("CV-105", "C10", "Textured paint", "Preparing surface and applying fine textured acrylic (Sandtex) coating "
           "to external walls, complete in all respects", "MRS Ch.11 item 40", "Sft",
           M=[row(X.M("C11-40-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(140, "Sft", "CALC-2026"))
    X.item("CV-106", "C10", "Epoxy paint", "Epoxy paint two coats to walls / steel including preparation, complete in "
           "all respects", "Brand system", "Sft",
           M=[row(bm("106", "Epoxy paint 2 coats", "Sft", 120, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-107", "C10", "Whitewash", "White washing new surface three coats, complete in all respects",
           "MRS Ch.11 item 26(a)(iii)", "Sft", M=[row(X.M("C11-26-3", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(18, "Sft", "CALC-2026"))
    X.item("CV-108", "C07", "Waterproofing", "Bitumen coating two coats to plastered / concrete surfaces at 14 lb per "
           "100 Sft, complete in all respects", "Foundations, retaining faces", "Sft",
           M=[row(bit, "14/100*0.4536", "14 lb per 100 Sft × 0.4536")],
           L=[row(X.M("C13-9-2"), 1, "MRS labour per Sft")], note=file_note(55, "Sft", "ASSUMP-2026"))
    X.item("CV-109", "C08", "POP ceiling", "Plain POP false ceiling with framing and basic cornice, complete in all "
           "respects", "Installed rate", "Sft", M=[row(pop, 1)], wast=0, note=file_note(180, "Sft", "WEB-2026"))
    X.item("CV-110", "C08", "PVC ceiling", "PVC / WPC panel ceiling on support frame with trims, complete in all "
           "respects", "Installed rate", "Sft", M=[row(pvc, 1)], wast=0, note=file_note(180, "Sft", "WEB-2026"))
    X.item("CV-111", "C08", "Tile / grid ceiling", "Vinyl-faced gypsum ceiling tiles 2'×2' on exposed grid, complete "
           "in all respects", "Installed rate", "Sft",
           M=[row(bm("111", "Gypsum vinyl tile ceiling 2×2 on grid", "Sft", 220, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-112", "C08", "Tile / grid ceiling", "Metal linear ceiling with carriers and suspension, complete in all "
           "respects", "Installed rate", "Sft",
           M=[row(bm("112", "Metal linear ceiling", "Sft", 450, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-113", "C08", "Gypsum board ceiling", "Gypsum board bulkhead on GI framing, jointed and ready for paint, "
           "measured per running foot, complete in all respects", "Up to 2 ft girth", "Rft",
           M=[row(bm("113", "Gypsum bulkhead", "Rft", 500, "ASSUMP-2026"), 1)], wast=0,
           note="Gypsum board and GI section prices are still missing (QE-GYP-* lines at 0).")

    # ======================================================= metal work
    X.item("CV-114", "C19", "Metal work", "Providing and fixing stair railing of MS box section 1½\"×3\" 16 SWG with "
           "MS flats, primed and painted, complete in all respects", "MRS Ch.25 item 34", "Rft",
           M=[row(X.M("C25-34-1", "comp"), 1, "MRS composite per Rft")], wast=0,
           note=file_note(1600, "Rft", "CALC-2026"))
    X.item("CV-115", "C04", "Structural steel", "Fabrication and erection of structural steel work in angles, tees, "
           "flats and sheet including cutting, drilling, welding and priming, complete in all respects",
           "MRS Ch.25 item 10 (heavy steel work)", "Kg",
           M=[row(X.M("C25-10-1", "comp"), 1, "MRS composite per Kg")], wast=0,
           note=file_note(360, "Kg", "CALC-2026 — priced at the rebar rate") + "Sections: TR girder 190–235 per kg "
           "(checkprice.pk, search 26-Sep-2026).")
    X.item("CV-116", "C19", "Metal work", "MS cat ladder of angle / flat / round bars, primed and painted, fixed, "
           "complete in all respects", "Per Rft of ladder", "Rft",
           M=[row(bm("116", "MS cat ladder", "Rft", 1400, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-117", "C19", "Metal work", "Providing and fixing MS double-leaf main gate of angle-iron frame and sheet, "
           "with hinges and locking, primed and painted, complete in all respects", "MRS Ch.25 item 61(ii)", "Sft",
           M=[row(X.M("C25-61-2", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(1800, "Sft", "ASSUMP-2026"))

    # ======================================================= 16 External works
    X.item("CV-118", "C17", "External works", "Boundary wall 9\" brick with plaster both sides and paint, including "
           "normal foundation allowance, measured on elevation, complete in all respects", "Composite", "Sft",
           M=[row(bm("118", "Boundary wall all-in", "Sft", 1200, "ASSUMP-2026"), 1)], wast=0,
           note="Better priced from its parts: CV-035 / CV-034 masonry, PLS-E / PLS-I plaster and paint items.")
    X.item("CV-119", "C18", "Paving", "Providing and fixing precast K-2 edge kerb stone embedded in PCC 1:2:4 over lean "
           "concrete, complete in all respects", "MRS Ch.10 item 45", "Rft",
           M=[row(X.M("C10-45-1", "comp"), 1, "MRS composite per Rft")], wast=0,
           note=file_note(900, "Rft", "ASSUMP-2026"))
    X.item("CV-120", "C18", "Road works", "Road sub-base of compacted gravel in 6\" layers, watered and compacted, "
           "complete in all respects", "Measured compacted", "Cft",
           M=[row("GRAVEL-SB", 1.2, "+20% compaction"), row("WATER", 0.04)],
           L=[row("L-HELPER", 0.01, "as EX-130")], P=[row("P-COMP", 0.0025, "as EX-130")], wast=0,
           note=file_note(180, "Cft", "CALC-2026"))
    X.item("CV-121", "C18", "Road works", "Road base of graded crushed aggregate in 6\" layers, watered and compacted, "
           "complete in all respects", "Measured compacted", "Cft",
           M=[row("CRSH-SG", 1.25, "+25% compaction"), row("WATER", 0.04)],
           L=[row("L-HELPER", 0.012)], P=[row("P-COMP", 0.003)], wast=0, note=file_note(230, "Cft", "CALC-2026"))
    X.item("CV-122", "C18", "Road works", "Asphalt wearing course 2\" compacted with tack coat, complete in all respects",
           "Plant and source dependent", "Sft",
           M=[row(bm("122", "Asphalt carpet 2\"", "Sft", 280, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-123", "C18", "Road works", "RCC road slab 6\" with mesh reinforcement, formwork and finish, complete in "
           "all respects", "Composite", "Sft",
           M=[row(bm("123", "RCC road 6\"", "Sft", 650, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-124", "C17", "External drainage", "Septic tank, domestic 8–10 users, masonry / RCC with plaster and "
           "waterproofing, excluding excavation, complete in all respects", "Size by design", "Nos",
           M=[row(bm("124", "Septic tank", "Nos", 250000, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-125", "C17", "External drainage", "Soakage pit with honeycomb brick lining, filter media and RCC cover, "
           "complete in all respects", "Size by design", "Nos",
           M=[row(bm("125", "Soakage pit", "Nos", 180000, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-126", "C17", "External drainage", "Providing and fitting 4\" gully trap with PVC grating and masonry "
           "chamber 12\"×12\", complete in all respects", "MRS Ch.19 item 36", "Nos",
           M=[row(X.M("C19-36-1", "comp"), 1, "MRS composite per Nos")], wast=0,
           note=file_note(9500, "Nos", "ASSUMP-2026 — with larger chamber and cover") + "Larger chambers need their "
           "own build-up.")
    X.item("CV-127", "C17", "External drainage", "Storm-water drain, masonry / RCC channel with render and cover, "
           "complete in all respects", "Standard detail", "Rft",
           M=[row(bm("127", "Storm-water drain", "Rft", 1800, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-128", "C18", "Landscaping", "Grassing with fine Dhaka grass on 3\" topsoil, watering and maintenance "
           "until established, complete in all respects", "Topsoil price to be entered", "Sft",
           M=[row(grass, 1.1, "+10% losses"), row(topsoil, 0.25, "3\" topsoil")],
           L=[row("L-HELPER", 0.02, "50 Sft per helper-day (assumption)")],
           note=file_note(160, "Sft", "ASSUMP-2026") + "Shows as incomplete until TOPSOIL is priced.")
    X.item("CV-129", "C18", "Landscaping", "Masonry / RCC planter with waterproofing and finish, complete in all "
           "respects", "Standard size", "Nos",
           M=[row(bm("129", "Planter", "Nos", 15000, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-130", "C12", "Façade", "Providing and fixing ¾\" sand stone cladding 12\"×24\" on walls over "
           "pre-plastered surface, complete in all respects", "MRS Ch.11 item 41", "Sft",
           M=[row(X.M("C11-41-1", "comp"), 1, "MRS composite per Sft")], wast=0,
           note=file_note(650, "Sft", "WEB-2026 — no site named"))

    # ======================================================= Repair
    X.item("CV-R01", "C06", "Repair", "Crack treatment to plaster / concrete: chasing, filling with repair mortar and "
           "sealant, mesh where required, complete in all respects", "Per Rft of crack", "Rft",
           M=[row(bm("R01", "Crack treatment", "Rft", 180, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-R02", "C06", "Repair", "Epoxy injection crack repair through injection ports, complete in all respects",
           "Depth / width dependent", "Rft",
           M=[row(bm("R02", "Epoxy injection crack repair", "Rft", 1200, "ASSUMP-2026"), 1)], wast=0)
    X.item("CV-R03", "C06", "Repair", "Hacking old plaster and re-plastering external walls with cement sand plaster "
           "1:4, ½\" thick, using suspended cradle, complete in all respects", "Cradle as a separate plant line",
           "Sft", M=mortar("1:4", round(0.5 / 12, 6), what="plaster"),
           L=[row(X.M("C4-48-1"), 1, "MRS removing plaster labour"), row(X.M("C11-9-2"), 1, "MRS plaster labour ½\"")],
           P=[row("P-CRADLE", 0.0015, "as PLS-E")], note=file_note(120, "Sft", "ASSUMP-2026"))

    # ======================================================= seed items repaired
    fix = {
        "FN-560": {"M": [row("DOOR-W", 1), row("DOOR-HW", 0.055),
                         row(giframe, "1/21", "1 frame ÷ 21 Sft (3'-0\" × 7'-0\" leaf)")],
                   "note": "Frame added 26-Sep-2026 (civil gap review): galvanised steel door frame for 9\" wall, "
                           "Quadrangle GRN — the frame type used on Zameen projects. For a deodar chowkat use CV-085."},
        "EW-950": {"M": [row(paver, 1.03, "+3% cutting"), row("SAND-CH", 0.12)],
                   "note": "Paver block added 26-Sep-2026 (civil gap review); the seed item priced only sand, labour "
                           "and compactor. MRS 2026 composite for 2⅜\" tuff pavers is 216.10 per Sft."},
        "EW-960": {"M": ([row("BRK-1", 56.25 / BRICK_CFT, "9\" walls: 4 × 3.75 ft centre-line × 0.75 × 5 ft = 56.25 cft "
                                                        "× 12.101 bricks per cft")]
                         + mortar("1:6", round(56.25 * mw, 6), what="brickwork mortar")
                         + conc("1:4:8", 10.125, what="base PCC 4.5 × 4.5 × 0.5 ft")
                         + mortar("1:4", round(69 * 0.5 / 12, 6), what="plaster ½\" on 69 Sft")
                         + conc("1:2:4", round(4 * 4 * 4 / 12, 6), what="RCC cover slab 4 × 4 ft × 4\"")
                         + [row("STL60", "5.333333*0.01*490*0.4536", "cover slab steel ≈1% of volume"),
                            row(mcover, 1, "C.I. manhole cover 24\" with frame")]),
                   "L": [row("L-MASON", 1.6), row("L-HELPER", 2.4),
                         row(X.M("C7-4-5"), 56.25, "MRS brickwork labour × 56.25 cft"),
                         row(X.M("C11-9-2"), 69, "MRS plaster labour × 69 Sft")],
                   "P": [],
                   "note": "Materials added 26-Sep-2026 (civil gap review) for a 3 × 3 ft internal, 5 ft deep brick "
                           "manhole: 9\" brick walls 1:6, 6\" PCC 1:4:8 base, ½\" plaster inside, RCC cover slab and "
                           "C.I. cover. The seed item carried labour only."},
    }
    return fix


SEED_M = {  # the seed items' material rows as shipped (raSeed / RA_LIB_SEED)
    "FN-560": [["DOOR-W", 1], ["DOOR-HW", 0.055]],
    "EW-950": [["SAND-CH", 0.12]],
    "EW-960": [],
}
PREV_RATES = {  # published versions of library lines this block moves on
    "L-HELPER": [[1300, "2026-09-23"]],
    "BRK-2": [[15, "2026-09-23"]],
}


def make(html, as_of):
    c = Ctx(html, as_of)
    fix = build(c)
    rates = list(c.rates.values())
    items = c.items
    upd = []
    for iid, f in fix.items():
        upd.append({"id": iid, "M": f["M"], "note": f["note"], **({"L": f["L"], "P": f["P"], "full": True}
                                                                  if "L" in f else {})})
    body = json.dumps({"rates": rates, "items": items, "upd": upd}, ensure_ascii=False, sort_keys=True)
    rev = f"{as_of.isoformat()}-{hashlib.sha1(body.encode()).hexdigest()[:8]}"
    return {"rev": rev, "source": "Civil gap review of " + FILE + " (docs/civil-gap-rate-review.md)",
            "rates": rates, "items": items, "upd": upd,
            "prevRates": PREV_RATES, "prevItems": {k: [v] for k, v in SEED_M.items()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--as-of", default=dt.date.today().isoformat())
    ap.add_argument("--dump", type=Path, help="also write the block to this JSON file")
    a = ap.parse_args()
    html = a.html.read_text(encoding="utf-8")
    data = make(html, dt.date.fromisoformat(a.as_of))
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if BLOCK_RE.search(html):
        html = BLOCK_RE.sub(lambda m: m.group(1) + js + m.group(3), html)
    else:
        if ANCHOR not in html:
            sys.exit("anchor for the new block not found")
        html = html.replace(ANCHOR, f'<script type="application/json" id="raCivilData">{js}</script>\n' + ANCHOR, 1)
    a.html.write_text(html, encoding="utf-8")
    if a.dump:
        a.dump.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = {}
    for r in data["rates"]:
        k = "MRS" if r["code"].startswith("MRS-") else "GRN" if r["code"].startswith("GRN-") else \
            "assumption" if r["vs"] == "A" else "web / other"
        kinds[k] = kinds.get(k, 0) + 1
    print(f"raCivilData {data['rev']}: {len(data['items'])} items, {len(data['upd'])} seed repairs, "
          f"{len(data['rates'])} rate lines {kinds}")


if __name__ == "__main__":
    main()
