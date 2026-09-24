#!/usr/bin/env python3
"""Build the MEP rate analyses for the Rate Analysis library from the MAK final bill.

    tools/mep_rates.py "MAK Final Bill Checking.xlsx"
    tools/mep_rates.py --html path/to/index.html BILL.xlsx

MAK Contractors & Associates did the Mall-35 MEP works on an installation-only
contract (MEP Works Agreement dated 25-Sep-2023: materials and equipment are
provided by the Employer; rates include 7.5% income tax, exclude PRA). Its final
bill, Final IPC-09 (May-2025), therefore gives a dated installation rate for every
MEP item, and the GRN Price Register gives the material the Employer bought.

Each analysed item below is

    A. material  — latest GRN rate from the GRN Price Register (#raGrnData), or a
                   rate line already in the Rate Database; fittings for pipework and
                   accessories for cable tray are added as a share of the pipe / tray
                   value, taken from the Quadrangle GRN receipts themselves
    B. wastage   — per trade (cables 3%, pipework / conduit / duct 5%, fixtures 0%)
    C. labour    — the MAK installation rate for the item, read from the bill
    G/H          — house overhead 8% and profit 10% (editable per item)

Rates, units and quantities of the MAK lines are read from the bill rows listed
in ITEMS, never typed in: every row an item points at must carry the same rate,
or the build stops. Where no GRN exists for a material, the line is kept at 0
and marked "ASSUMPTION — no dated source", so the item shows an unpriced gap
instead of an invented figure. Per-point quantities (feet of wire and conduit
per wiring point) are stated assumptions in the line notes; the rates are not.

Output: the `<script type="application/json" id="raMepData">` block of the
dashboard, which the Rate Analysis library adds to the Rate Database and Item
Library on next load (missing lines and items only; nothing already there is
overwritten).
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = ROOT / "zameen-developments" / "index.html"
GRN_RE = re.compile(r'<script type="application/json" id="raGrnData">(.*?)</script>', re.S)
BLOCK_RE = re.compile(r'(<script type="application/json" id="raMepData">)(.*?)(</script>)', re.S)

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SHEETS = {"E": "03a Electrical", "P": "03b Plumbing", "H": "03c HVAC ", "N": "NON-BOQ"}
BOQ_DATE, NB_DATE = "2023-09-25", "2025-05-31"
BOQ_SRC = ("MAK MEP Works Agreement (Mall-35), 25-Sep-2023 — BOQ item {ref}, installation only "
           "(material by Employer), incl. 7.5% income tax, excl. PRA; billed in MAK Final IPC-09, May-2025")
NB_SRC = ("MAK Final IPC-09 (Mall-35 MEP final bill), 31-May-2025 — Non-BOQ {ref}, rate as billed; "
          "certificate is dated by month (May-2025), month-end used as the effective date")
COIL_FT = 90 / 0.3048          # standard house-wire coil, 90 metres
WAST = {"cable": 3, "pipe": 5, "fix": 0}


def dmy(d):
    y, m, dd = d.split("-")
    return f"{dd}-{MON[int(m) - 1]}-{y}"


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def rs(v):
    return f"{v:,.2f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- GRN
class Grn:
    """Latest-receipt view of the GRN Price Register, same codes as its + Rate DB."""

    def __init__(self, html):
        d = json.loads(GRN_RE.search(html).group(1))
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
            it["last"] = it["rc"][0]
            code = re.sub(r"^INV-", "", it["code"]) or "X"
            dup = seen[(it["site"], it["code"])] > 1 or not it["code"]
            it["db"] = "GRN-" + it["site"][:3].upper() + "-" + code + (f"-{it['ix']}" if dup else "")

    def remark(self, it):
        l, rates = it["last"], [r["rate"] for r in it["rc"]]
        age = (dt.date.today() - dt.date.fromisoformat(l["date"])).days
        s = f"{it['site']} GRN {l['grn'] or '(no receipt no.)'}, {dmy(l['date'])} — {l['vendor'] or 'vendor not recorded'}"
        if it["k"] != 1:
            s += f"; billed {rs(l['grnRate'])} per {it['uom']}, converted to per {it['unit']}"
        if len(it["rc"]) > 1:
            s += f"; {len(it['rc'])} receipts, range {rs(min(rates))}–{rs(max(rates))}"
        if age > 365:
            s += f". Dated {l['date'][:4]} — reconfirm before use"
        return s

    def line(self, ix):
        it = self.items[ix]
        l = it["last"]
        return {"code": it["db"], "kind": "M", "name": it["desc"], "unit": it["unit"], "rate": l["rate"],
                "loc": "Lahore", "src": self.remark(it), "date": l["date"], "vs": "V"}


# ------------------------------------------------------------- derived material lines
PCL_SRC, PCL_DATE = "Pakistan Cables suggested retail price list, 03-Jun-2026", "2026-06-03"
FAST_SRC = "Fast Cables retail price list, 10-Jan-2026"
TRADE_DISC = 0.30   # trade discount on cable list prices, supplied by Sajjad on 24-Sep-2026
# (code, name, Pakistan Cables 90 m coil price, Fast Cables 90 m coil price or None, GRN index for comparison)
PRICE_LIST = [
    ("MEP-W1C15", "Copper wire 1C × 1.5 mm² stranded Cu/PVC 450/750 V (BS 6004)", 10915, 11449, 289),
    ("MEP-W1C25", "Copper wire 1C × 2.5 mm² stranded Cu/PVC 450/750 V (BS 6004)", 17415, 18199, 301),
    ("MEP-W1C4", "Copper wire 1C × 4 mm² Cu/PVC 450/750 V (BS 6004)", 26010, 27499, 307),
    ("MEP-W1C4GY", "Earth wire 1C × 4 mm² Cu/PVC 450/750 V green/yellow (BS 6004)", 26010, 27499, 647),
    ("MEP-W1C6", "Copper wire 1C × 6 mm² Cu/PVC 450/750 V (BS 6004)", 38650, 40599, 275),
    ("MEP-E1C10", "Earth cable 1C × 10 mm² Cu/PVC 450/750 V (BS 6004)", 66810, 68499, 269),
    ("MEP-E1C16", "Earth cable 1C × 16 mm² Cu/PVC 450/750 V (BS 6004)", 101785, 106499, 270),
    ("MEP-E1C25", "Earth cable 1C × 25 mm² Cu/PVC 450/750 V (BS 6004)", 159670, None, 277),
    ("MEP-E1C35", "Earth cable 1C × 35 mm² Cu/PVC 450/750 V (BS 6004)", 224885, None, 1225),
    ("MEP-E1C50", "Earth cable 1C × 50 mm² Cu/PVC 450/750 V (BS 6004)", 305475, None, None),
    ("MEP-E1C70", "Earth cable 1C × 70 mm² Cu/PVC 450/750 V (BS 6004)", 439475, None, 276),
    ("MEP-SPK2C15", "Cable 2C × 1.5 mm² stranded Cu/PVC/PVC 300/500 V (BS 6004)", 27060, 27299, 1469),
    ("MEP-RG6", "Co-axial cable RG-6 (Cu clad steel)", 14560, 23999, None),
    ("MEP-RG11", "Co-axial cable RG-11 (Cu clad steel)", 30490, 36299, None),
]


def derived(grn):
    """Material lines that need a unit conversion of a GRN, or have no GRN at all."""
    out = {}

    for code, name, pcl, fast, gix in PRICE_LIST:
        net = pcl * (1 - TRADE_DISC)
        per = round(net / COIL_FT, 2)
        src = (f"{PCL_SRC} — {name}, {rs(pcl)} per 90 metre coil (registered price, incl. 18% GST), "
               f"less {TRADE_DISC:.0%} trade discount (supplied by Sajjad, 24-Sep-2026) = {rs(round(net, 2))} "
               f"÷ {COIL_FT:.3f} ft = {rs(per)}/Rft")
        if fast:
            src += (f"; cross-check {FAST_SRC}: {rs(fast)} per coil, net "
                    f"{rs(round(fast * (1 - TRADE_DISC) / COIL_FT, 2))}/Rft")
        if gix is not None:
            it = grn.items[gix]; l = it["last"]
            last = l["rate"] / COIL_FT if it["unit"] == "Coil" else l["rate"]
            src += (f"; last GRN {it['site']} {l['grn'] or '(no receipt no.)'}, {dmy(l['date'])}: "
                    f"{rs(round(last, 2))}/Rft")
        out[code] = {"code": code, "kind": "M", "name": name, "unit": "Rft", "rate": per, "loc": "Lahore",
                     "src": src, "date": PCL_DATE, "vs": "I"}

    it = grn.items[469]; l = it["last"]; ft = 500 / 0.3048
    out["MEP-CAT6A"] = {"code": "MEP-CAT6A", "kind": "M", "name": "Cat-6A cable", "unit": "Rft",
                        "rate": round(l["rate"] / ft, 2), "loc": "Lahore",
                        "src": grn.remark(it) + f". Per Rft = {rs(l['rate'])} per 500 metre coil ÷ {ft:.3f} ft",
                        "date": l["date"], "vs": "V"}
    it = grn.items[1183]; l = it["last"]; sft = 107.639          # 1 × 10 metre roll
    out["MEP-NBR19"] = {"code": "MEP-NBR19", "kind": "M", "name": 'NBR / elastomeric insulation sheet 3/4" thick',
                        "unit": "Sft", "rate": round(l["rate"] / sft, 2), "loc": "Lahore",
                        "src": grn.remark(it) + f". Per Sft = {rs(l['rate'])} per roll ÷ {sft} Sft per roll",
                        "date": l["date"], "vs": "V"}
    it = grn.items[805]; l = it["last"]; kg = 0.411
    out["MEP-GI26"] = {"code": "MEP-GI26", "kind": "M", "name": "GI sheet 26 gauge", "unit": "Sft",
                       "rate": round(l["rate"] * kg, 2), "loc": "Lahore",
                       "src": grn.remark(it) + f". Per Sft = {rs(l['rate'])}/kg × {kg} kg/Sft "
                              "(galvanised sheet gauge table, 26 ga = 0.906 lb/Sft)",
                       "date": l["date"], "vs": "I"}
    return out


NOSRC = "ASSUMPTION — no dated source. No GRN for this material in the Quadrangle / Phoenix receipts; enter a quotation or GRN rate"


def zero(code, name, unit):
    return {"code": code, "kind": "M", "name": name, "unit": unit, "rate": 0, "loc": "Lahore",
            "src": NOSRC, "date": "", "vs": "A"}


# Fittings / accessories as a share of pipe / tray value, Quadrangle GRN receipts
FIT = {
    "PPR": (1.054, "PPRC fittings 5,625,676 ÷ PPRC pipes 5,335,563 received, Quadrangle GRNs 05-Jan-2023 to 29-Jul-2025"),
    "UPVC": (0.980, "UPVC fittings 10,860,239 ÷ UPVC pipes 11,077,394 received, Quadrangle GRNs 31-Mar-2022 to 28-Jul-2025"),
    "MS": (0.483, "MS fittings 10,185,712 ÷ MS pipes 21,068,461 received, Quadrangle GRNs 23-May-2022 to 05-Aug-2025"),
    "TRAY": (0.224, "tray bends, tees, reducers and couplers 1,313,311 ÷ tray 5,874,892 received (covers excluded), Quadrangle GRNs 07-Mar-2023 to 03-May-2025"),
}

# ------------------------------------------------------------------ item table
# (code, cat, sub, desc, unit, rows, mats, wast, note)
#  rows : "E:20,21" style references into the bill sheets (see SHEETS)
#  mats : [(ref, qty, note)], ref = GRN index (int) or a Rate Database code (str)
E, PL, FF, HV, ELV = "Electrical", "Plumbing", "Fire Fighting", "HVAC", "ELV"


def pipe(ix, fit, extra=""):
    f, why = FIT[fit]
    return [(ix, 1, "1.00 Rft pipe per Rft" + extra), (ix, f, f"fittings allowance {f} × pipe value — {why}")]


def tray(ix):
    f, why = FIT["TRAY"]
    return [(ix, 1, "1.00 Rft tray per Rft"), (ix, f, f"accessories allowance {f} × tray value — {why}")]


def pt(ft, wires, conduit="COND1", box=None, extra=()):
    """Point wiring: `ft` feet of run, wires = [(ref, conductors)]."""
    m = [(w, n * ft, f"{n} conductors × {ft} ft average run per point (quantity ASSUMPTION)") for w, n in wires]
    m.append((conduit, ft, f"{ft} ft conduit per point (quantity ASSUMPTION)"))
    if box:
        m.append((box, 1, "1 back box per point"))
    m.extend(extra)
    return m


INS = lambda od_in: round(math.pi * (od_in + 1.5) / 12, 3)   # 3/4" wall each side → OD + 1.5"


def ins(od_in, label):
    q = INS(od_in)
    return [("MEP-NBR19", q, f"π × ({od_in}\" OD + 2 × 0.75\") ÷ 12 = {q} Sft of sheet per Rft of {label} pipe")]


ITEMS = [
    # ---------------------------------------------------------------- LT switchgear
    ("ME-201", E, "LT switchgear", "Installing, testing and commissioning Employer-supplied Main LT Panel Board (MLTP), free standing, including cable termination, complete in all respects", "Nos", "E:20,21", [], 0,
     "Panel supplied by Employer. Indicative supply price: Quadrangle GRN RCP-2422, 19-Mar-2025 — MLTP-01 6,721,659 (different project / configuration)."),
    ("ME-202", E, "LT switchgear", "Installing, testing and commissioning Employer-supplied metering / main / ATS / sub-main panel board (MTPB, MPB, ATS, SMPB), complete in all respects", "Nos", "E:28,29,30,31,32,33,35,36,37,38,39,46,47,48,49,50,55,56,57,58", [], 0,
     "Panel supplied by Employer. Indicative supply prices: Quadrangle GRN RCP-2422, 19-Mar-2025 — MTPB Wapda 483,537–1,165,868; MTPB Generator with ATS 1,319,911–3,426,106; SMPB Common 2,613,226."),
    ("ME-205", E, "LT switchgear", "Installing, testing and commissioning Employer-supplied auto load-sharing synchronising generator panel for 3 DG sets, complete in all respects", "Nos", "E:69", [], 0,
     "Panel supplied by Employer. Indicative supply price: Quadrangle GRN RCP-2422, 19-Mar-2025 — Sync Panel 7,331,702."),
    ("ME-206", E, "LT switchgear", "Installing, testing and commissioning Employer-supplied power factor improvement panel (100–175 KVAR), complete in all respects", "Nos", "E:75,76,77", [], 0, ""),
    ("ME-207", E, "Distribution", "Installing, terminating, testing and commissioning Employer-supplied distribution board (DBC / DB / KT-DB / meter box / busbar panel), complete in all respects", "Nos", "E:83,84,85,87,91,97,100,104,105,106,107,108,110,111,112,114,115,116,118,119,120;N:132,133,134,137,138,139,140,142,143", [], 0,
     "DB supplied by Employer. Indicative supply prices: Quadrangle GRN RCP-1232, 26-Oct-2023 — typical floor DBC 50,351–101,130; hotel-room DB 59,778–79,499."),
    ("ME-208", E, "Distribution", "Providing and installing shop / restaurant isolator box, including termination and testing, complete in all respects", "Nos", "E:88,89,92,95,98,101,102", [(924, 1, "1 isolator box per Nos")], 0, ""),
    # ---------------------------------------------------------------- wiring
    ("ME-301", E, "Wiring", "Providing light circuit wiring from MCB in DB to switch board, 2 × 1C 2.5 mm² + 1C 2.5 mm² CPC Cu/PVC in 1\" heavy-duty PVC conduit with accessories, complete in all respects", "Nos", "E:125",
     pt(45, [("MEP-W1C25", 3)]), WAST["cable"], ""),
    ("ME-302", E, "Wiring", "Providing wiring from switch to first light point, 2 × 1C 1.5 mm² + 1C 1.5 mm² CPC Cu/PVC in 1\" PVC conduit with ceiling rose and accessories, complete in all respects", "Nos", "E:127",
     pt(15, [("MEP-W1C15", 3)]), WAST["cable"], ""),
    ("ME-303", E, "Wiring", "Providing light point-to-point wiring, 2 × 1C 1.5 mm² + 1C 1.5 mm² CPC Cu/PVC in 1\" PVC conduit with accessories, complete in all respects", "Nos", "E:129;N:234",
     pt(10, [("MEP-W1C15", 3)]), WAST["cable"], ""),
    ("ME-304A", E, "Switches", "Providing and fixing 1-gang 10 A switch with 16 SWG MS back box, complete in all respects", "Nos", "E:132", [(278, 1, ""), (321, 1, '3"×3" back box')], 0, ""),
    ("ME-304B", E, "Switches", "Providing and fixing 2-gang 10 A switch with 16 SWG MS back box, complete in all respects", "Nos", "E:133", [(1616, 1, ""), (321, 1, '3"×3" back box')], 0, ""),
    ("ME-304C", E, "Switches", "Providing and fixing 3-gang 10 A switch with 16 SWG MS back box, complete in all respects", "Nos", "E:134", [(317, 1, ""), (321, 1, '3"×3" back box')], 0, ""),
    ("ME-304D", E, "Switches", "Providing and fixing 4-gang 10 A switch with 16 SWG MS back box, complete in all respects", "Nos", "E:135", [(330, 1, ""), (1014, 1, '6"×3" back box')], 0, ""),
    ("ME-304E", E, "Switches", "Providing and fixing 6-gang 10 A switch with 16 SWG MS back box, complete in all respects", "Nos", "E:136", [(338, 1, ""), (1014, 1, '6"×3" back box')], 0, ""),
    ("ME-304F", E, "Switches", "Providing and fixing 1-gang 2-way 10 A switch with 16 SWG MS back box, complete in all respects", "Nos", "E:137", [(278, 1, "1-gang switch GRN used for the 2-way switch (no 2-way GRN)"), (321, 1, '3"×3" back box')], 0, ""),
    ("ME-305", E, "Wiring", "Providing wiring of one light point controlled by two 2-way switches, 1.5 mm² Cu/PVC in 1\" PVC conduit, complete in all respects", "Nos", "E:139",
     pt(25, [("MEP-W1C15", 3)]), WAST["cable"], ""),
    ("ME-306A", E, "Wiring", "Providing wiring from MCB in DB to light point, 2 × 1C 2.5 mm² + 1C 2.5 mm² CPC in 1\" PVC conduit, complete in all respects", "Nos", "E:141",
     pt(45, [("MEP-W1C25", 3)]), WAST["cable"], ""),
    ("ME-306B", E, "Wiring", "Providing point-to-point wiring, 2 × 1C 2.5 mm² + 1C 2.5 mm² CPC in 1\" PVC conduit, complete in all respects", "Nos", "E:142",
     pt(10, [("MEP-W1C25", 3)]), WAST["cable"], ""),
    ("ME-307A", E, "Power points", "Providing wiring and fixing 3-pin 15 A switch socket, 3 × 1C 4 mm² (P+N+CPC) in 1\" PVC conduit with 16 SWG MS box, complete in all respects", "Nos", "E:145",
     pt(40, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)], box=321, extra=[(320, 1, "15 A switch socket")]), WAST["cable"], ""),
    ("ME-307B", E, "Power points", "Providing wiring and fixing 3-pin 13 A switch socket, DB to first point, 3 × 1C 4 mm² in 1\" PVC conduit with 16 SWG MS box, complete in all respects", "Nos", "E:146",
     pt(40, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)], box=321, extra=[(318, 1, "13 A switch socket")]), WAST["cable"], ""),
    ("ME-307C", E, "Power points", "Providing wiring and fixing 3-pin 13 A switch socket, point to point, 3 × 1C 4 mm² in 1\" PVC conduit with 16 SWG MS box, complete in all respects", "Nos", "E:147",
     pt(12, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)], box=321, extra=[(318, 1, "13 A switch socket")]), WAST["cable"], ""),
    ("ME-307D", E, "Power points", "Providing wiring and fixing 3-pin 13 A weather-proof socket, point to point, complete in all respects", "Nos", "E:148",
     pt(12, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)], box=321, extra=[("MEP-Z-WPSKT", 1, "weather-proof socket")]), WAST["cable"], ""),
    ("ME-307E", E, "Power points", "Providing wiring and fixing shaver socket, point to point, complete in all respects", "Nos", "E:149",
     pt(12, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)], box=321, extra=[("MEP-Z-SHAVER", 1, "shaver socket")]), WAST["cable"], ""),
    ("ME-307F", E, "Power points", "Providing wiring for hand dryer point, 3 × 1C 4 mm² in 1\" PVC conduit, complete in all respects (dryer by others)", "Nos", "E:150",
     pt(30, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)], box=321), WAST["cable"], ""),
    ("ME-308", E, "Power points", "Providing wiring and fixing 5-pin 32 A industrial socket, 5 × 1C 6 mm² in 1-1/2\" PVC conduit, complete in all respects", "Nos", "E:152",
     pt(40, [("MEP-W1C6", 5)], conduit="COND15", extra=[("MEP-Z-IPS32", 1, "32 A industrial socket with plug")]), WAST["cable"], ""),
    ("ME-309", E, "Power points", "Providing wiring of fan coil unit / air handling unit from DB, 3 × 1C 4 mm² (P+N+CPC) in 1\" PVC conduit, complete in all respects", "Nos", "E:154,156",
     pt(40, [("MEP-W1C4", 2), ("MEP-W1C4GY", 1)]), WAST["cable"], ""),
    ("ME-311", E, "Power points", "Providing wiring of HVAC exhaust fan from DB, 4C 6 mm² + 1C 6 mm² CPC in 1-1/2\" PVC conduit, complete in all respects", "Nos", "E:158",
     [(334, 40, "40 ft of 4C 6 mm² per point (quantity ASSUMPTION)"), ("MEP-W1C6", 40, "40 ft CPC"), ("COND15", 40, "40 ft conduit")], WAST["cable"], ""),
    ("ME-312", E, "Wiring", "Providing wiring and fixing hotel room door bell, 2 × 1C 1.5 mm² in 1\" PVC conduit, complete in all respects", "Nos", "E:160",
     pt(20, [("MEP-W1C15", 2)], box=321, extra=[(603, 1, "door push button"), ("MEP-Z-BELL", 1, "door bell")]), WAST["cable"], ""),
    ("ME-313", E, "Wiring", "Providing wiring and fixing DND panel with door bell push, 2 × 1C 1.5 mm² in 1\" PVC conduit, complete in all respects", "Nos", "E:162",
     pt(20, [("MEP-W1C15", 2)], extra=[("MEP-Z-DND", 1, "DND / PCU panel set")]), WAST["cable"], ""),
    ("ME-314", E, "Wiring", "Providing wiring and fixing RFID key-card time-delay switch, 2 × 1C 2.5 mm² in 1\" PVC conduit to room DB, complete in all respects", "Nos", "E:164",
     pt(15, [("MEP-W1C25", 2)], box=321, extra=[("MEP-Z-KEYCARD", 1, "key-card switch")]), WAST["cable"], ""),
    ("ME-315", E, "Wiring", "Providing wiring and fixing wardrobe light push button, 2 × 1C 1.5 mm² in 1\" PVC conduit, complete in all respects", "Nos", "E:166",
     pt(10, [("MEP-W1C15", 2)], extra=[(603, 1, "push button")]), WAST["cable"], ""),
    ("ME-316", E, "Wiring", "Providing wiring of ceiling / exhaust / bracket fan point as per light point wiring, including fan hook box, complete in all respects", "Nos", "E:168,170,172",
     pt(15, [("MEP-W1C15", 3)], box=321), WAST["cable"], ""),
    ("ME-341", E, "Wiring", "Providing electrical connection point for toilet exhaust fan, complete in all respects", "Nos", "N:244",
     pt(10, [("MEP-W1C15", 3)]), WAST["cable"], ""),
    # ---------------------------------------------------------------- fixtures
    ("ME-401A", E, "Lighting", "Supplying, installing, testing and commissioning 10 W recessed LED downlight, complete in all respects", "Nos", "E:181,182", [(951, 1, "")], 0, ""),
    ("ME-401B", E, "Lighting", "Supplying, installing, testing and commissioning 20 W recessed LED downlight (mall area), complete in all respects", "Nos", "E:183", [("MEP-Z-DL20", 1, "")], 0, ""),
    ("ME-401C", E, "Lighting", "Supplying, installing, testing and commissioning recessed square 3 × 10 W LED downlight, complete in all respects", "Nos", "E:184", [("MEP-Z-DLSQ", 1, "")], 0, ""),
    ("ME-401D", E, "Lighting", "Supplying, installing, testing and commissioning LED track light with track, 3 × 10 W, complete in all respects", "Nos", "E:185",
     [(1477, 1, "track light head"), (1478, 1, "1 track length per light (quantity ASSUMPTION)")], 0, ""),
    ("ME-401E", E, "Lighting", "Supplying, installing, testing and commissioning damp-proof LED linear light 40 W, complete in all respects", "Nos", "E:180", [(1479, 1, "36 W IP66 weather-proof batten GRN used for the 40 W damp-proof linear light")], 0, ""),
    ("ME-401F", E, "Lighting", "Installing, testing and commissioning Employer-supplied light fitting (mirror, surface, wardrobe, bedside, panel, concealed floor light), complete in all respects", "Nos", "E:179,186,188", [], 0,
     "Installation rate only — fittings vary; add the fitting from its own quotation or GRN."),
    ("ME-401G", E, "Lighting", "Installing, testing and commissioning Employer-supplied fancy chandelier as per architect's detail, complete in all respects", "Nos", "E:187", [], 0, ""),
    ("ME-401H", E, "Lighting", "Supplying, installing, testing and commissioning 100 W LED flood light IP66, complete in all respects", "Nos", "E:189", [(93, 1, "")], 0, ""),
    ("ME-401J", E, "Lighting", "Supplying, installing, testing and commissioning 10 W LED bulkhead light / external spot light, complete in all respects", "Nos", "E:190", [("MEP-Z-BULK", 1, "")], 0, ""),
    ("ME-401K", E, "Lighting", "Supplying, installing, testing and commissioning self-contained battery emergency light, wall mounted, complete in all respects", "Nos", "E:191", [(651, 1, "")], 0, ""),
    ("ME-401L", E, "Lighting", "Supplying, installing, testing and commissioning self-contained battery emergency light, ceiling type, complete in all respects", "Nos", "E:192", [(650, 1, "")], 0, ""),
    ("ME-401M", E, "Lighting", "Supplying, installing, testing and commissioning self-contained battery exit sign, complete in all respects", "Nos", "E:193", [(649, 1, "")], 0, ""),
    ("ME-401N", E, "Lighting", "Supplying, installing, testing and commissioning LED rope light, complete in all respects", "Rft", "E:194", [("MEP-Z-ROPE", 1, "")], 5, ""),
    ("ME-401P", E, "Lighting", "Supplying, installing, testing and commissioning outdoor flexible LED strip light IP65, complete in all respects", "Rft", "E:195", [("MEP-Z-STRIP", 1, "")], 5, ""),
    ("ME-401Q", E, "Lighting", "Supplying, installing, testing and commissioning 4 ft linear LED wall washer 48 W IP66, complete in all respects", "Nos", "E:196", [("MEP-Z-WASH", 1, "")], 0, ""),
    ("ME-402", E, "Accessories", "Fabricating, supplying and installing 16 SWG MS floor outlet box, not less than 10\" × 10\", including tile and concrete cutting, complete in all respects", "Nos", "E:198;N:191", [("MEP-Z-FOB", 1, "")], 0, ""),
    ("ME-403", E, "Fans", "Supplying and installing 56\" ceiling fan, complete in all respects", "Nos", "E:201", [(28, 1, "")], 0, ""),
    ("ME-404", E, "Fans", "Supplying and installing 8\" exhaust fan, plastic body, complete in all respects", "Nos", "E:204", [(471, 1, "ceiling-type exhaust fan GRN")], 0, ""),
    ("ME-405", E, "Fans", "Supplying and installing 18\" wall bracket fan, complete in all respects", "Nos", "E:206", [("MEP-Z-BFAN", 1, "")], 0, ""),
    # ---------------------------------------------------------------- LV cables
    ("ME-501A", E, "Power cable", "Supplying, laying, testing and commissioning 1C × 95 mm² Cu/PVC/PVC 600/1000 V cable in conduit / on tray, including lugs and glands, complete in all respects", "Rft", "E:213", [(424, 1, "")], WAST["cable"], ""),
    ("ME-501B", E, "Power cable", "Supplying, laying, testing and commissioning 1C × 70 mm² Cu/PVC 600/1000 V cable, including lugs and glands, complete in all respects", "Rft", "E:214", [(276, 1, "1C × 70 mm² PVC insulated GRN (green/yellow) used")], WAST["cable"], ""),
    ("ME-501C", E, "Power cable", "Supplying, laying, testing and commissioning 1C × 185 mm² Cu/PVC/PVC 600/1000 V cable, including lugs and glands, complete in all respects", "Rft", "E:215,216", [(1224, 1, "")], WAST["cable"], ""),
    ("ME-501D", E, "Power cable", "Supplying, laying, testing and commissioning 1C × 240 mm² Cu/PVC/PVC 600/1000 V cable, including lugs and glands, complete in all respects", "Rft", "E:217,218", [(1226, 1, "")], WAST["cable"], ""),
    ("ME-501E", E, "Power cable", "Supplying, laying, testing and commissioning 1C × 300 mm² Cu/PVC/PVC 600/1000 V cable, including lugs and glands, complete in all respects", "Rft", "E:219", [(1227, 1, "")], WAST["cable"], ""),
    ("ME-502A", E, "Power cable", "Supplying, laying, testing and commissioning 2C × 4 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:222", [("MEP-Z-2C4", 1, "")], WAST["cable"], ""),
    ("ME-502B", E, "Power cable", "Supplying, laying, testing and commissioning 2C × 6 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:223", [(1228, 1, "")], WAST["cable"], ""),
    ("ME-503A", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 6 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:226", [(334, 1, "")], WAST["cable"], ""),
    ("ME-503B", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 10 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:227", [(322, 1, "")], WAST["cable"], ""),
    ("ME-503C", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 16 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:228", [(324, 1, "")], WAST["cable"], ""),
    ("ME-503D", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 25 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:229", [(1236, 1, "")], WAST["cable"], ""),
    ("ME-503E", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 35 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:230", [(0, 1, "")], WAST["cable"], ""),
    ("ME-503F", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 50 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:231", [(1234, 1, "")], WAST["cable"], ""),
    ("ME-503G", E, "Power cable", "Supplying, laying, testing and commissioning 4C × 95 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "E:232", [(329, 1, "")], WAST["cable"], ""),
    ("ME-503H", E, "Power cable", "Supplying, laying, testing and commissioning 3C × 16 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "N:188", [("MEP-Z-3C16", 1, "")], WAST["cable"], ""),
    ("ME-503J", E, "Power cable", "Supplying, laying, testing and commissioning 3C × 4 mm² Cu/PVC/PVC cable, complete in all respects", "Rft", "N:189", [("MEP-Z-3C4", 1, "")], WAST["cable"], ""),
    ("ME-504A", E, "Earthing", "Supplying and laying 1C × 4 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:235", [("MEP-W1C4GY", 1, "")], WAST["cable"], ""),
    ("ME-504B", E, "Earthing", "Supplying and laying 1C × 6 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:236", [("MEP-W1C6", 1, "")], WAST["cable"], ""),
    ("ME-504C", E, "Earthing", "Supplying and laying 1C × 10 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:237", [("MEP-E1C10", 1, "")], WAST["cable"], ""),
    ("ME-504D", E, "Earthing", "Supplying and laying 1C × 16 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:238", [("MEP-E1C16", 1, "")], WAST["cable"], ""),
    ("ME-504E", E, "Earthing", "Supplying and laying 1C × 25 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:239", [("MEP-E1C25", 1, "")], WAST["cable"], ""),
    ("ME-504F", E, "Earthing", "Supplying and laying 1C × 35 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:240", [("MEP-E1C35", 1, "")], WAST["cable"], ""),
    ("ME-504G", E, "Earthing", "Supplying and laying 1C × 50 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:241", [("MEP-E1C50", 1, "")], WAST["cable"], ""),
    ("ME-504H", E, "Earthing", "Supplying and laying 1C × 70 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:242,243,380", [("MEP-E1C70", 1, "")], WAST["cable"], ""),
    ("ME-504J", E, "Earthing", "Supplying and laying 1C × 95 mm² green/yellow PVC insulated earth conductor, complete in all respects", "Rft", "E:244,381", [(424, 1, "1C × 95 mm² cable GRN")], WAST["cable"], ""),
    # ---------------------------------------------------------------- containment
    ("ME-505A", E, "Containment", "Supplying and installing 1\" heavy-duty PVC conduit with accessories and pull wire, complete in all respects", "Rft", "E:249,250", [("COND1", 1, "")], WAST["pipe"], ""),
    ("ME-505B", E, "Containment", "Supplying and installing 1-1/2\" heavy-duty PVC conduit with accessories and pull wire, complete in all respects", "Rft", "E:251,252,384", [("COND15", 1, "")], WAST["pipe"], ""),
    ("ME-505C", E, "Containment", "Supplying and installing 2\" heavy-duty PVC conduit with accessories, complete in all respects", "Rft", "E:253", [(1350, 1, "")], WAST["pipe"], ""),
    ("ME-505D", E, "Containment", "Supplying and installing 3\" heavy-duty PVC conduit with accessories, complete in all respects", "Rft", "E:254", [(1353, 1, "")], WAST["pipe"], ""),
    ("ME-505E", E, "Containment", "Supplying and installing 6\" heavy-duty PVC conduit with accessories, complete in all respects", "Rft", "E:255", [("MEP-Z-COND6", 1, "")], WAST["pipe"], ""),
    ("ME-505F", E, "Containment", "Installing flexible conduit for wiring, complete in all respects", "Nos", "N:21", [], 0, ""),
    ("ME-506A", E, "Containment", "Fabricating, supplying and installing 16 SWG perforated GI cable tray 4\" × 3\" with 18 SWG cover, hangers and supports, complete in all respects", "Rft", "E:265,266", [("MEP-Z-CT4", 1, "")], WAST["pipe"], ""),
    ("ME-506B", E, "Containment", "Fabricating, supplying and installing 16 SWG perforated GI cable tray 6\" × 3\" with hangers and supports, complete in all respects", "Rft", "E:267,268,288", tray(1766), WAST["pipe"], "Cover not included in material (GRN 6\"×3\" cover 204/Rft, RCP-1791, 01-Jul-2024)."),
    ("ME-506C", E, "Containment", "Fabricating, supplying and installing 16 SWG perforated GI cable tray 9\" × 3\" with hangers and supports, complete in all respects", "Rft", "E:269,270", tray(455), WAST["pipe"], ""),
    ("ME-506D", E, "Containment", "Fabricating, supplying and installing 16 SWG perforated GI cable tray / ladder 12\" × 3\" with hangers and supports, complete in all respects", "Rft", "E:271,272,273,287,293,294", tray(777), WAST["pipe"], "15\" tray and roof trays billed at the 12\" rate are grouped here; 12\"×3\" GRN used."),
    ("ME-506E", E, "Containment", "Fabricating, supplying and installing 16 SWG perforated GI cable tray 18\" × 3\" with hangers and supports, complete in all respects", "Rft", "E:274,295", tray(452), WAST["pipe"], ""),
    ("ME-506F", E, "Containment", "Fabricating, supplying and installing 16 SWG perforated GI cable tray / ladder 24\" × 3\" with hangers and supports, complete in all respects", "Rft", "E:275,286", tray(453), WAST["pipe"], ""),
    ("ME-506G", E, "Containment", "Dismantling and re-installing cable tray with additional bend under beam, including cables on it, complete in all respects", "Rft", "E:570,571", [], 0, "4\"×3\" and 6\"×3\" tray. 9\", 12\" and 18\" tray are ME-506H, ME-506J and ME-506K."),
    ("ME-507", E, "Accessories", "Supplying and laying 3.5 mm insulation rubber mat 75 Shore A in MV / LV rooms, complete in all respects", "Sft", "E:296", [("MEP-Z-MAT", 1, "")], 5, ""),
    # ---------------------------------------------------------------- busway
    ("ME-601", E, "Busway", "Installing, testing and commissioning Employer-supplied 2500 A sandwich busway straight length, complete in all respects", "Rft", "E:318", [], 0, ""),
    ("ME-602", E, "Busway", "Installing, testing and commissioning Employer-supplied 2500 A busway elbow / flange end / tap-off box (100–1000 A MCCB), complete in all respects", "Nos", "E:324,329,334,335,336,337", [], 0, ""),
    # ---------------------------------------------------------------- earthing / LPS
    ("ME-801", E, "Earthing", "Supplying and installing copper earth rod electrode, complete in all respects", "Nos", "E:375", [(553, 1, 'Cu-bond earth rod 5/8" × 3 m threaded GRN (BOQ calls 1" × 3000 mm)')], 0, ""),
    ("ME-802", E, "Earthing", "Supplying and installing sectionable copper test link, including brass fixings, complete in all respects", "Nos", "E:387,388", [(919, 1, "inspection chamber / test link L300 × W50 × T6 GRN")], 0, ""),
    ("ME-803", E, "Earthing", "Testing of complete earthing system with earth tester in the presence of the Engineer, with written report, complete in all respects", "Job", "E:391", [], 0, ""),
    ("ME-811", E, "Lightning protection", "Supplying, installing, testing and commissioning ESE lightning arrestor, complete in all respects", "Nos", "E:397", [(658, 1, "")], 0, ""),
    ("ME-812", E, "Lightning protection", "Supplying and installing 2 ft-class GI mast for ESE arrestor, including fixing, complete in all respects", "Nos", "E:399", [("MEP-Z-MAST", 1, "")], 0, "BOQ mast is 2 metre high, 1-1/2\" dia GI pipe."),
    ("ME-813", E, "Lightning protection", "Supplying and installing copper down-conductor strip 30 × 2 with clips and fixings, complete in all respects", "Rft", "E:401", [("MEP-Z-CUSTRIP", 1, "")], 5, ""),
    ("ME-814", E, "Lightning protection", "Supplying, installing and connecting surge / lightning event counter, complete in all respects", "Nos", "E:403", [(956, 1, "")], 0, ""),
    ("ME-815", E, "Lightning protection", "Supplying and installing copper-bond threaded earth rods (set of 3) bonded in manhole, complete in all respects", "Set", "E:405", [(553, 3, "3 rods per set; 5/8\" × 3 m GRN")], 0, ""),
    # ---------------------------------------------------------------- ELV: fire alarm
    ("MX-1101", ELV, "Fire alarm", "Installing, testing and commissioning 6-loop intelligent addressable fire alarm control panel, complete in all respects", "Nos", "E:429", [(339, 1, "")], 0, ""),
    ("MX-1102", ELV, "Fire alarm", "Supplying, installing and connecting addressable manual call station, complete in all respects", "Nos", "E:430", [(347, 1, "")], 0, ""),
    ("MX-1103", ELV, "Fire alarm", "Supplying, installing and connecting addressable alarm sounder, complete in all respects", "Nos", "E:431", [(346, 1, "")], 0, ""),
    ("MX-1104", ELV, "Fire alarm", "Supplying, installing and connecting addressable optical smoke detector, complete in all respects", "Nos", "E:432,433", [(349, 1, "smoke detector with built-in isolator")], 0, "Smoke detector with sounder base billed at the same rate; sounder base not included."),
    ("MX-1105", ELV, "Fire alarm", "Supplying, installing and connecting addressable multi (smoke and heat) detector, complete in all respects", "Nos", "E:434", [(348, 1, "")], 0, ""),
    ("MX-1106", ELV, "Fire alarm", "Supplying, installing and connecting addressable rate-of-rise heat detector, complete in all respects", "Nos", "E:435", [(345, 1, "")], 0, ""),
    ("MX-1107", ELV, "Fire alarm", "Supplying, installing and connecting addressable gas detector, complete in all respects", "Nos", "E:436", [(344, 1, "")], 0, ""),
    ("MX-1108", ELV, "Fire alarm", "Providing fire alarm device wiring, 120 min fire-rated 1 × 2C 1.5 mm² cable in 1\" PVC conduit, complete in all respects", "Nos", "E:438",
     [(674, 40, "40 ft FA cable per device (quantity ASSUMPTION)"), ("COND1", 40, "40 ft conduit per device (quantity ASSUMPTION)")], WAST["cable"], ""),
    ("MX-1109", ELV, "Fire alarm", "Supplying and laying fire alarm / PA cable in riser, complete in all respects", "Rft", "N:144,145", [(674, 1, "FA cable GRN")], WAST["cable"], ""),
    # ---------------------------------------------------------------- ELV: CCTV / data / PA / MATV
    ("MX-1201", ELV, "CCTV", "Providing camera point wiring, Cat-6 UTP in 1\" PVC conduit from RJ45 outlet to patch panel, including outlet and 16 SWG back box, complete in all respects", "Point", "E:444",
     [(27, 60, "60 ft Cat-6 per point (quantity ASSUMPTION)"), ("COND1", 60, "60 ft conduit per point (quantity ASSUMPTION)"), (564, 1, "RJ45 outlet"), (321, 1, "back box")], WAST["cable"], ""),
    ("MX-1202", ELV, "CCTV", "Supplying, installing and commissioning Cat-6 UTP uplink cable on tray / in conduit, complete in all respects", "Rft", "E:445", [(27, 1, "")], WAST["cable"], ""),
    ("MX-1203", ELV, "CCTV", "Supplying, installing, testing and commissioning indoor IP POE 2 MP camera (box / dome), complete in all respects", "Nos", "E:447,448", [(560, 1, "Dahua 2 MP camera GRN used for box and dome")], 0, ""),
    ("MX-1204", ELV, "CCTV", "Supplying, installing, testing and commissioning outdoor IP65 IP POE 4 MP camera, complete in all respects", "Nos", "E:450", [("MEP-Z-CAM4", 1, "")], 0, ""),
    ("MX-1205", ELV, "CCTV", "Supplying, installing, testing and commissioning NVR (32 / 100 cameras) with software, complete in all respects", "Job", "E:452,453", [(561, 1, "32-channel NVR GRN (hotel); mall 100-camera NVR has no GRN")], 0, ""),
    ("MX-1206", ELV, "Networking", "Supplying, installing, testing and commissioning 32-port POE network switch, complete in all respects", "Nos", "E:455,494", [("MEP-Z-SW32", 1, "")], 0, ""),
    ("MX-1207", ELV, "Networking", "Supplying, installing, testing and commissioning 24 / 16-port POE network switch, complete in all respects", "Nos", "E:456,495", [(491, 1, "24-port POE switch GRN")], 0, ""),
    ("MX-1208", ELV, "Networking", "Supplying, installing, testing and commissioning 8-port POE / core network switch, complete in all respects", "Nos", "E:457,458,496,497", [(61, 1, "8-port POE switch GRN")], 0, ""),
    ("MX-1209", ELV, "Networking", "Supplying, installing and terminating Cat-6 patch panel 32-port, complete in all respects", "Nos", "E:460,499", [("MEP-Z-PP32", 1, "")], 0, ""),
    ("MX-1210", ELV, "Networking", "Supplying, installing and terminating Cat-6 patch panel 24 / 16-port, complete in all respects", "Nos", "E:461,500", [("MEP-Z-PP24", 1, "")], 0, ""),
    ("MX-1211", ELV, "Networking", "Supplying, installing and terminating Cat-6 patch panel 8-port, complete in all respects", "Nos", "E:462,501", [("MEP-Z-PP8", 1, "")], 0, ""),
    ("MX-1212", ELV, "Networking", "Supplying and fixing Cat-6 patch cord 1 m long, complete in all respects", "Nos", "E:464,503", [("MEP-Z-PCORD", 1, "")], 0, ""),
    ("MX-1213", ELV, "Networking", "Supplying and installing 42U data cabinet with accessories (network / PA rack), complete in all respects", "Nos", "E:467,485", [("MEP-Z-RACK42", 1, "")], 0, ""),
    ("MX-1214", ELV, "Networking", "Supplying and installing 24U data cabinet with accessories, complete in all respects", "Nos", "E:510", [("MEP-Z-RACK24", 1, "")], 0, ""),
    ("MX-1215", ELV, "Networking", "Supplying, installing, testing and commissioning wireless access point, complete in all respects", "Nos", "E:491", [("MEP-Z-WAP", 1, "")], 0, ""),
    ("MX-1216", ELV, "Networking", "Providing data / telephone outlet wiring, Cat-6 UTP in 1\" PVC conduit to patch panel / POE switch, including RJ45 outlet plate and 16 SWG back box, complete in all respects", "Point", "E:505,529",
     [(27, 60, "60 ft Cat-6 per point (quantity ASSUMPTION)"), ("COND1", 60, "60 ft conduit per point (quantity ASSUMPTION)"), (564, 1, "RJ45 outlet plate"), (321, 1, "back box")], WAST["cable"], ""),
    ("MX-1217", ELV, "Networking", "Providing FCU control wiring with Cat-6 UTP in 1\" PVC / flexible conduit or on tray, complete in all respects", "Point", "N:104",
     [(27, 40, "40 ft Cat-6 per point (quantity ASSUMPTION)"), ("COND1", 40, "40 ft conduit per point (quantity ASSUMPTION)")], WAST["cable"], ""),
    ("MX-1218", ELV, "Networking", "Supplying and laying Cat-6A data cable in riser, complete in all respects", "Rft", "N:146", [("MEP-CAT6A", 1, "")], WAST["cable"], ""),
    ("MX-1301", ELV, "Public address", "Supplying, installing and commissioning 6 W ceiling speaker, complete in all respects", "Nos", "E:473", [("MEP-Z-SPK6", 1, "")], 0, ""),
    ("MX-1302", ELV, "Public address", "Supplying, installing and commissioning 20 W wall-mounted speaker, complete in all respects", "Nos", "E:474", [("MEP-Z-SPK20", 1, "")], 0, ""),
    ("MX-1303", ELV, "Public address", "Installing, testing and commissioning PA head-end equipment (4 × 4 channel amplifier), complete in all respects", "Job", "E:476", [], 0, "Music system is MX-1308."),
    ("MX-1304", ELV, "Public address", "Installing, testing and commissioning 60 W integrated power amplifier, complete in all respects", "Nos", "E:477", [], 0, ""),
    ("MX-1305", ELV, "Public address", "Installing and commissioning 10-zone remote microphone, complete in all respects", "Nos", "E:478", [], 0, ""),
    ("MX-1306", ELV, "Public address", "Providing speaker wiring, 2C 1.5 mm² PVC/PVC in 1\" PVC conduit, complete in all respects", "Point", "E:481",
     [("MEP-SPK2C15", 40, "40 ft speaker cable per point (quantity ASSUMPTION)"), ("COND1", 40, "40 ft conduit per point (quantity ASSUMPTION)")], WAST["cable"], ""),
    ("MX-1307", ELV, "Public address", "Providing speaker wiring through wall-mounted volume controller, including controller and back box, complete in all respects", "Point", "E:482",
     [("MEP-SPK2C15", 40, "40 ft speaker cable per point (quantity ASSUMPTION)"), ("COND1", 40, "40 ft conduit per point (quantity ASSUMPTION)"), ("MEP-Z-VOLC", 1, "volume controller"), (321, 1, "back box")], WAST["cable"], ""),
    ("MX-1501", ELV, "Telephone", "Supplying, fabricating, installing and commissioning 300-pair MDF, complete in all respects", "Nos", "E:517", [], 0, ""),
    ("MX-1502", ELV, "Telephone", "Supplying and installing telephone DB (10 pair), complete in all respects", "Nos", "E:520", [], 0, "30 pair is MX-1503; 40 pair is MX-1504."),
    ("MX-1601", ELV, "RFID door lock", "Installing, testing and commissioning offline RF door lock with RFID reader, complete in all respects", "Nos", "E:538", [], 0, ""),
    ("MX-1602", ELV, "RFID door lock", "Installing and commissioning door-lock / hotel management desktop server, complete in all respects", "Job", "E:540", [], 0, ""),
    ("MX-1701", ELV, "MATV", "Supplying and installing MATV 8-way / 4-way splitter, complete in all respects", "Nos", "E:547,548", [("MEP-Z-SPLIT", 1, "")], 0, ""),
    ("MX-1702", ELV, "MATV", "Supplying, installing and commissioning HDTV booster, complete in all respects", "Nos", "E:550", [("MEP-Z-BOOST", 1, "")], 0, ""),
    ("MX-1703", ELV, "MATV", "Supplying, installing and commissioning 4-channel combiner mixer, complete in all respects", "Nos", "E:552", [], 0, ""),
    ("MX-1704", ELV, "MATV", "Supplying, installing and commissioning RG-11 co-axial riser cable on tray, complete in all respects", "Rft", "E:554", [("MEP-RG11", 1, "")], WAST["cable"], ""),
    ("MX-1705", ELV, "MATV", "Providing TV outlet wiring, RG-6 co-axial in 1\" PVC conduit, including TV outlet plate and back box, complete in all respects", "Point", "E:555",
     [("MEP-RG6", 50, "50 ft RG-6 per point (quantity ASSUMPTION)"), ("COND1", 50, "50 ft conduit per point (quantity ASSUMPTION)"), (1615, 1, "TV outlet"), (321, 1, "back box")], WAST["cable"], ""),
    ("MX-1706", ELV, "MATV", "Supplying and installing 16 SWG MS TV junction box, complete in all respects", "Nos", "E:557", [], 0, ""),
    # ---------------------------------------------------------------- plumbing fixtures
    ("MP-101", PL, "Sanitary ware", "Providing and fixing European WC with muslim shower, tee stop cock, flush and connections, complete in all respects", "Nos", "P:9", [("SAN-WC", 1, "WC suite rate line of the Rate Database")], 0, ""),
    ("MP-102", PL, "Core cutting", "Cutting RCC slab with core cutter for pipe crossings, complete in all respects", "Nos", "P:11", [], 0, "Core cutting by size band is MP-102A to MP-102D."),
    ("MP-103", PL, "Sanitary ware", "Providing and fixing under-counter wash hand basin vanity with basin mixer, waste coupling, bottle trap and tee stop cock, complete in all respects", "Nos", "P:14", [("SAN-WB", 1, "wash basin set rate line of the Rate Database")], 0, ""),
    ("MP-104", PL, "Sanitary ware", "Providing and fixing pedestal wash hand basin with basin mixer, waste coupling and tee stop cock, complete in all respects", "Nos", "P:22",
     [(1723, 1, "basin with pedestal"), (384, 1, "basin mixer"), (1583, 1, "tee stop cock"), (1727, 1, "waste coupling")], 0, ""),
    ("MP-105", PL, "Sanitary ware", "Providing and fixing kitchen sink with mixer, waste coupling and tee stop cock, complete in all respects", "Nos", "P:29",
     [("MEP-Z-SINK", 1, "kitchen sink"), (1453, 1, "sink mixer"), (1727, 1, "waste coupling"), (1583, 1, "tee stop cock")], 0, ""),
    ("MP-106", PL, "Sanitary ware", "Providing and fixing shower mixer with shower head, complete set with interconnecting pipe, complete in all respects", "Nos", "P:36", [(1437, 1, "")], 0, ""),
    ("MP-107", PL, "Accessories", "Providing and fixing soap dispenser, complete in all respects", "Nos", "P:41", [("MEP-Z-SOAPD", 1, "")], 0, ""),
    ("MP-108", PL, "Accessories", "Providing and fixing CP toilet paper holder, complete in all respects", "Nos", "P:45", [(1606, 1, "")], 0, ""),
    ("MP-109", PL, "Accessories", "Providing and fixing 5 mm first-quality looking glass with fixing clamps, complete in all respects", "Sft", "P:50", [("MEP-Z-MIRROR", 1, "")], 5, ""),
    ("MP-110", PL, "Accessories", "Providing and fixing soap dish, complete in all respects", "Nos", "P:54", [(1457, 1, "")], 0, ""),
    ("MP-111", PL, "Accessories", "Providing and fixing towel rod, complete in all respects", "Nos", "P:58", [(1607, 1, "towel ring GRN used for towel rod")], 0, ""),
    ("MP-112", PL, "Accessories", "Providing and fixing 3/4\" tap, complete in all respects", "Nos", "P:62", [("MEP-Z-TAP", 1, "")], 0, ""),
    ("MP-113", PL, "Accessories", "Providing and fixing ablution tap mixer, complete in all respects", "Nos", "P:67", [("MEP-Z-ABL", 1, "")], 0, ""),
    # ---------------------------------------------------------------- water supply
    ("MP-201A", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 25 mm dia with fittings and supports, complete in all respects", "Rft", "P:71,72", pipe(1298, "PPR"), WAST["pipe"], ""),
    ("MP-201B", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 32 mm dia with fittings and supports, complete in all respects", "Rft", "P:73,74", pipe(1299, "PPR"), WAST["pipe"], ""),
    ("MP-201C", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 40 mm dia with fittings and supports, complete in all respects", "Rft", "P:75,76", pipe(1300, "PPR"), WAST["pipe"], ""),
    ("MP-201D", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 50 mm dia with fittings and supports, complete in all respects", "Rft", "P:77,78", pipe(1295, "PPR"), WAST["pipe"], ""),
    ("MP-201E", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 63 mm dia with fittings and supports, complete in all respects", "Rft", "P:79", pipe(1301, "PPR"), WAST["pipe"], ""),
    ("MP-201F", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 75 mm dia with fittings and supports, complete in all respects", "Rft", "P:80", [("MEP-Z-PPR75", 1, "")], WAST["pipe"], ""),
    ("MP-201G", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 90 mm dia with fittings and supports, complete in all respects", "Rft", "P:83", pipe(1297, "PPR"), WAST["pipe"], "Installation rate pro-rata from 110 mm (bill)."),
    ("MP-201H", PL, "Water supply", "Providing, fixing, jointing and testing PPR PN20 pipe 110 mm dia with fittings and supports, complete in all respects", "Rft", "P:81,82", pipe(1291, "PPR"), WAST["pipe"], ""),
    ("MP-202A", PL, "Insulation", "Providing and laying Armaflex insulation on 25 mm hot water pipe, complete in all respects", "Rft", "P:86", ins(1.0, "25 mm"), WAST["pipe"], "BOQ installation rate 334.65 is out of line with 32 mm (43.65) — likely a BOQ error; check before use."),
    ("MP-202B", PL, "Insulation", "Providing and laying Armaflex insulation on 32 mm hot water pipe, complete in all respects", "Rft", "P:87", ins(1.26, "32 mm"), WAST["pipe"], ""),
    ("MP-202C", PL, "Insulation", "Providing and laying Armaflex insulation on 40 mm hot water pipe, complete in all respects", "Rft", "P:88", ins(1.575, "40 mm"), WAST["pipe"], ""),
    ("MP-202D", PL, "Insulation", "Providing and laying Armaflex insulation on 50 mm hot water pipe, complete in all respects", "Rft", "P:89", ins(1.969, "50 mm"), WAST["pipe"], ""),
    ("MP-203A", PL, "Valves", "Providing and installing gate / ball valve 25 mm (3/4\") with jointing, complete in all respects", "Nos", "P:93", [(380, 1, "3/4\" ball valve GRN")], 0, ""),
    ("MP-203B", PL, "Valves", "Providing and installing gate / ball valve 32 mm (1\") with jointing, complete in all respects", "Nos", "P:94", [(379, 1, "1\" ball valve GRN")], 0, ""),
    ("MP-203C", PL, "Valves", "Providing and installing gate / ball valve 40 mm (1-1/4\") with jointing, complete in all respects", "Nos", "P:95", [(708, 1, "1-1/2\" threaded gate valve GRN (no 1-1/4\" receipt)")], 0, ""),
    ("MP-203D", PL, "Valves", "Providing and installing gate / ball valve 50 mm (1-1/2\") with jointing, complete in all respects", "Nos", "P:96", [(708, 1, "1-1/2\" threaded gate valve GRN")], 0, ""),
    ("MP-203E", PL, "Valves", "Providing and installing gate / ball valve 110 mm (4\") with jointing, complete in all respects", "Nos", "P:97", [(1054, 1, "4\" MS gate valve R/F PN-16 GRN")], 0, ""),
    ("MP-204A", PL, "Valves", "Providing, installing, testing and commissioning pressure reducing valve assembly, 32 mm inlet, complete in all respects", "Nos", "P:101", [("MEP-Z-PRV32", 1, "")], 0, ""),
    ("MP-204B", PL, "Valves", "Providing, installing, testing and commissioning pressure reducing valve assembly, 40 mm inlet, complete in all respects", "Nos", "P:102", [(417, 1, "1-1/2\" brass PRV GRN")], 0, ""),
    ("MP-204C", PL, "Valves", "Providing, installing, testing and commissioning pressure reducing valve assembly, 50 mm inlet, complete in all respects", "Nos", "P:103", [("MEP-Z-PRV50", 1, "")], 0, ""),
    ("MP-204D", PL, "Valves", "Providing, installing, testing and commissioning pressure reducing valve assembly, 63 mm inlet, complete in all respects", "Nos", "P:104", [("MEP-Z-PRV63", 1, "")], 0, ""),
    # ---------------------------------------------------------------- drainage
    ("MP-301A", PL, "Drainage", "Providing, fixing, jointing and testing uPVC pipe 2\" (BS EN 1329) with fittings, clamps and hangers, complete in all respects", "Rft", "P:110", pipe(1681, "UPVC"), WAST["pipe"], ""),
    ("MP-301B", PL, "Drainage", "Providing, fixing, jointing and testing uPVC pipe 3\" (BS EN 1329) with fittings, clamps and hangers, complete in all respects", "Rft", "P:111", pipe(1691, "UPVC"), WAST["pipe"], ""),
    ("MP-301C", PL, "Drainage", "Providing, fixing, jointing and testing uPVC pipe 4\" (BS EN 1329) with fittings, clamps and hangers, complete in all respects", "Rft", "P:112,113", pipe(1682, "UPVC"), WAST["pipe"], ""),
    ("MP-301D", PL, "Drainage", "Providing, fixing, jointing and testing uPVC pipe 8\" (BS EN 1329) with fittings, clamps and hangers, complete in all respects", "Rft", "P:114", pipe(1669, "UPVC"), WAST["pipe"], ""),
    ("MP-301E", PL, "Drainage", "Providing, fixing, jointing and testing uPVC pressure pipe 2\" Class D with fittings, complete in all respects", "Rft", "P:117", pipe(1675, "UPVC"), WAST["pipe"], ""),
    ("MP-301F", PL, "Drainage", "Providing and installing uPVC pipe 12\" dia (pro-rata of 4\"), complete in all respects", "Rft", "N:171", [("MEP-Z-UPVC12", 1, "")], WAST["pipe"], ""),
    ("MP-302", PL, "Drainage", "Providing and laying Armawave sound insulation on 4\" uPVC pipe, complete in all respects", "Rft", "P:121", [("MEP-Z-ARMAW", 1, "")], WAST["pipe"], ""),
    ("MP-303", PL, "Drainage", "Providing and fixing 4\" floor drain with P-trap and stainless steel grating, complete in all respects", "Nos", "P:123", [(685, 1, "6\"×6\" floor drain GRN")], 0, ""),
    ("MP-304", PL, "Drainage", "Providing and fixing stainless steel grease trap, complete in all respects", "Nos", "P:128", [("MEP-Z-GTRAP", 1, "")], 0, ""),
    ("MP-305", PL, "Drainage", "Providing and fixing clean-out for uPVC pipe with stainless steel cover plate, including core cutting, complete in all respects", "Nos", "P:130", [(1635, 1, "4\" uPVC clean-out GRN; SS cover not in GRN")], 0, ""),
    # ---------------------------------------------------------------- misc plumbing / gas / equipment
    ("MP-501", PL, "Tanks", "Providing and placing sleeves and puddle flanges in RCC water tank walls with GI inlet / outlet pipework, manhole covers and float valve (UG or OH tank), complete in all respects", "Job", "P:193,196", [], 0, ""),
    ("MP-503", PL, "Tanks", "Providing and placing sleeves in RCC septic tank walls with inlet / outlet pipework, complete in all respects", "Nos", "P:198", [], 0, ""),
    ("MP-701A", PL, "Gas", "Providing, fixing, jointing and testing GI pipe 1\" with fittings (LPG), complete in all respects", "Rft", "P:220", [("MEP-Z-GI1", 1, "")], WAST["pipe"], ""),
    ("MP-701B", PL, "Gas", "Providing, fixing, jointing and testing GI pipe 2\" with fittings (LPG), complete in all respects", "Rft", "P:221", [("MEP-Z-GI2", 1, "")], WAST["pipe"], ""),
    ("MP-702A", PL, "Gas", "Providing and installing gas ball valve 1\", complete in all respects", "Nos", "P:223;N:265,266", [(379, 1, "1\" ball valve GRN")], 0, "Gas burner connection and 1\" solenoid valve (Non-BOQ #9) billed at this rate."),
    ("MP-702B", PL, "Gas", "Providing and installing gas ball valve 2\", complete in all respects", "Nos", "P:224", [(711, 1, "2\" brass gate valve GRN")], 0, ""),
    ("MP-801", PL, "Equipment", "Installing, testing and commissioning Employer-supplied water transfer pump set, complete in all respects", "Set", "P:235", [], 0, "Indicative supply price: Quadrangle GRN RCP-2381, 05-Mar-2025 — Water Transfer Pump 885,000."),
    ("MP-802", PL, "Equipment", "Installing, testing and commissioning Employer-supplied water pressure boosting system with VFD panel, complete in all respects", "Set", "P:239", [], 0, "Indicative supply price: Quadrangle GRN RCP-2381, 05-Mar-2025 — Water Supply Booster 472,000."),
    ("MP-803", PL, "Equipment", "Installing, testing and commissioning Employer-supplied hot water generator, complete in all respects", "Nos", "P:242", [], 0, ""),
    ("MP-804", PL, "Equipment", "Installing, testing and commissioning Employer-supplied hot water circulation pump, complete in all respects", "Nos", "P:244", [], 0, ""),
    ("MP-805", PL, "Equipment", "Installing, testing and commissioning Employer-supplied twin-tank automatic water softener, complete in all respects", "Set", "P:247", [], 0, ""),
    ("MP-806", PL, "Equipment", "Installing, testing and commissioning Employer-supplied multimedia filter (duplex / triplex), complete in all respects", "Set", "P:251", [], 0, ""),
    ("MP-807", PL, "Equipment", "Installing, testing and commissioning Employer-supplied submersible drainage sump pump set, complete in all respects", "Set", "P:253,255", [], 0, "Indicative supply price: Quadrangle GRN RCP-2381, 05-Mar-2025 — Submersible Pump for Drainage 200,128."),
    ("MP-808", PL, "Testing", "Testing and rectification of executed plumbing works, complete in all respects", "Job", "P:257", [], 0, ""),
    ("MP-809", PL, "Equipment", "Installing submersible pump (Non-BOQ #7), complete in all respects", "Nos", "N:228", [], 0, ""),
    ("MP-810", PL, "Equipment", "Installing electric geyser in kitchen, complete in all respects", "Nos", "N:273", [(675, 1, "Fischer 15 litre instant geyser GRN")], 0, ""),
    ("MP-811", PL, "Valves", "Installing PVC ball / check valve 2\" on submersible pump line, complete in all respects", "Nos", "N:271,272", [], 0, ""),
    ("MP-812", PL, "Valves", "Installing solenoid valve 1-1/2\" in kitchen gas line, complete in all respects", "Nos", "N:267", [], 0, ""),
    # ---------------------------------------------------------------- fire fighting
    ("MF-401A", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 1\" with fittings, supports and red paint, complete in all respects", "Rft", "P:140,141", pipe(1063, "MS"), WAST["pipe"], ""),
    ("MF-401B", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 1-1/4\" with fittings, supports and red paint, complete in all respects", "Rft", "P:142,143", pipe(1065, "MS"), WAST["pipe"], ""),
    ("MF-401C", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 1-1/2\" with fittings, supports and red paint, complete in all respects", "Rft", "P:144,145", pipe(1064, "MS"), WAST["pipe"], ""),
    ("MF-401D", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 2\" with fittings, supports and red paint, complete in all respects", "Rft", "P:146,147", pipe(1066, "MS"), WAST["pipe"], ""),
    ("MF-401E", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 2-1/2\" with fittings, supports and red paint, complete in all respects", "Rft", "P:148,149", pipe(1067, "MS"), WAST["pipe"], ""),
    ("MF-401F", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 3\" with fittings, supports and red paint, complete in all respects", "Rft", "P:150,151", pipe(1068, "MS"), WAST["pipe"], ""),
    ("MF-401G", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 4\" with fittings, supports and red paint, complete in all respects", "Rft", "P:152,153", pipe(1072, "MS"), WAST["pipe"], ""),
    ("MF-401H", FF, "Piping", "Providing, fixing and testing MS Sch-40 seamless pipe 6\" with fittings, supports and red paint, complete in all respects", "Rft", "P:154", pipe(1069, "MS"), WAST["pipe"], ""),
    ("MF-402A", FF, "Valves", "Providing and installing UL-listed gate / ball valve 1\", complete in all respects", "Nos", "P:157", [(413, 1, "1\" brass gate valve GRN")], 0, ""),
    ("MF-402B", FF, "Valves", "Providing and installing UL-listed gate / ball valve 1-1/4\", complete in all respects", "Nos", "P:158", [("MEP-Z-GV125", 1, "")], 0, ""),
    ("MF-402C", FF, "Valves", "Providing and installing UL-listed gate / ball valve 1-1/2\", complete in all respects", "Nos", "P:159", [(708, 1, "")], 0, ""),
    ("MF-402D", FF, "Valves", "Providing and installing UL-listed gate / ball valve 2\", complete in all respects", "Nos", "P:160", [(711, 1, "")], 0, ""),
    ("MF-402E", FF, "Valves", "Providing and installing UL-listed gate / ball valve 2-1/2\" flanged, complete in all respects", "Nos", "P:161", [(709, 1, "")], 0, ""),
    ("MF-402F", FF, "Valves", "Providing and installing UL-listed gate / ball valve 3\" flanged, complete in all respects", "Nos", "P:162", [(1053, 1, "3\" MS gate valve R/F PN-16 GRN")], 0, ""),
    ("MF-402G", FF, "Valves", "Providing and installing UL-listed gate valve 4\" flanged, indicating type, complete in all respects", "Nos", "P:163", [(598, 1, "")], 0, ""),
    ("MF-402H", FF, "Valves", "Providing and installing UL-listed gate valve 6\" flanged, complete in all respects", "Nos", "P:164", [(1055, 1, "6\" MS gate valve R/F PN-16 GRN")], 0, ""),
    ("MF-404A", FF, "Sprinklers", "Providing, installing and testing upright sprinkler K5.6, complete in all respects", "Nos", "P:170", [(1471, 1, "")], 0, ""),
    ("MF-404B", FF, "Sprinklers", "Providing, installing and testing concealed ceiling sprinkler K5.6, complete in all respects", "Nos", "P:171", [(1476, 1, "")], 0, ""),
    ("MF-404C", FF, "Sprinklers", "Providing, installing and testing sidewall sprinkler K5.6, complete in all respects", "Nos", "P:172", [("MEP-Z-SPRSW", 1, "")], 0, ""),
    ("MF-405", FF, "Hydrants", "Providing, installing, testing and commissioning pillar-type fire hydrant with external hose cabinet, complete in all respects", "Nos", "P:174", [(673, 1, "")], 0, ""),
    ("MF-406", FF, "Hydrants", "Providing, installing, testing and commissioning fire brigade (Siamese) inlet connection, complete in all respects", "Nos", "P:176", [(418, 1, "4\" 2-way breeching inlet GRN")], 0, ""),
    ("MF-407", FF, "Hose cabinets", "Providing, installing, testing and commissioning double-door fire hose cabinet, complete in all respects", "Nos", "P:178", [(1041, 1, "MS fire hose cabinet (two layers) GRN")], 0, ""),
    ("MF-408A", FF, "Valves", "Providing, installing, testing and commissioning zone check assembly 4\" (alarm valve, flow switch, gauges, drain), complete in all respects", "Nos", "P:181", [(1773, 1, "")], 0, ""),
    ("MF-408B", FF, "Valves", "Providing, installing, testing and commissioning zone check / alarm check valve assembly 6\", complete in all respects", "Nos", "P:182", [(1774, 1, "")], 0, ""),
    ("MF-409", FF, "Piping", "Providing, installing, testing and commissioning fire fighting drain / test point, complete in all respects", "Nos", "P:184", [], 0, ""),
    ("MF-410A", FF, "Extinguishers", "Providing and fixing portable DCP / CO2 fire extinguisher, complete in all respects", "Nos", "P:187,188", [("MEP-Z-EXT", 1, "")], 0, ""),
    ("MF-410B", FF, "Extinguishers", "Providing and fixing ceiling-hanging automatic fire extinguisher for electrical rooms, complete in all respects", "Nos", "P:189", [("MEP-Z-EXTC", 1, "")], 0, ""),
    ("MF-801", FF, "Equipment", "Installing, testing and commissioning Employer-supplied fire pump set (electric, diesel, jockey) with pump-room valves and controls, complete in all respects", "Set", "P:233", [], 0, "Indicative supply price: Quadrangle GRN RCP-2381, 05-Mar-2025 — Fire Fighting Pumps Set 5,975,000."),
    ("MF-901", FF, "Pressure gauges", "Providing and installing pressure gauge with fire hose cabinet / ZCVA, complete in all respects", "Nos", "N:277", [(1334, 1, "4\" dial 12 bar gauge GRN")], 0, ""),
    # ---------------------------------------------------------------- HVAC equipment
    ("MH-101", HV, "Equipment", "Installing, testing and commissioning Employer-supplied VFD water-cooled chiller, complete in all respects", "Nos", "H:10", [], 0, ""),
    ("MH-102", HV, "Equipment", "Installing, testing and commissioning Employer-supplied induced-draft cooling tower, complete in all respects", "Nos", "H:13", [], 0, ""),
    ("MH-103", HV, "Equipment", "Installing, testing and commissioning Employer-supplied double-skin air handling unit (2,900–4,450 CFM), complete in all respects", "Nos", "H:17,18,19,20,21,22", [], 0, ""),
    ("MH-104", HV, "Equipment", "Installing, testing and commissioning Employer-supplied ceiling concealed ducted fan coil unit (250–3,236 CFM), complete in all respects", "Nos", "H:26,27,28,29,30,31,32,33,34,35,36,37,38,39,40", [], 0, ""),
    ("MH-105", HV, "Equipment", "Installing, testing and commissioning Employer-supplied dual-fuel hot water generator, complete in all respects", "Nos", "H:44", [], 0, ""),
    ("MH-106", HV, "Equipment", "Installing, testing and commissioning Employer-supplied end-suction chilled / condenser water pump, complete in all respects", "Nos", "H:49,50,51", [], 0, ""),
    ("MH-107A", HV, "Ventilation", "Installing, testing and commissioning Employer-supplied parking exhaust fan (10,000 CFM class), complete in all respects", "Nos", "H:54,55", [], 0, "Indicative supply price: Quadrangle GRN RCP-2698, 25-Aug-2025 — tube axial fan 13,500 CFM fire-rated 822,214."),
    ("MH-107B", HV, "Ventilation", "Installing, testing and commissioning Employer-supplied 1,500 CFM supply / exhaust fan (and shifting of 1,500–1,800 CFM fans), complete in all respects", "Nos", "H:56,57,58,59,60,65,66,67,68,69", [], 0,
     "Indicative supply price: Quadrangle GRN RCP-2698, 25-Aug-2025 — centrifugal cabinet fan 1,800 CFM 225,630."),
    ("MH-107C", HV, "Ventilation", "Installing, testing and commissioning Employer-supplied 200–250 CFM exhaust fan, complete in all respects", "Nos", "H:61,62,63,64", [], 0, "Indicative supply price: Quadrangle GRN RCP-2698, 25-Aug-2025 — wall propeller fan 200 CFM 37,340."),
    ("MH-108", HV, "Equipment", "Installing Employer-supplied centrifugal air separator / expansion tank, complete in all respects", "Nos", "H:72,75", [], 0, ""),
    ("MH-109A", HV, "Water treatment", "Supplying and installing chemical feeder with chemicals for chilled / hot water system, complete in all respects", "Job", "H:78", [], 0, ""),
    ("MH-109B", HV, "Water treatment", "Supplying and installing chemical feeder with chemicals for condenser water system, complete in all respects", "Job", "H:79", [], 0, ""),
    # ---------------------------------------------------------------- HVAC pipework
    ("MH-201A", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 3/4\" with fittings and supports, complete in all respects", "Rft", "H:83", [("MEP-Z-MS075", 1, "")], WAST["pipe"], ""),
    ("MH-201B", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 1\" with fittings and supports, complete in all respects", "Rft", "H:84,85", pipe(1063, "MS"), WAST["pipe"], ""),
    ("MH-201C", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 1-1/4\" with fittings and supports, complete in all respects", "Rft", "H:86,87", pipe(1065, "MS"), WAST["pipe"], ""),
    ("MH-201D", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 1-1/2\" with fittings and supports, complete in all respects", "Rft", "H:88", pipe(1064, "MS"), WAST["pipe"], ""),
    ("MH-201E", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 2\" with fittings and supports, complete in all respects", "Rft", "H:89,90", pipe(1066, "MS"), WAST["pipe"], ""),
    ("MH-201F", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 2-1/2\" with fittings and supports, complete in all respects", "Rft", "H:91,92", pipe(1067, "MS"), WAST["pipe"], ""),
    ("MH-201G", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 3\" with fittings and supports, complete in all respects", "Rft", "H:93,94", pipe(1068, "MS"), WAST["pipe"], ""),
    ("MH-201H", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 4\" with fittings and supports, complete in all respects", "Rft", "H:95,96", pipe(1072, "MS"), WAST["pipe"], ""),
    ("MH-201J", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 6\" with fittings and supports, complete in all respects", "Rft", "H:97", pipe(1069, "MS"), WAST["pipe"], ""),
    ("MH-201K", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 8\" with fittings and supports, complete in all respects", "Rft", "H:98", [("MEP-Z-MS8", 1, "")], WAST["pipe"], ""),
    ("MH-201L", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 10\" with fittings and supports, complete in all respects", "Rft", "H:99", [("MEP-Z-MS10", 1, "")], WAST["pipe"], ""),
    ("MH-201M", HV, "Chilled water piping", "Providing, fixing and testing MS Sch-40 seamless chilled water pipe 12\" with fittings and supports, complete in all respects", "Rft", "H:100", [("MEP-Z-MS12", 1, "")], WAST["pipe"], ""),
    ("MH-218A", HV, "Condensate piping", "Supplying and installing uPVC Class E condensate pipe 3/4\" with fittings and hangers, complete in all respects", "Rft", "H:103", pipe(1640, "UPVC"), WAST["pipe"], ""),
    ("MH-218B", HV, "Condensate piping", "Supplying and installing uPVC Class E condensate pipe 1\" with fittings and hangers, complete in all respects", "Rft", "H:104", [("MEP-Z-UE1", 1, "")], WAST["pipe"], ""),
    ("MH-218C", HV, "Condensate piping", "Supplying and installing uPVC Class E condensate pipe 2\" with fittings and hangers, complete in all respects", "Rft", "H:105", [("MEP-Z-UE2", 1, "")], WAST["pipe"], ""),
]

# Valves / strainers / flex connectors on chilled water, by size (threaded bronze)
_TH = [("075", '3/4"', "109", "115", "120", "127", "133", "139"),
       ("100", '1"', "110", "116", "121", "128", "134", "140"),
       ("125", '1-1/4"', "111", "117", "122", "129", "135", "141"),
       ("150", '1-1/2"', "112", "118", "123", "130", "136", "142"),
       ("200", '2"', None, None, "124", "131", "137", "143")]
_GV = {"075": ("MEP-Z-GV075", ""), "100": (413, '1" brass gate valve GRN'), "125": ("MEP-Z-GV125", ""),
       "150": (708, ""), "200": (711, "")}
_BV = {"075": (380, '3/4" ball valve GRN'), "100": (379, '1" ball valve GRN'), "125": ("MEP-Z-BV125", ""),
       "150": ("MEP-Z-BV150", "")}
for k, sz, gv, bv, picv, strn, mv, flex in _TH:
    if gv:
        ITEMS.append((f"MH-219A-{k}", HV, "Valves", f"Supplying and installing threaded bronze gate valve {sz} on chilled water line, complete in all respects", "Nos", f"H:{gv}", [(_GV[k][0], 1, _GV[k][1])], 0, ""))
    if bv:
        ITEMS.append((f"MH-219B-{k}", HV, "Valves", f"Supplying and installing threaded bronze ball valve {sz}, complete in all respects", "Nos", f"H:{bv}", [(_BV[k][0], 1, _BV[k][1])], 0, ""))
    ITEMS.append((f"MH-219C-{k}", HV, "Valves", f"Supplying and installing pressure-independent control valve (PICV) {sz}, complete in all respects", "Nos", f"H:{picv}", [(f"MEP-Z-PICV{k}", 1, "")], 0, ""))
    ITEMS.append((f"MH-219D-{k}", HV, "Valves", f"Supplying and installing threaded Y-strainer {sz}, complete in all respects", "Nos", f"H:{strn}", [(f"MEP-Z-YS{k}", 1, "")], 0, ""))
    ITEMS.append((f"MH-219E-{k}", HV, "Valves", f"Supplying and installing motorised (2-way) valve {sz}, complete in all respects", "Nos", f"H:{mv}", [(f"MEP-Z-MV{k}", 1, "")], 0, ""))
    ITEMS.append((f"MH-220-{k}", HV, "Valves", f"Supplying and installing 4 ft insulated flexible pipe connector {sz} with flare nuts for terminal unit, complete in all respects", "Nos", f"H:{flex}", [(f"MEP-Z-FX{k}", 1, "")], 0, ""))
ITEMS.append(("MH-219B-050", HV, "Valves", "Supplying and installing threaded bronze ball valve 1/2\", complete in all respects", "Nos", "H:114", [("MEP-Z-BV050", 1, "")], 0, ""))

ITEMS += [
    ("MH-221A", HV, "Valves", "Supplying and installing flanged ductile iron gate valve 2\", complete in all respects", "Nos", "H:146", [(711, 1, '2" brass gate valve GRN')], 0, ""),
    ("MH-221B", HV, "Valves", "Supplying and installing flanged ductile iron gate valve 3\", complete in all respects", "Nos", "H:147", [(1053, 1, "")], 0, ""),
    ("MH-221C", HV, "Valves", "Supplying and installing flanged ductile iron gate valve 4\", complete in all respects", "Nos", "H:148", [(1054, 1, "")], 0, ""),
    ("MH-221D", HV, "Valves", "Supplying and installing flanged gate valve / PICV / check valve / Y-strainer / bellow connector 6\", complete in all respects", "Nos", "H:125,149", [(1055, 1, "6\" MS gate valve GRN")], 0, "6\" check valve, Y-strainer and bellow connector are billed at 2,446.63 — see MH-221F."),
    ("MH-221E", HV, "Valves", "Supplying and installing flanged ductile iron gate valve 8\", complete in all respects", "Nos", "H:150", [("MEP-Z-GV8", 1, "")], 0, "10\" valve is MH-221H."),
    ("MH-221F", HV, "Valves", "Supplying and installing 6\" swing check valve / Y-strainer / bellow-type flexible connector, complete in all respects", "Nos", "H:154,157,159", [(1768, 1, "6\" Y-strainer GRN used as the reference fitting")], 0, ""),
    ("MH-221G", HV, "Valves", "Installing 4\" strainer / check valve in pump room, complete in all respects", "Nos", "N:268,269", [(1767, 1, "4\" Y-strainer GRN")], 0, ""),
    ("MH-223", HV, "Accessories", "Supplying and installing 1\" drain cock, complete in all respects", "Nos", "H:161", [("MEP-Z-DCOCK", 1, "")], 0, ""),
    ("MH-224", HV, "Accessories", "Supplying and installing automatic air vent, complete in all respects", "Nos", "H:163", [("MEP-Z-AAV", 1, "")], 0, ""),
    ("MH-225", HV, "Accessories", "Supplying and installing dial pressure gauge 0–150 psi / pipe thermometer / gas pressure gauge, complete in all respects", "Nos", "H:164,165,166", [(1334, 1, "4\" dial pressure gauge GRN (thermometer has no GRN)")], 0, ""),
    # ---------------------------------------------------------------- HVAC insulation
    ("MH-228", HV, "Insulation", "Supplying and installing 3/4\" elastomeric closed-cell insulation with fibreglass cloth on air separator / expansion tank, complete in all respects", "Sft", "H:170", [("MEP-NBR19", 1, "")], WAST["pipe"], ""),
    ("MH-229", HV, "Insulation", "Supplying and installing 1/2\" elastomeric closed-cell insulation on indoor ducts, complete in all respects", "Sft", "H:172", [("MEP-Z-NBR13", 1, "")], WAST["pipe"], "Only 3/4\" sheet has a GRN (MEP-NBR19)."),
    ("MH-230", HV, "Insulation", "Supplying and installing 3\" rock wool insulation on kitchen exhaust duct / restaurant area, complete in all respects", "Sft", "H:173", [(1402, 1, "")], WAST["pipe"], ""),
]
for rows, od, sz in [("175", 1.05, '3/4"'), ("176", 1.315, '1"'), ("177", 1.66, '1-1/4"'), ("178", 1.9, '1-1/2"'),
                     ("179", 2.375, '2"'), ("180", 2.875, '2-1/2"'), ("181", 3.5, '3"'), ("182", 4.5, '4"'),
                     ("183", 6.625, '6"'), ("184", 8.625, '8"'), ("185", 10.75, '10"'), ("186", 12.75, '12"')]:
    ITEMS.append((f"MH-231-{sz.replace('/', '').replace('-', '').replace(chr(34), '')}", HV, "Insulation",
                  f"Supplying and installing elastomeric closed-cell insulation with fibreglass cloth on chilled water pipe {sz}, complete in all respects",
                  "Rft", f"H:{rows}", ins(od, sz), WAST["pipe"], "Material taken at 3/4\" sheet; thicker schedules cost more."))
ITEMS += [
    ("MH-232A", HV, "Insulation", "Supplying and installing 1/4\" polyethylene (Jumbolon) insulation with GI tape on condensate pipe 2\", complete in all respects", "Rft", "H:189", [("MEP-Z-PE6", 1, "")], WAST["pipe"], "1\" pipe is MH-232B; 3\" pipe is MH-232C."),
    ("MH-233", HV, "Insulation", "Supplying and installing 26 gauge GI sheet cladding over exposed duct and pipe insulation, complete in all respects", "Sft", "H:191", [("MEP-GI26", 1.1, "1.10 Sft of sheet per Sft (laps and seams)")], WAST["pipe"], ""),
    # ---------------------------------------------------------------- air distribution
    ("MH-301", HV, "Ductwork", "Supplying, fabricating and installing G-60 / Z-180 GI sheet ductwork 26 gauge with splitter dampers, bracings and hangers, complete in all respects", "Sft", "H:208,209", [("MEP-GI26", 1.15, "1.15 Sft of sheet per Sft of duct surface (seams, locks, stiffeners — quantity ASSUMPTION)")], WAST["pipe"], "Measured on duct surface area. Hangers and sealant not included in material."),
    ("MH-302", HV, "Ductwork", "Supplying and installing round insulated flexible duct with jubilee clamps, complete in all respects", "Rft", "H:216", [(365, 1, "aluminium flexible duct 6\" GRN (uninsulated)")], WAST["pipe"], "Billed per Rft (unit printed 'job' in the bill)."),
    ("MH-303", HV, "Air devices", "Supplying and installing 2\" washable aluminium filter, complete in all respects", "Sft", "H:221", [("MEP-Z-ALF", 1, "")], 0, ""),
    ("MH-304A", HV, "Air devices", "Supplying and installing aluminium supply / return / fresh air diffuser, complete in all respects", "Sft", "H:223", [("MEP-Z-DIFF", 1, "")], 0, "GRN has only a 6\"×6\" 4-way diffuser (2,360 each = 9,440/Sft) — not representative of typical sizes, so not used."),
    ("MH-304B", HV, "Air devices", "Supplying and installing aluminium supply / return / fresh air grille, complete in all respects", "Sft", "H:224", [(852, 0.444, "18\"×18\" grille GRN = 2.25 Sft → 1 ÷ 2.25 = 0.444 Nos per Sft")], 0, ""),
    ("MH-304C", HV, "Air devices", "Supplying and installing fresh / exhaust air louvre with insect screen, complete in all respects", "Sft", "H:225", [(978, 0.075, "40\"×48\" louvre GRN = 13.333 Sft → 1 ÷ 13.333 = 0.075 Nos per Sft")], 0, ""),
    ("MH-304D", HV, "Air devices", "Supplying and installing wire mesh on air openings, complete in all respects", "Sft", "H:226", [("MEP-Z-MESH", 1, "")], 0, ""),
    ("MH-304E", HV, "Air devices", "Supplying and installing return linear grille, complete in all respects", "Rft", "H:227", [("MEP-Z-RLG", 1, "")], 0, ""),
    ("MH-305", HV, "Air devices", "Supplying and installing 18 gauge GI volume control damper, complete in all respects", "Sft", "H:229", [(1709, 0.545, "22\"×12\" VCD GRN = 1.833 Sft → 1 ÷ 1.833 = 0.545 Nos per Sft")], 0, ""),
    ("MH-306", HV, "Ductwork", "Supplying and installing pre-assembled flexible duct connector, coated woven fabric with GI collars, complete in all respects", "Rft", "H:230", [("MEP-Z-FDC", 1, "")], 0, ""),
    # ---------------------------------------------------------------- HVAC misc / testing
    ("MH-401", HV, "General", "Painting and equipment identification of HVAC system, complete in all respects", "Job", "H:195", [], 0, ""),
    ("MH-402", HV, "General", "Preparing shop drawings and as-built drawings for HVAC works, complete in all respects", "Job", "H:197", [], 0, ""),
    ("MH-403", HV, "Testing", "Testing and rectification of executed HVAC works, complete in all respects", "Job", "H:232", [], 0, ""),
    ("MH-404", HV, "Testing", "Water and air balancing of complete system (work order 130524-01), complete in all respects", "Job", "N:297", [], 0, ""),
]

# ---------------------------------------------------------------- Non-BOQ labour items
NB = [
    ("MN-E01", E, "Rework", "Dismantling and re-installing 3\"×3\" / 6\"×3\" back box", "Nos", "N:9,10"),
    ("MN-E02", E, "Rework", "Tracing, terminating, testing and commissioning LT cable 1C 6 mm² to 4C 35 mm²", "Nos", "N:11"),
    ("MN-E03", E, "Rework", "Tracing, terminating, testing and commissioning LT cable 1C 50 mm² to 4C 95 mm²", "Nos", "N:12"),
    ("MN-E04", E, "Rework", "Dismantling and re-installing point wiring in wash room, kettle, fridge and wardrobe areas", "Nos", "N:13"),
    ("MN-E05", E, "Supports", "Fabricating, welding and installing angle iron support for panel / roof cable tray", "Nos", "N:14"),
    ("MN-E06", ELV, "Rework", "Tracing, terminating, testing and commissioning installed Cat-6 / RG-6 telephone cable", "Nos", "N:15"),
    ("MN-E07", E, "Rework", "Terminating, testing and commissioning installed DB in shops and guest rooms", "Nos", "N:16"),
    ("MN-E08", E, "Rework", "Tracing, testing and commissioning installed light / power circuit wiring", "Nos", "N:17"),
    ("MN-E09", E, "Rework", "Tracing, testing, commissioning and looping installed light / power circuit wiring", "Nos", "N:18"),
    ("MN-E10", ELV, "Rework", "Tracing, testing and commissioning installed fire alarm and PA wiring", "Nos", "N:19"),
    ("MN-E11", E, "Dismantling", "Dismantling cable tray 12\"×3\"", "Rft", "N:55"),
    ("MN-E12", E, "Dismantling", "Dismantling cable tray 9\"×3\" / 6\"×3\"", "Rft", "N:56,57"),
    ("MN-E13", E, "Dismantling", "Dismantling cable tray 4\"×4\"", "Rft", "N:58"),
    ("MN-E14", E, "Dismantling", "Dismantling cable tray 4\"×3\"", "Rft", "N:59"),
    ("MN-E15", E, "Dismantling", "Dismantling power cable 2C 6 mm²", "Rft", "N:61"),
    ("MN-E16", E, "Dismantling", "Dismantling power cable 1C 6 mm²", "Rft", "N:62"),
    ("MN-E17", ELV, "Dismantling", "Dismantling Cat-6 cable", "Rft", "N:63"),
    ("MN-E18", E, "Rework", "Dismantling wiring to install missing earth wire", "Point", "N:92"),
    ("MN-E19", E, "Rework", "Disconnecting, dismantling, tracing, reconnecting and testing LT cable 1C 240 mm²", "Rft", "N:100"),
    ("MN-E20", E, "Rework", "Disconnecting, dismantling, tracing, reconnecting and testing LT cable 1C 185 mm²", "Rft", "N:101"),
    ("MN-E21", E, "Rework", "Disconnecting, dismantling, tracing, reconnecting and testing LT cable 1C 70 mm²", "Rft", "N:102"),
    ("MN-E22", E, "Rework", "Shifting cable tray 18\"×3\"", "Rft", "N:103"),
    ("MN-E23", E, "Distribution", "Installing DB for fuel pump", "Nos", "N:135"),
    ("MN-E24", E, "Distribution", "Installing DB for fire pump", "Nos", "N:136"),
    ("MN-E25", E, "Distribution", "Installing BMS panel", "Nos", "N:141"),
    ("MN-E26", E, "Controls", "Terminating and fixing thermostat", "Nos", "N:190"),
    ("MN-E27", E, "Supports", "Providing support for elevation lights", "Nos", "N:192"),
    ("MN-E28", E, "Equipment", "Installing UPS", "Job", "N:193"),
    ("MN-E29", E, "Distribution", "Terminating and fixing MCCB box", "Nos", "N:194"),
    ("MN-E30", E, "Distribution", "Fixing metering panel including tracing and terminating cable connections from all shops and busbar", "Job", "N:195"),
    ("MN-E31", E, "Accessories", "Installing USB socket", "Nos", "N:281"),
    ("MN-P01", PL, "Dismantling", "Dismantling PPR pipe 50 mm", "Rft", "N:65"),
    ("MN-P02", PL, "Dismantling", "Dismantling PPR pipe 40 mm", "Rft", "N:84"),
    ("MN-P03", PL, "Dismantling", "Dismantling PPR pipe 25–32 mm", "Rft", "N:85,86"),
    ("MN-P04", PL, "Dismantling", "Dismantling PVC pipe of submersible pumps in basement", "Rft", "N:107"),
    ("MN-P05", PL, "Dismantling", "Dismantling PPR pipe 110 mm", "Rft", "N:169"),
    ("MN-P06", PL, "Dismantling", "Dismantling uPVC pipe 100 mm", "Rft", "N:170"),
    ("MN-P11", PL, "Valves", "Installing globe valve on PPR pipe 25 mm (3/4\")", "Nos", "N:205"),
    ("MN-P07", PL, "Valves", "Installing globe valve on PPR pipe 32 mm (1\")", "Nos", "N:206"),
    ("MN-P08", PL, "Valves", "Installing globe valve on PPR pipe 40 mm (1-1/4\")", "Nos", "N:207"),
    ("MN-P09", PL, "Valves", "Installing globe valve on PPR pipe 50 mm (1-1/2\")", "Nos", "N:208"),
    ("MN-P10", PL, "Valves", "Installing globe valve on PPR pipe 63 mm (2\")", "Nos", "N:209"),
    ("MN-F01", FF, "Dismantling", "Dismantling MS pipe 1\" / 1-1/4\"", "Rft", "N:38,39,33,34"),
    ("MN-F02", FF, "Dismantling", "Dismantling MS pipe 1-1/2\"", "Rft", "N:40"),
    ("MN-F03", FF, "Dismantling", "Dismantling MS pipe 2\" / 2-1/2\"", "Rft", "N:41,42,32"),
    ("MN-F04", FF, "Dismantling", "Dismantling MS pipe 3\"", "Rft", "N:43,30"),
    ("MN-F05", FF, "Dismantling", "Dismantling MS pipe 4\"", "Rft", "N:44"),
    ("MN-F06", FF, "Dismantling", "Dismantling MS pipe 6\"", "Rft", "N:45"),
    ("MN-F07", FF, "Dismantling", "Dismantling MS pipe 1\" (LGF / kitchen, Scope #02)", "Rft", "N:67,78"),
    ("MN-F08", FF, "Dismantling", "Dismantling MS pipe 1-1/2\" (Scope #02)", "Rft", "N:68"),
    ("MN-F09", FF, "Dismantling", "Dismantling MS pipe 2\" (Scope #02)", "Rft", "N:69"),
    ("MN-F10", FF, "Dismantling", "Dismantling MS pipe 2-1/2\" (Scope #02)", "Rft", "N:70,77"),
    ("MN-F11", FF, "Dismantling", "Dismantling MS pipe 3\" (Scope #02)", "Rft", "N:71,76"),
    ("MN-F12", FF, "Dismantling", "Dismantling MS pipe 4\" (Scope #02)", "Rft", "N:72,75"),
    ("MN-F13", FF, "Dismantling", "Dismantling zone control valve assembly 4\"", "Nos", "N:150"),
    ("MN-F14", FF, "Rework", "Re-installing zone control valve assembly 4\" (approved rate)", "Nos", "N:151"),
    ("MN-F15", FF, "Dismantling", "Dismantling dual-compartment fire hose cabinet", "Nos", "N:164"),
    ("MN-H01", HV, "Dismantling", "Dismantling ductwork (level 06)", "Sft", "N:27"),
    ("MN-H02", HV, "Dismantling", "Dismantling chilled water pipe 4\" (pro-rata)", "Rft", "N:29"),
    ("MN-H03", HV, "Dismantling", "Dismantling ductwork 26 gauge (Scope #02)", "Sft", "N:80"),
    ("MN-H04", HV, "Ductwork", "Installing canvas cloth wrapping with anti-fungus paint on supply / return air duct", "Sft", "N:115"),
    ("MN-H05", HV, "Ductwork", "Installing sound liner on supply and return air duct", "Sft", "N:116"),
    ("MN-H06", HV, "Kitchen exhaust", "Labour services and scaffolding for kitchen exhaust works", "LS", "N:125"),
    ("MN-H07", HV, "Ventilation", "Shifting and installing kitchen exhaust fan 7,000 CFM including checker plate cutting and foundation", "Nos", "N:175"),
    ("MN-H08", HV, "Ventilation", "Shifting and installing fresh air fan 3,375 CFM", "Nos", "N:178"),
    ("MN-H09", HV, "Ventilation", "Shifting and installing fresh air fan 1,000 CFM", "Nos", "N:179"),
    ("MN-H10", HV, "Insulation", "Installing 1\" duct insulation on AHU-06 fresh / exhaust air duct at roof", "Sft", "N:180"),
    ("MN-H11", HV, "Insulation", "Installing 3/4\" polyethylene insulation with GI tape on condensate drain pipe", "Rft", "N:181"),
    ("MN-H12", HV, "Valves", "Shifting and installing modulating valve 6\"", "Nos", "N:214"),
    ("MN-H13", HV, "Accessories", "Installing 2\" air vent on chilled water line in plant room", "Nos", "N:221"),
    ("MN-H14", HV, "Metering", "Dismantling 6\" spool and installing 6\" BTU meter on chilled water line", "Nos", "N:222"),
    ("MN-H15", HV, "Metering", "Installing 6\" flow meter on chilled water line", "Nos", "N:223"),
    ("MN-H16", HV, "Metering", "Installing 10\" flow meter on chilled water line", "Nos", "N:224"),
    ("MN-H17", HV, "Controls", "Installing flow switch on chilled / cooling water line with electrical connections", "Nos", "N:225"),
    ("MN-H18", HV, "Split AC", "Installing split AC unit", "Nos", "N:226"),
    ("MN-H19", HV, "Split AC", "Installing split AC unit 4 ton", "Nos", "N:288"),
    ("MN-H20", HV, "Ventilation", "Installing air curtain", "Nos", "N:242"),
    ("MN-H21", HV, "Ventilation", "Installing toilet exhaust fan including dismantling of diffuser and duct drop neck", "Nos", "N:243"),
    ("MN-H22", HV, "Commissioning", "Draining chilled water circuit", "Job", "N:245"),
    ("MN-H23", HV, "Valves", "Installing balancing valve 3\" / 4\" including cutting of MS pipe", "Nos", "N:247,248"),
    ("MN-H24", HV, "Commissioning", "Re-filling chilled water circuit (chemical by Employer)", "Job", "N:249"),
    ("MN-H25", HV, "Commissioning", "Testing and flushing the system after valve installation", "Job", "N:250"),
    ("MN-H26", HV, "Commissioning", "Temporary spool arrangement in plant room for flushing and dismantling after flushing", "Job", "N:251"),
    ("MN-H27", HV, "Commissioning", "Water balancing for hotel apartments", "Job", "N:252"),
    ("MN-H28", HV, "Ventilation", "Shifting and installing fresh air fan 5,000 CFM in plant room", "Nos", "N:254"),
    ("MN-H29", HV, "Dismantling", "Dismantling gate valve 6\" / fan coil unit", "Nos", "N:290,291"),
    ("MN-H30", HV, "Accessories", "Installing PRV 3/4\"", "Nos", "N:263"),
    ("ME-210", E, "Distribution", "Installing, terminating and testing DB in server room / admin office", "Nos", "N:283,284"),
    ("ME-342", E, "Power points", "Providing wiring of 4 mm² power circuit (Scope #07)", "Nos", "N:235"),
    ("ME-505G", E, "Containment", "Installing 1\" PVC conduit run (Scope #07, billed per Nos)", "Nos", "N:232"),
    ("ME-401R", E, "Lighting", "Installing Employer-supplied 2'×2' ceiling panel light, floor-mounted concealed light or bedside light", "Nos", "N:255,256,280"),
    ("ME-401S", E, "Lighting", "Installing Employer-supplied spot light in external area", "Nos", "N:282"),
    ("MN-P12", PL, "Valves", "Installing ball valve 1/2\" (20 mm) on PPR pipe", "Nos", "N:210"),
    ("MN-P13", PL, "Valves", "Installing gate valve 63 mm", "Nos", "N:264"),
    ("MN-P14", PL, "Accessories", "Installing bellow-type flexible connector in pump room", "Nos", "N:270"),
    ("MN-F16", FF, "Dismantling", "Dismantling MS pipe 1\" (4th floor kitchen area, Scope #02)", "Rft", "N:88"),
    ("MN-F17", FF, "Dismantling", "Dismantling MS pipe 1\" (25 mm), Scope #05 approved rate", "Rft", "N:154"),
    ("MN-F18", FF, "Dismantling", "Dismantling MS pipe 1-1/2\" (40 mm), Scope #05 approved rate", "Rft", "N:155"),
    ("MN-F19", FF, "Dismantling", "Dismantling MS pipe 2\" / 2-1/2\" (50–63 mm), Scope #05 approved rate", "Rft", "N:156,157"),
    ("MN-F20", FF, "Rework", "Re-installing MS pipe 1\" (25 mm), Scope #05 approved rate", "Rft", "N:159"),
    ("MN-F21", FF, "Rework", "Re-installing MS pipe 1-1/2\" (40 mm), Scope #05 approved rate", "Rft", "N:160"),
    ("MN-F22", FF, "Rework", "Re-installing MS pipe 2\" (50 mm), Scope #05 approved rate", "Rft", "N:161"),
    ("MN-F23", FF, "Rework", "Re-installing MS pipe 2-1/2\" (63 mm), Scope #05 approved rate", "Rft", "N:162"),
    ("MN-F24", FF, "Rework", "Re-installing MS pipe 6\" (150 mm), Scope #06 approved rate", "Rft", "N:200"),
    ("MN-F25", FF, "Rework", "Re-installing dual-compartment fire hose cabinet (approved rate)", "Nos", "N:165"),
    ("MN-F26", FF, "Valves", "Installing alarm check valve assembly 6\" in pump room", "Nos", "N:276"),
    ("MN-H34", HV, "Dismantling", "Dismantling chilled water pipe 2-1/2\" (level 06)", "Rft", "N:31"),
    ("MN-H35", HV, "Ventilation", "Shifting and installing fresh air fan 1,500 CFM / exhaust air fan 1,800 CFM (Scope #05)", "Nos", "N:176,177"),
    ("MN-H36", HV, "Insulation", "Installing rock wool insulation in 3rd floor restaurant area", "Sft", "N:287"),
]
for code, cat, sub, d, unit, rows in NB:
    ITEMS.append((code, cat, sub, d + ", complete in all respects", unit, rows, [], 0, "Labour-only item (Non-BOQ)."))

ITEMS += [
    ("MN-H31", HV, "Kitchen exhaust", "Supplying and installing 14 SWG MS kitchen exhaust duct, complete in all respects", "Sft", "N:123", [], 0,
     "MAK rate is supply and install (Kitchen Additional Scope); no separate material line."),
    ("MN-H32", HV, "Kitchen exhaust", "Supplying and installing rock wool insulation on kitchen exhaust duct, complete in all respects", "Sft", "N:124", [], 0,
     "MAK rate is supply and install; compare GRN rock wool 3\" at 139.42/Sft (MH-230)."),
    ("MN-H33", HV, "Split AC", "Supplying and installing additional copper pipe pair with insulation for split AC (beyond 10 Rft per unit), complete in all respects", "Rft", "N:289",
     [(522, 1, '1/2" copper pipe'), (523, 1, '1/4" copper pipe'), (552, 1, '1/2" insulation 9 mm'), (543, 1, '1/4" insulation 9 mm')], WAST["pipe"], "Pipe pair for 1.5 ton unit."),
]

ITEMS += [
    ("ME-209", E, "Distribution", "Installing, terminating, testing and commissioning Employer-supplied 1st floor common distribution board DBC-1F, complete in all respects", "Nos", "E:94", [], 0,
     "Billed at the panel-board rate (40,012.50), not the 14,550 DB rate of ME-207."),
    ("ME-506H", E, "Containment", "Dismantling and re-installing cable tray 9\"×3\" with additional bend under beam, including cables on it, complete in all respects", "Rft", "E:572", [], 0, ""),
    ("ME-506J", E, "Containment", "Dismantling and re-installing cable tray 12\"×3\" with additional bend under beam, including cables on it, complete in all respects", "Rft", "E:573", [], 0, ""),
    ("ME-506K", E, "Containment", "Dismantling and re-installing cable tray 18\"×3\" with additional bend under beam, including cables on it, complete in all respects", "Rft", "E:574", [], 0, ""),
    ("MX-1219", ELV, "Networking", "Supplying and installing 12U data cabinet with accessories, complete in all respects", "Nos", "E:468,511", [("MEP-Z-RACK12", 1, "")], 0, ""),
    ("MX-1220", ELV, "Networking", "Supplying and installing 16 SWG MS ELV junction box for TV, telephone and data in shops, concealed in wall, with earthing terminal, complete in all respects", "Nos", "E:507", [(648, 1, "")], 0, ""),
    ("MX-1308", ELV, "Public address", "Installing, testing and commissioning music system with microphone and USB input, complete in all respects", "Nos", "E:479", [], 0, ""),
    ("MX-1503", ELV, "Telephone", "Supplying and installing telephone DB (30 pair), complete in all respects", "Nos", "E:521", [], 0, ""),
    ("MX-1504", ELV, "Telephone", "Supplying and installing telephone DB (40 pair), complete in all respects", "Nos", "E:522", [], 0, ""),
    ("MX-1505", ELV, "Telephone", "Installing, testing and commissioning EPABX telephone exchange (4 external / 128 extension lines), complete in all respects", "Job", "E:532", [], 0, ""),
    ("MP-102A", PL, "Core cutting", "Core cutting of RCC for pipe crossing 2\"–3\" dia (core sealant not included), complete in all respects", "Nos", "P:260", [], 0, ""),
    ("MP-102B", PL, "Core cutting", "Core cutting of RCC for pipe crossing 4\"–5\" dia (core sealant not included), complete in all respects", "Nos", "P:261", [], 0, ""),
    ("MP-102C", PL, "Core cutting", "Core cutting of RCC for pipe crossing 6\" dia (core sealant not included), complete in all respects", "Nos", "P:262", [], 0, ""),
    ("MP-102D", PL, "Core cutting", "Core cutting of RCC for pipe crossing 8\" dia (core sealant not included), complete in all respects", "Nos", "P:263", [], 0, ""),
    ("MH-218D", HV, "Condensate piping", "Supplying and installing uPVC Class E condensate pipe 3\" with fittings and hangers, complete in all respects", "Rft", "H:106", [("MEP-Z-UE3", 1, "")], WAST["pipe"], ""),
    ("MH-221H", HV, "Valves", "Supplying and installing flanged ductile iron gate valve 10\", complete in all respects", "Nos", "H:151", [("MEP-Z-GV10", 1, "")], 0, ""),
    ("MH-232B", HV, "Insulation", "Supplying and installing 1/4\" polyethylene (Jumbolon) insulation with GI tape on condensate pipe 1\", complete in all respects", "Rft", "H:188", [("MEP-Z-PE6", 1, "")], WAST["pipe"], ""),
    ("MH-232C", HV, "Insulation", "Supplying and installing 1/4\" polyethylene (Jumbolon) insulation with GI tape on condensate pipe 3\", complete in all respects", "Rft", "H:190", [("MEP-Z-PE6", 1, "")], WAST["pipe"], ""),
]

# Materials with no GRN: (code, name, unit)
ZERO = {
    "MEP-Z-WPSKT": ("Weather-proof 13 A socket", "Nos"), "MEP-Z-SHAVER": ("Shaver socket", "Nos"),
    "MEP-Z-IPS32": ("Industrial socket 5-pin 32 A with plug", "Nos"), "MEP-Z-BELL": ("Door bell", "Nos"),
    "MEP-Z-DND": ("DND / PCU panel set", "Set"), "MEP-Z-KEYCARD": ("RFID key-card switch", "Nos"),
    "MEP-Z-DL20": ("LED recessed downlight 20 W", "Nos"), "MEP-Z-DLSQ": ("LED square downlight 3 × 10 W", "Nos"),
    "MEP-Z-BULK": ("LED bulkhead light 10 W", "Nos"), "MEP-Z-ROPE": ("LED rope light", "Rft"),
    "MEP-Z-STRIP": ("LED flexible strip light IP65", "Rft"), "MEP-Z-WASH": ("LED linear wall washer 48 W", "Nos"),
    "MEP-Z-FOB": ("MS floor outlet box 16 SWG", "Nos"), "MEP-Z-BFAN": ("Wall bracket fan 18\"", "Nos"),
    "MEP-Z-2C4": ("Cable 2C × 4 mm² Cu/PVC/PVC", "Rft"), "MEP-Z-3C16": ("Cable 3C × 16 mm² Cu/PVC/PVC", "Rft"),
    "MEP-Z-3C4": ("Cable 3C × 4 mm² Cu/PVC/PVC", "Rft"), "MEP-Z-1C50": ("Cable 1C × 50 mm² green/yellow", "Rft"),
    "MEP-Z-COND6": ("PVC conduit 6\" heavy duty", "Rft"), "MEP-Z-CT4": ("GI perforated cable tray 4\" × 3\"", "Rft"),
    "MEP-Z-MAT": ("Insulation rubber mat 3.5 mm", "Sft"), "MEP-Z-MAST": ("GI mast pipe 1-1/2\" for ESE", "Nos"),
    "MEP-Z-CUSTRIP": ("Copper tape 30 × 2 with clips", "Rft"), "MEP-Z-CAM4": ("Outdoor IP camera 4 MP", "Nos"),
    "MEP-Z-SW32": ("POE switch 32-port", "Nos"), "MEP-Z-PP32": ("Cat-6 patch panel 32-port", "Nos"),
    "MEP-Z-PP24": ("Cat-6 patch panel 24-port", "Nos"), "MEP-Z-PP8": ("Cat-6 patch panel 8-port", "Nos"),
    "MEP-Z-PCORD": ("Cat-6 patch cord 1 m", "Nos"), "MEP-Z-RACK42": ("Data cabinet 42U", "Nos"),
    "MEP-Z-RACK24": ("Data cabinet 24U", "Nos"), "MEP-Z-WAP": ("Wireless access point", "Nos"),
    "MEP-Z-SPK6": ("Ceiling speaker 6 W", "Nos"), "MEP-Z-SPK20": ("Wall speaker 20 W", "Nos"),
    "MEP-Z-VOLC": ("Volume controller", "Nos"), "MEP-Z-SPLIT": ("MATV splitter", "Nos"),
    "MEP-Z-BOOST": ("HDTV booster", "Nos"), "MEP-Z-RG11": ("RG-11 co-axial cable", "Rft"),
    "MEP-Z-RG6": ("RG-6 co-axial cable", "Rft"), "MEP-Z-SINK": ("Kitchen sink", "Nos"),
    "MEP-Z-SOAPD": ("Soap dispenser", "Nos"), "MEP-Z-MIRROR": ("Looking glass 5 mm", "Sft"),
    "MEP-Z-TAP": ("Tap 3/4\"", "Nos"), "MEP-Z-ABL": ("Ablution tap mixer", "Nos"),
    "MEP-Z-PPR75": ("PPR PN20 pipe 75 mm", "Rft"), "MEP-Z-PRV32": ("PRV assembly 32 mm", "Nos"),
    "MEP-Z-PRV50": ("PRV assembly 50 mm", "Nos"), "MEP-Z-PRV63": ("PRV assembly 63 mm", "Nos"),
    "MEP-Z-UPVC12": ("uPVC pipe 12\"", "Rft"), "MEP-Z-ARMAW": ("Armawave pipe sound insulation 4\"", "Rft"),
    "MEP-Z-GTRAP": ("Stainless steel grease trap", "Nos"), "MEP-Z-GI1": ("GI pipe 1\" with fittings", "Rft"),
    "MEP-Z-GI2": ("GI pipe 2\" with fittings", "Rft"), "MEP-Z-GV125": ("Gate valve 1-1/4\"", "Nos"),
    "MEP-Z-SPRSW": ("Sidewall sprinkler K5.6", "Nos"), "MEP-Z-EXT": ("Portable fire extinguisher DCP / CO2", "Nos"),
    "MEP-Z-EXTC": ("Ceiling-hanging automatic extinguisher", "Nos"), "MEP-Z-MS075": ("MS Sch-40 pipe 3/4\"", "Rft"),
    "MEP-Z-MS8": ("MS Sch-40 pipe 8\"", "Rft"), "MEP-Z-MS10": ("MS Sch-40 pipe 10\"", "Rft"),
    "MEP-Z-MS12": ("MS Sch-40 pipe 12\"", "Rft"), "MEP-Z-UE1": ("uPVC Class E pipe 1\"", "Rft"),
    "MEP-Z-UE2": ("uPVC Class E pipe 2\"", "Rft"), "MEP-Z-GV075": ("Bronze gate valve 3/4\"", "Nos"),
    "MEP-Z-BV125": ("Ball valve 1-1/4\"", "Nos"), "MEP-Z-BV150": ("Ball valve 1-1/2\"", "Nos"),
    "MEP-Z-BV050": ("Ball valve 1/2\"", "Nos"), "MEP-Z-GV8": ("Flanged gate valve 8\"", "Nos"),
    "MEP-Z-DCOCK": ("Drain cock 1\"", "Nos"), "MEP-Z-AAV": ("Automatic air vent", "Nos"),
    "MEP-Z-NBR13": ("Elastomeric insulation sheet 1/2\"", "Sft"), "MEP-Z-PE6": ("Polyethylene insulation 1/4\" with GI tape", "Rft"),
    "MEP-Z-ALF": ("Washable aluminium filter 2\"", "Sft"), "MEP-Z-DIFF": ("Aluminium air diffuser", "Sft"),
    "MEP-Z-MESH": ("Wire mesh", "Sft"), "MEP-Z-RLG": ("Return linear grille", "Rft"),
    "MEP-Z-FDC": ("Flexible duct connector", "Rft"),
    "MEP-Z-RACK12": ("Data cabinet 12U", "Nos"), "MEP-Z-UE3": ("uPVC Class E pipe 3\"", "Rft"),
    "MEP-Z-GV10": ("Flanged gate valve 10\"", "Nos"),
}
for k in ("075", "100", "125", "150", "200"):
    sz = {"075": '3/4"', "100": '1"', "125": '1-1/4"', "150": '1-1/2"', "200": '2"'}[k]
    ZERO[f"MEP-Z-PICV{k}"] = (f"PICV {sz}", "Nos")
    ZERO[f"MEP-Z-YS{k}"] = (f"Y-strainer {sz} threaded", "Nos")
    ZERO[f"MEP-Z-MV{k}"] = (f"Motorised 2-way valve {sz}", "Nos")
    ZERO[f"MEP-Z-FX{k}"] = (f"Insulated flexible pipe connector {sz}, 4 ft", "Nos")

ALIAS = {"COND1": 282, "COND15": 1351}   # 1" and 1-1/2" PVC conduit GRNs


def block_of(html):
    m = BLOCK_RE.search(html)
    return json.loads(m.group(2)) if m else None


# ------------------------------------------------------------------ bill reader
PARENT = {}   # (sheet, row) -> item number of the heading above it


def read_bill(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = {}
    for key, name in SHEETS.items():
        parent = ""
        for i, r in enumerate(wb[name].iter_rows(max_col=13, values_only=True), 1):
            a = str(r[0]).strip() if r[0] not in (None, "") else ""
            if key == "N":
                m = re.match(r"(?i)(kitchen )?additional scope\s*#?\s*(\d*)", a)
                if m:
                    parent = "Kitchen Additional Scope" if m.group(1) else f"Additional Scope #{int(m.group(2)):02d}"
            elif re.fullmatch(r"\d+(\.\d+)?", a):
                parent = a
            rows[(key, i)] = r
            PARENT[(key, i)] = parent
    return rows


def refs(spec):
    out = []
    for part in spec.split(";"):
        k, nums = part.split(":")
        out += [(k, int(n)) for n in nums.split(",")]
    return out


def ref_label(k, r, row):
    no = str(row[0]).strip() if row[0] not in (None, "") else ""
    par = PARENT.get((k, r), "")
    item = par + ((" item " if k == "N" else " ") + no if no and no != par else "")
    sheet = {"E": "Electrical", "P": "Plumbing", "H": "HVAC", "N": ""}[k]
    return f"{sheet} {item.strip() or 'item'} (bill row {r})".strip()


def build(bill, grn):
    rates, items, problems = {}, [], []
    der = derived(grn)

    def use(ref):
        if isinstance(ref, str) and ref in ALIAS:
            ref = ALIAS[ref]
        if isinstance(ref, int):
            line = grn.line(ref)
        elif ref in der:
            line = der[ref]
        elif ref in ZERO:
            line = zero(ref, *ZERO[ref])
        else:
            return ref           # an existing Rate Database line, e.g. SAN-WC
        rates.setdefault(line["code"], line)
        return line["code"]

    for code, cat, sub, desc, unit, spec, mats, wast, note in ITEMS:
        rs_ = [(k, r, bill[(k, r)]) for k, r in refs(spec)]
        rate_vals = {round(num(row[4]), 4) for k, r, row in rs_ if num(row[4])}
        if len(rate_vals) != 1:
            problems.append(f"{code}: rows {spec} carry rates {sorted(rate_vals)}")
            continue
        mak = rate_vals.pop()
        cq = sum(num(row[3]) or 0 for k, r, row in rs_)
        fq = sum(num(row[12]) or 0 for k, r, row in rs_)
        nb = all(k == "N" for k, r, row in rs_)
        where = "; ".join(ref_label(k, r, row) for k, r, row in rs_[:4]) + (" …" if len(rs_) > 4 else "")
        lcode = "MAK-" + code
        rates[lcode] = {
            "code": lcode, "kind": "L", "name": "MAK installation — " + re.sub(r",? complete in all respects$", "", desc)[:110], "unit": unit,
            "rate": mak, "loc": "Rawalpindi",
            "src": (NB_SRC if nb else BOQ_SRC).format(ref=where), "date": NB_DATE if nb else BOQ_DATE, "vs": "V"}
        M = [{"ref": use(r), "qty": round(q, 4), **({"note": n} if n else {})} for r, q, n in mats]
        qn = f"Mall-35 quantities: contract {cq:,.2f}, final bill {fq:,.2f} {unit}."
        items.append({
            "id": code, "code": code, "cat": cat, "sub": sub, "desc": desc,
            "spec": "Mall-35 MEP (MAK) " + ("Non-BOQ " if nb else "BOQ ") + where,
            "unit": unit, "M": M, "L": [{"ref": lcode, "qty": 1, "note": "MAK installation rate per " + unit}], "P": [],
            "wast": wast, "oh": 8, "prof": 10, "acc": 0, "trans": 0, "gen": None,
            "note": (note + " " if note else "") + qn +
                    " Labour = MAK installation rate, which already carries MAK's own overhead and profit; "
                    "set OH / profit to 0 for Zameen's direct cost (material at GRN + MAK installation)."})
    return rates, items, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bill", type=Path, help="MAK final bill workbook (MAK Final Bill Checking.xlsx)")
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    a = ap.parse_args()
    html = a.html.read_text(encoding="utf-8")
    rates, items, problems = build(read_bill(a.bill), Grn(html))
    if problems:
        sys.exit("Bill rows disagree:\n  " + "\n  ".join(problems))
    body = json.dumps([sorted(rates.values(), key=lambda r: r["code"]), items], sort_keys=True, ensure_ascii=False)
    data = {"rev": dt.date.today().isoformat() + "-" + hashlib.sha1(body.encode()).hexdigest()[:8],
            "source": f"{a.bill.name} — MAK Contractors & Associates, Mall-35 MEP Final IPC-09 (May-2025); "
                      "material from the GRN Price Register",
            "rates": sorted(rates.values(), key=lambda r: r["code"]), "items": items}
    old = block_of(html)
    if old:
        pr, pi = dict(old.get("prevRates", {})), dict(old.get("prevItems", {}))
        new_r = {r["code"]: r for r in data["rates"]}
        for r in old.get("rates", []):
            n = new_r.get(r["code"])
            if n and (n["rate"], n["date"], n["src"]) != (r["rate"], r["date"], r["src"]):
                pr.setdefault(r["code"], [])
                if [r["rate"], r["date"]] not in pr[r["code"]]:
                    pr[r["code"]].append([r["rate"], r["date"]])
        new_i = {i["id"]: i for i in data["items"]}
        for i in old.get("items", []):
            n = new_i.get(i["id"])
            sig = [[m["ref"], m["qty"]] for m in i["M"]]
            if n and sig != [[m["ref"], m["qty"]] for m in n["M"]]:
                pi.setdefault(i["id"], [])
                if sig not in pi[i["id"]]:
                    pi[i["id"]].append(sig)
        data["prevRates"], data["prevItems"] = pr, pi
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if BLOCK_RE.search(html):
        html = BLOCK_RE.sub(lambda m: m.group(1) + blob + m.group(3), html)
    else:
        anchor = '<script type="application/json" id="raMrsData">'
        html = html.replace(anchor, f'<script type="application/json" id="raMepData">{blob}</script>\n' + anchor, 1)
    a.html.write_text(html, encoding="utf-8")
    zero_n = sum(1 for r in rates.values() if r["kind"] == "M" and not r["rate"])
    print(f"{len(items)} MEP items, {len(rates)} rate lines ({zero_n} material lines without a dated source) → {a.html}")


if __name__ == "__main__":
    main()
