#!/usr/bin/env python3
"""Build the Calculator tab's reference data (the calcData JSON block).

Every standardised value in the Calculator comes from this script, never from
the UI code. Section and pipe tables are read from published, machine-readable
sources rather than typed in:

  eurocodepy (PyPI)       IPE / HEA / HEB / HEM (EN 10365) and EN 10210-2 hot-
                          finished SHS / RHS / CHS: published mass, area, props
  steelpy (PyPI)          AISC Shapes Database v16.0: W, S, M, HP, C, MC, L,
                          WT, HSS (rect + round), Pipe: published weight, area
  Osdag (FOSSEE, IIT      IS 808:1989 beams, columns, channels, angles;
  Bombay, GitHub)         IS 4923 SHS / RHS; IS 1161 CHS; BS 4-1 UB / UC
  structuralcodes (PyPI)  EN dimensions (h, b, tw, tf, r, taper) for UPN, UPE,
                          IPN, HD, HP, EN 10056-1 angles: the area is computed
                          from the exact profile polygon (fillets, toe radii and
                          flange taper) and mass = A x 7850. Checked against
                          catalogue values (UPN 100 13.47 vs 13.5 cm2, IPN 300
                          69.00 vs 69.0, L100x100x10 19.16 vs 19.2).
  fluids (PyPI)           ASME B36.10M-2004 / B36.19M-2004 pipe schedules,
                          ASTM D1785 PVC, BS 1387 wall thicknesses, AWG

Hand-entered constants (unit factors, densities, rebar tables, IEC 60228
resistances, sheet gauges) are in this file with the reference each came from.

Usage:
  pip install eurocodepy steelpy structuralcodes fluids shapely numpy
  git clone --depth 1 https://github.com/osdag-admin/Osdag.git /tmp/osdag
  tools/calc_data.py --osdag /tmp/osdag zameen-developments/index.html

The block <script type="application/json" id="calcData"> is replaced in place.
"""

import argparse
import csv
import importlib.util
import json
import math
import pathlib
import re
import sqlite3
import sys
import types

REV = "2026-09-25"
RHO_STEEL = 7850.0          # kg/m3 (EN 10220 / B36.10M / BS 4449 mass basis)
IN = 25.4                   # mm, exact (1959 international inch)
LBFT = 0.45359237 / 0.3048  # kg/m per lb/ft, exact

# ----------------------------------------------------------------------------
# Sources. Every series / material / constant points at one of these ids.
# ----------------------------------------------------------------------------
SOURCES = {
    "nist811": {"t": "NIST SP 811 (2008) Appendix B — Guide for the Use of the SI; exact definitions of inch (25.4 mm), pound (0.45359237 kg), gn (9.80665 m/s²), US gallon (231 in³), imperial gallon (4.54609 L)",
                "url": "https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors", "d": REV},
    "eurocodepy": {"t": "eurocodepy 2026.1.1 (PyPI) profile tables — EN 10365:2017 open sections; EN 10210-2 hot-finished hollow sections (published mass & properties)",
                   "url": "https://github.com/pcachim/eurocodepy", "d": REV},
    "steelpy": {"t": "AISC Shapes Database v16.0 via steelpy 1.1.1 (PyPI) — published weight (lb/ft), area & properties; converted to SI exactly",
                "url": "https://www.aisc.org/publications/steel-construction-manual-resources/", "d": REV},
    "osdag": {"t": "Osdag section database (FOSSEE, IIT Bombay), Intg_osdag.sql @ fd1a7d8 (09-Jan-2025) — IS 808:1989 (Rev), IS 4923:1997, IS 1161:2014, BS 4-1 UB/UC",
              "url": "https://github.com/osdag-admin/Osdag", "d": REV},
    "sc": {"t": "structuralcodes 0.7.2 (PyPI, fib) EN profile dimensions (Euronorm 19-57, 53-62, EN 10279, EN 10365, EN 10056-1); area computed from exact profile polygon, mass = A × 7850 kg/m³",
           "url": "https://github.com/fib-international/structuralcodes", "d": REV},
    "fluids": {"t": "fluids 1.3.1 (PyPI, C. Bell) piping tables — ASME B36.10M-2004, ASME B36.19M-2004, ASTM D1785, BS 1387:1985 wall thicknesses, AWG",
               "url": "https://github.com/CalebBell/fluids", "d": REV},
    "b3610": {"t": "ASME B36.10M plain-end mass formula W = 0.0246615 (D − t) t kg/m (ρ = 7850 kg/m³); same factor as EN 10220",
              "url": "https://www.asme.org/codes-standards/find-codes-standards/b36-10m-welded-seamless-wrought-steel-pipe", "d": REV},
    "en10255": {"t": "EN 10255:2004 non-alloy steel tubes for welding and threading (replaces BS 1387) — nominal OD D and wall T, Medium (M) and Heavy (H) series; mass calculated with the EN 10220 formula",
                "url": "https://standards.iteh.ai/catalog/standards/cen/", "d": REV},
    "en1991": {"t": "EN 1991-1-1:2002 Annex A — nominal densities: normal-weight concrete 24 kN/m³ (+1 reinforced, +1 fresh), steel 77.0–78.5 kN/m³, aluminium 27.0 kN/m³",
               "url": "https://eurocodes.jrc.ec.europa.eu/", "d": REV},
    "is875": {"t": "IS 875 (Part 1):1987 unit weights of building materials — brick masonry 1920 kg/m³, cement 1440 kg/m³, cement mortar 2080 kg/m³, dry sand 1540–1600 kg/m³",
              "url": "https://archive.org/details/gov.in.is.875.1.1987", "d": REV},
    "en10088": {"t": "EN 10088-1 stainless steels — density 1.4301 (304) 7.9 kg/dm³, 1.4401 (316) 8.0 kg/dm³",
                "url": "https://tubingchina.com/EN-10088-1-Ambient-temperature-physical-properties-of-stainless-steel.htm", "d": REV},
    "iec60028": {"t": "IEC 60028 international standard of resistance for copper — annealed copper density 8.89 g/cm³ at 20 °C, resistivity 1/58 Ω·mm²/m",
                 "url": "https://webstore.iec.ch/en/publication/98", "d": REV},
    "iec60889": {"t": "IEC 60889 hard-drawn aluminium wire for overhead conductors — density 2.703 g/cm³ at 20 °C",
                 "url": "https://webstore.iec.ch/", "d": REV},
    "en1999": {"t": "EN 1999-1-1 cl. 3.2.5 — aluminium alloys, density 2700 kg/m³", "url": "https://eurocodes.jrc.ec.europa.eu/", "d": REV},
    "en545": {"t": "EN 545 ductile iron pipes — density used for mass calculation 7050 kg/m³",
              "url": "https://en.wikipedia.org/wiki/Ductile_iron_pipe", "d": REV},
    "c26000": {"t": "Wieland Concast C26000 cartridge brass (70/30) datasheet — density 8.53 g/cm³",
               "url": "https://www.concast.com/c26000.php", "d": REV},
    "en10346": {"t": "EN 10346 continuously hot-dip coated steel — Z275 = 275 g/m² zinc, total both sides (minimum average)",
                "url": "https://www.galvinfo.com/wp-content/uploads/sites/8/2017/05/GalvInfoNote_1_1.pdf", "d": REV},
    "a653gauge": {"t": "Galvanized sheet gauge table (ASTM A653 base steel, manufacturers' standard gauge): 16 ga 0.0635 in … 26 ga 0.0217 in",
                  "url": "https://www.custompartnet.com/library/sheet-metal-gauge", "d": REV},
    "bs4449": {"t": "BS 4449:2005+A3:2016 Table — nominal mass per metre on the basis of 0.00785 kg/mm² per metre (7850 kg/m³)",
               "url": "https://regbar.com/wp-content/uploads/2019/09/BS-4449-2005A2-2009.pdf", "d": REV},
    "a615": {"t": "ASTM A615/A615M Table 1 — deformed bar nominal weight (lb/ft); bar No. = diameter in eighths of an inch (sutar)",
             "url": "https://store.astm.org/a0615_a0615m-22.html", "d": REV},
    "iec60228": {"t": "IEC 60228 Table 2 — maximum DC resistance of Class 2 stranded conductors at 20 °C (Ω/km)",
                 "url": "https://www.nexans.be/en/dam/jcr:efe5d9a2-f346-4047-87b4-99d1e319d768/IEC60228_ENG.pdf", "d": REV},
    "b258": {"t": "ASTM B258 — AWG diameter d = 0.005 in × 92^((36 − n)/39)", "url": "https://store.astm.org/b0258-18.html", "d": REV},
    "en10219": {"t": "EN 10219-2 cold-formed hollow sections — corner radii for calculation: ro = 2.0t, ri = 1.0t (t ≤ 6); 2.5t / 1.5t (6 < t ≤ 10); 3.0t / 2.0t (t > 10)",
                "url": "https://standards.iteh.ai/catalog/standards/cen/073cb87d-d24a-4cde-b626-79d9b01cb537/en-10219-2-2019", "d": REV},
    "en10210": {"t": "EN 10210-2 hot-finished hollow sections — corner radii for calculation: ro = 1.5t, ri = 1.0t", "url": "https://standards.iteh.ai/", "d": REV},
    "bs3737": {"t": "Imperial Standard Wire Gauge (SWG, BS 3737) diameters via fluids 1.3.1 BSWG table — e.g. 16 SWG 0.064 in, 18 SWG 0.048 in, 20 SWG 0.036 in",
               "url": "https://github.com/CalebBell/fluids", "d": REV},
    "geom": {"t": "Engineering geometry (exact formula) — no empirical coefficient", "url": "", "d": REV},
    "conv": {"t": "QS practice convention — editable default, not a standard value. Confirm against the project specification.", "url": "", "d": REV},
    "user": {"t": "User-defined value", "url": "", "d": ""},
}

# ----------------------------------------------------------------------------
# Units — factor to the SI base of the dimension. All factors are exact by
# definition (NIST SP 811) unless noted. Construction aliases (RFT, SFT, CFT)
# are the same factor as ft, ft², ft³.
# ----------------------------------------------------------------------------
FT = 0.3048
UNITS = {
    "len": {"base": "m", "u": [["mm", 1e-3], ["cm", 1e-2], ["m", 1], ["km", 1e3], ["in", 0.0254], ["ft", FT], ["RFT", FT], ["yd", 0.9144], ["mile", 1609.344]]},
    "area": {"base": "m²", "u": [["mm²", 1e-6], ["cm²", 1e-4], ["m²", 1], ["in²", 0.0254**2], ["ft²", FT**2], ["SFT", FT**2], ["yd²", 0.9144**2],
                                ["acre", 4046.8564224], ["hectare", 1e4], ["Marla (225 SFT)", 225 * FT**2], ["Marla (272.25 SFT)", 272.25 * FT**2],
                                ["Kanal (20 × 225 SFT)", 4500 * FT**2]]},
    "vol": {"base": "m³", "u": [["mm³", 1e-9], ["cm³", 1e-6], ["m³", 1], ["litre", 1e-3], ["mL", 1e-6], ["in³", 0.0254**3], ["ft³", FT**3], ["CFT", FT**3],
                               ["yd³", 0.9144**3], ["US gallon", 3.785411784e-3], ["imp. gallon", 4.54609e-3], ["brass (100 CFT)", 100 * FT**3]]},
    "mass": {"base": "kg", "u": [["mg", 1e-6], ["g", 1e-3], ["kg", 1], ["ton (metric, 1000 kg)", 1000], ["lb", 0.45359237], ["long ton (2240 lb)", 1016.0469088],
                                ["short ton (2000 lb)", 907.18474], ["maund (40 kg)", 40]]},
    "force": {"base": "N", "u": [["N", 1], ["kN", 1e3], ["kgf", 9.80665], ["tonf (metric)", 9806.65], ["lbf", 4.4482216152605], ["kip", 4448.2216152605]]},
    "press": {"base": "Pa", "u": [["Pa", 1], ["kPa", 1e3], ["MPa (N/mm²)", 1e6], ["bar", 1e5], ["psi", 6894.757293168361], ["ksi", 6894757.293168361],
                                 ["kg/cm²", 98066.5], ["atm", 101325], ["m H₂O", 9806.65], ["mm Hg", 133.322387415], ["kN/m²", 1e3], ["lb/ft² (psf)", 47.88025898033584]]},
    "temp": {"base": "K", "u": [["°C", "C"], ["°F", "F"], ["K", "K"]]},
    "time": {"base": "s", "u": [["second", 1], ["minute", 60], ["hour", 3600], ["day", 86400], ["week", 604800]]},
    "flow": {"base": "m³/s", "u": [["m³/s", 1], ["m³/h", 1 / 3600], ["L/s", 1e-3], ["L/min", 1e-3 / 60], ["CFM (ft³/min)", FT**3 / 60],
                                  ["US gpm", 3.785411784e-3 / 60], ["imp. gpm", 4.54609e-3 / 60]]},
    "power": {"base": "W", "u": [["W", 1], ["kW", 1e3], ["MW", 1e6], ["hp (mechanical)", 745.6998715822702], ["BTU/h (IT)", 1055.05585262 / 3600],
                                ["ton of refrigeration (12,000 BTU/h)", 12000 * 1055.05585262 / 3600]]},
    "energy": {"base": "J", "u": [["J", 1], ["kJ", 1e3], ["kWh", 3.6e6], ["BTU (IT)", 1055.05585262], ["kcal (IT)", 4186.8]]},
    "dens": {"base": "kg/m³", "u": [["kg/m³", 1], ["g/cm³", 1e3], ["lb/ft³", 0.45359237 / FT**3], ["kN/m³ (÷ gn)", 1e3 / 9.80665]]},
    "lmass": {"base": "kg/m", "u": [["kg/m", 1], ["kg/ft", 1 / FT], ["lb/ft", LBFT], ["g/m", 1e-3]]},
    "amass": {"base": "kg/m²", "u": [["kg/m²", 1], ["kg/SFT", 1 / FT**2], ["lb/ft²", 0.45359237 / FT**2]]},
    "vel": {"base": "m/s", "u": [["m/s", 1], ["km/h", 1 / 3.6], ["ft/s", FT], ["ft/min (fpm)", FT / 60]]},
}

# ----------------------------------------------------------------------------
# Materials. st: std = standard value verified; typ = typical/range value,
# verify with product data; nv = no verified value (user must enter density).
# ----------------------------------------------------------------------------
MATERIALS = [
    # id, group, name, grade, rho, status, src, note
    ["ms", "Steel", "Mild steel (MS) / structural carbon steel", "S235–S355, A36, A572, Fe410", 7850, "std", "en1991",
     "EN 1991-1-1 gives 77.0–78.5 kN/m³; 7850 kg/m³ is the mass basis of EN 10220, ASME B36.10M, BS 4449 and EN 10025 section tables."],
    ["cs", "Steel", "Carbon steel pipe / plate", "ASTM A53, A106, A283", 7850, "std", "b3610", "ASME B36.10M weights are calculated at 7850 kg/m³."],
    ["gi", "Steel", "Galvanized steel (base steel)", "DX51D + Z275, A653", 7850, "std", "en10346",
     "Base steel only. Add zinc separately: Z275 = 275 g/m² total both sides (EN 10346)."],
    ["ss304", "Stainless", "Stainless steel 304", "1.4301 / X5CrNi18-10", 7900, "std", "en10088", ""],
    ["ss316", "Stainless", "Stainless steel 316", "1.4401 / X5CrNiMo17-12-2", 8000, "std", "en10088", ""],
    ["al", "Non-ferrous", "Aluminium alloy (structural)", "EN AW-6063 / 6061 etc.", 2700, "std", "en1999", ""],
    ["alc", "Non-ferrous", "Aluminium conductor (hard-drawn)", "IEC 60889", 2703, "std", "iec60889", ""],
    ["cu", "Non-ferrous", "Copper (annealed, conductor)", "IEC 60028", 8890, "std", "iec60028", ""],
    ["brass", "Non-ferrous", "Brass 70/30 (cartridge brass)", "C26000 / CuZn30", 8530, "std", "c26000", "Other brasses differ (e.g. CuZn37); use the grade datasheet."],
    ["di", "Iron", "Ductile iron (pipe)", "EN 545 / EN 598", 7050, "std", "en545", ""],
    ["ci", "Iron", "Grey cast iron", "EN 1561", 7200, "typ", "en1991",
     "Typical 7.1–7.3 g/cm³ (EN 1991-1-1 lists cast iron 71.0–72.5 kN/m³). Grade dependent — verify with the casting datasheet."],
    ["conc", "Civil", "Plain concrete (normal weight)", "EN 1991-1-1 Table A.1", 2400, "std", "en1991", "24 kN/m³ ≈ 2447 kg/m³ strictly (÷ gn); 2400 kg/m³ is the common mass convention."],
    ["rcc", "Civil", "Reinforced concrete", "EN 1991-1-1 Table A.1", 2500, "std", "en1991", "Plain + 1 kN/m³ for normal reinforcement."],
    ["brick", "Civil", "Brick masonry (cement mortar)", "IS 875-1", 1920, "std", "is875", ""],
    ["mortar", "Civil", "Cement mortar", "IS 875-1", 2080, "std", "is875", ""],
    ["cement", "Civil", "Cement (loose bulk)", "IS 875-1", 1440, "std", "is875", "Used to convert 50 kg bags to volume: 50 / 1440 = 0.0347 m³ = 1.226 CFT per bag."],
    ["sand", "Civil", "Sand, dry", "IS 875-1", 1600, "typ", "is875", "IS 875-1 range 1540–1600 kg/m³ (dry, clean)."],
    ["water", "Civil", "Water (fresh)", "", 1000, "std", "nist811", ""],
    ["earth", "Civil", "Earth / soil fill", "site soil", None, "nv", "user", "Data not verified — soil density varies; take from site / lab test."],
    ["agg", "Civil", "Coarse aggregate (crush / bajri)", "loose", None, "nv", "user", "Data not verified — take loose bulk density from the supplier or a site test."],
    ["pvc", "Plastic", "uPVC", "ASTM D1784", None, "nv", "user", "Data not verified — enter density from the pipe manufacturer's TDS."],
    ["cpvc", "Plastic", "CPVC", "ASTM D1784", None, "nv", "user", "Data not verified — enter density from the manufacturer's TDS."],
    ["hdpe", "Plastic", "HDPE (PE100)", "ISO 4427", None, "nv", "user", "Data not verified — enter density from the manufacturer's TDS."],
    ["ppr", "Plastic", "PP-R", "DIN 8077/8078", None, "nv", "user", "Data not verified — enter density from the manufacturer's TDS."],
]

# Rebar: BS 4449 table masses (kg/m); ASTM A615 (in, lb/ft).
REBAR_BS4449 = [[6, 0.222], [8, 0.395], [10, 0.617], [12, 0.888], [16, 1.579], [20, 2.466], [25, 3.854], [32, 6.313], [40, 9.864], [50, 15.413]]
REBAR_A615 = [  # bar no. (sutar), nominal dia in, lb/ft
    [3, 0.375, 0.376], [4, 0.500, 0.668], [5, 0.625, 1.043], [6, 0.750, 1.502], [7, 0.875, 2.044], [8, 1.000, 2.670],
    [9, 1.128, 3.400], [10, 1.270, 4.303], [11, 1.410, 5.313], [14, 1.693, 7.650], [18, 2.257, 13.600]]

# IEC 60228 Class 2 max DC resistance at 20 °C, Ω/km: [mm², plain Cu, Al]
IEC60228 = [[0.5, 36.0, None], [0.75, 24.5, None], [1, 18.1, None], [1.5, 12.1, None], [2.5, 7.41, None], [4, 4.61, None], [6, 3.08, None],
            [10, 1.83, 3.08], [16, 1.15, 1.91], [25, 0.727, 1.20], [35, 0.524, 0.868], [50, 0.387, 0.641], [70, 0.268, 0.443],
            [95, 0.193, 0.320], [120, 0.153, 0.253], [150, 0.124, 0.206], [185, 0.0991, 0.164], [240, 0.0754, 0.125],
            [300, 0.0601, 0.100], [400, 0.0470, 0.0778], [500, 0.0366, 0.0605], [630, 0.0283, 0.0469]]

GALV_GAUGE = [[16, 0.0635], [18, 0.0516], [20, 0.0396], [22, 0.0336], [24, 0.0276], [26, 0.0217]]  # gauge, inch

NPS_DN = {0.125: 6, 0.25: 8, 0.375: 10, 0.5: 15, 0.75: 20, 1: 25, 1.25: 32, 1.5: 40, 2: 50, 2.5: 65, 3: 80, 3.5: 90, 4: 100, 5: 125, 6: 150}


def nps_label(n):
    whole = int(n)
    frac = n - whole
    fr = {0.125: "1/8", 0.25: "1/4", 0.375: "3/8", 0.5: "1/2", 0.75: "3/4"}.get(round(frac, 3), "")
    s = (str(whole) if whole else "") + ("-" if whole and fr else "") + fr
    dn = NPS_DN.get(n, int(round(n * 25)))
    return f'{s}" (DN {dn})'


def r(x, n=3):
    return None if x is None else float(f"{x:.{n}g}") if abs(x) < 1 else round(x, n)


def num(x, d=4):
    if x is None or x == "" or x == "–":
        return None
    try:
        v = float(x)
    except ValueError:
        return None
    return round(v, d)


# ----------------------------------------------------------------------------
# Series builders. Column layouts per family (the UI reads the same lists):
#   I, C : name, h, b, tw, tf, r, A(cm²), m(kg/m), Iy, Iz(cm⁴), Wy, Wz(cm³), iy, iz(cm)
#   L    : name, a, b, t, r, A, m, Iy, Iz, iy, iz
#   T    : name, h, b, tw, tf, A, m, Iy, Iz
#   RHS  : name, h, b, t, A, m, Iy, Iz, Wy, Wz
#   CHS  : name, D, t, A, m, I, W, nb
# ----------------------------------------------------------------------------

def mseries(sid, grp, name, fam, std, src, kind, rows, note=""):
    return {"id": sid, "grp": grp, "name": name, "fam": fam, "std": std, "src": src, "kind": kind, "note": note, "rows": rows}


def euro(pkgdir):
    base = pathlib.Path(pkgdir) / "eurocodepy" / "data"
    out = []
    data = json.load(open(base / "i_profiles_euro.json"))
    for pre in ["IPE", "HEA", "HEB", "HEM"]:
        rows = []
        for x in data:
            if not re.fullmatch(pre + r"\d+", x["Section"]):
                continue
            rows.append([pre + " " + x["Section"][len(pre):], x["h"] * 10, x["b"] * 10, x["tw"] * 10, x["tf"] * 10, x["r"] * 10,
                         x["A"], x["m"], x["Iy"], x["Iz"], x["Wel_y"], x["Wel_z"], x["iy"], x["iz"]])
        rows.sort(key=lambda z: z[1])
        out.append(mseries("EU-" + pre, "EN (Europe)", pre, "I", "EN 10365:2017 / Euronorm 19-57 & 53-62", "eurocodepy", "pub", rows))
    for f, fam, pre in [("shs", "RHS", "SHS"), ("rhs", "RHS", "RHS")]:
        rows = []
        for x in json.load(open(base / f"{f}_profiles_euro.json")):
            h, b, t = x["h"] * 10, x["b"] * 10, x["tw"] * 10
            rows.append([f"{pre} {h:g}×{b:g}×{t:g}", h, b, t, x["A"], x["m"], x["Iy"], x["Iz"], x["Wel_y"], x["Wel_z"]])
        rows.sort(key=lambda z: (z[1], z[2], z[3]))
        out.append(mseries("EU-" + pre, "EN (Europe)", pre + " hot-finished", "RHS", "EN 10210-2 (ro = 1.5t)", "eurocodepy", "pub", rows))
    rows = []
    for x in json.load(open(base / "chs_profiles_euro.json")):
        D, t = round(x["h"] * 10, 1), round(x["tw"] * 10, 2)
        rows.append([f"CHS {D:g}×{t:g}", D, t, x["A"], x["m"], x["Iy"], x["Wel_y"], ""])
    rows.sort(key=lambda z: (z[1], z[2]))
    out.append(mseries("EU-CHS", "EN (Europe)", "CHS hot-finished", "CHS", "EN 10210-2", "eurocodepy", "pub", rows))
    return out


def sc_profiles(pkgdir):
    """EN profiles from structuralcodes dimensions; area from exact polygon."""
    base = pathlib.Path(pkgdir) / "structuralcodes" / "geometry" / "profiles"
    pkg = types.ModuleType("scprof")
    pkg.__path__ = [str(base)]
    sys.modules["scprof"] = pkg
    bp = types.ModuleType("scprof._base_profile")
    exec("class BaseProfile:\n    pass", bp.__dict__)
    sys.modules["scprof._base_profile"] = bp

    def load(name):
        spec = importlib.util.spec_from_file_location("scprof." + name, base / (name + ".py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["scprof." + name] = m
        spec.loader.exec_module(m)
        return m

    load("_common_functions")
    out = []
    spec = [("_upn", "UPN", "UPN (taper flange)", "C", "EN 10279 / DIN 1026-1 (8% taper)"),
            ("_upe", "UPE", "UPE (parallel flange)", "C", "EN 10365:2017"),
            ("_ipn", "IPN", "IPN (taper flange)", "I", "EN 10365 / DIN 1025-1 (14% taper)"),
            ("_hd", "HD", "HD (column)", "I", "EN 10365 / ArcelorMittal HD"),
            ("_hp", "HP", "HP (bearing pile)", "I", "EN 10365 / ArcelorMittal HP"),
            ("_l", "L", "Equal angle L", "L", "EN 10056-1"),
            ("_li", "LI", "Unequal angle L", "L", "EN 10056-1")]
    for mod, cls, name, fam, std in spec:
        C = getattr(load(mod), cls)
        rows = []
        for n, p in C.parameters.items():
            A = C.get_polygon(n).area / 100.0  # cm²
            m = A * 1e-4 * RHO_STEEL
            if fam == "L":
                label = "L " + n[1:].replace("x", "×")
                rows.append([label, p["h"], p["b"], p["t"], p.get("r1"), round(A, 2), round(m, 2), None, None, None, None])
            else:
                label = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", n).replace("x", "×")
                rows.append([label, p["h"], p["b"], p["tw"], p["tf"], p.get("r", p.get("r1")), round(A, 2), round(m, 2), None, None, None, None, None, None])
        out.append(mseries("EU-" + cls, "EN (Europe)", name, fam, std, "sc", "calc", rows,
                           "Mass calculated from standard dimensions incl. root/toe radii and flange taper, ρ = 7850 kg/m³ (matches catalogue values to ±0.5%)."))
    return out


def frac_name(n):
    """AISC fraction designations: L4X4X1_2 -> L4×4×1/2, HSS3_1_2X2X1_4 -> HSS3-1/2×2×1/4."""
    def part(p):
        b = p.split("_")
        if len(b) == 3:
            return f"{b[0]}-{b[1]}/{b[2]}"
        if len(b) == 2:
            return f"{b[0]}/{b[1]}"
        return p
    return "×".join(part(p) for p in n.split("X"))


def aisc(pkgdir):
    base = pathlib.Path(pkgdir) / "steelpy" / "shape files"
    I4, I3, I2 = IN ** 4 / 1e4, IN ** 3 / 1e3, IN ** 2 / 1e2

    def rd(f):
        return list(csv.DictReader(open(base / f, encoding="utf-8")))

    out = []
    for f, sid, name, fam in [("W_shapes.csv", "W", "W wide flange", "I"), ("S_shapes.csv", "S", "S American standard beam", "I"),
                              ("M_shapes.csv", "M", "M miscellaneous beam", "I"), ("HP_shapes.csv", "HP", "HP bearing pile", "I"),
                              ("C_shapes.csv", "C", "C American standard channel", "C"), ("MC_shapes.csv", "MC", "MC miscellaneous channel", "C")]:
        rows = []
        for x in rd(f):
            rows.append([x["shape"].replace("_", "."), num(x["d"]) * IN, num(x["bf"]) * IN, num(x["tw"]) * IN, num(x["tf"]) * IN, None,
                         round(num(x["area"]) * I2, 2), round(num(x["weight"]) * LBFT, 2), round(num(x["Ix"]) * I4, 1), round(num(x["Iy"]) * I4, 1),
                         round(num(x["Sx"]) * I3, 1), round(num(x["Sy"]) * I3, 1), round(num(x["rx"]) * 2.54, 2), round(num(x["ry"]) * 2.54, 2)])
        out.append(mseries("US-" + sid, "AISC (USA)", name, fam, "ASTM A6/A6M — AISC Shapes Database v16.0", "steelpy", "pub", rows,
                           "Published weight in lb/ft converted exactly to kg/m (× 1.48816)."))
    rows = []
    for x in rd("L_shapes.csv"):
        rows.append([frac_name(x["shape"]), num(x["d"]) * IN, num(x["b"]) * IN, num(x["t"]) * IN, None,
                     round(num(x["area"]) * I2, 2), round(num(x["weight"]) * LBFT, 2), round(num(x["Ix"]) * I4, 1), round(num(x["Iy"]) * I4, 1),
                     round(num(x["rx"]) * 2.54, 2), round(num(x["ry"]) * 2.54, 2)])
    out.append(mseries("US-L", "AISC (USA)", "L angle", "L", "ASTM A6/A6M — AISC Shapes Database v16.0", "steelpy", "pub", rows))
    rows = []
    for x in rd("WT_shapes.csv"):
        rows.append([x["shape"].replace("_", "."), num(x["d"]) * IN, num(x["bf"]) * IN, num(x["tw"]) * IN, num(x["tf"]) * IN,
                     round(num(x["area"]) * I2, 2), round(num(x["weight"]) * LBFT, 2), round(num(x["Ix"]) * I4, 1), round(num(x["Iy"]) * I4, 1)])
    out.append(mseries("US-WT", "AISC (USA)", "WT structural tee", "T", "ASTM A6/A6M — AISC Shapes Database v16.0", "steelpy", "pub", rows))
    rows = []
    for x in rd("HSS_shapes.csv"):
        rows.append([frac_name(x["shape"]), num(x["Ht"]) * IN, num(x["B"]) * IN, num(x["tnom"]) * IN,
                     round(num(x["area"]) * I2, 2), round(num(x["weight"]) * LBFT, 2), round(num(x["Ix"]) * I4, 1), round(num(x["Iy"]) * I4, 1),
                     round(num(x["Sx"]) * I3, 1), round(num(x["Sy"]) * I3, 1)])
    out.append(mseries("US-HSS", "AISC (USA)", "HSS rectangular / square", "RHS", "ASTM A500 — AISC Shapes Database v16.0", "steelpy", "pub", rows,
                       "t = nominal wall; AISC area/weight use design wall 0.93 t (ERW)."))
    rows = []
    for x in rd("HSS_R_shapes.csv"):
        rows.append([x["shape"].replace("_", ".").replace("X", "×"), round(num(x["OD"]) * IN, 1), round(num(x["tnom"]) * IN, 2),
                     round(num(x["area"]) * I2, 2), round(num(x["weight"]) * LBFT, 2), round(num(x["Ix"]) * I4, 1), round(num(x["Sx"]) * I3, 1), ""])
    out.append(mseries("US-HSSR", "AISC (USA)", "HSS round", "CHS", "ASTM A500 — AISC Shapes Database v16.0", "steelpy", "pub", rows,
                       "t = nominal wall; AISC area/weight use design wall 0.93 t (ERW)."))
    rows = []
    for x in rd("PIPE_shapes.csv"):
        rows.append([x["shape"], round(num(x["OD"]) * IN, 1), round(num(x["tnom"]) * IN, 2), round(num(x["area"]) * I2, 2),
                     round(num(x["weight"]) * LBFT, 2), round(num(x["Ix"]) * I4, 1), round(num(x["Sx"]) * I3, 1), ""])
    out.append(mseries("US-PIPE", "AISC (USA)", "Pipe (STD / XS / XXS)", "CHS", "ASTM A53 Gr B — AISC Shapes Database v16.0", "steelpy", "pub", rows))
    return out


def osdag(sqlpath):
    c = sqlite3.connect(":memory:")
    c.executescript(open(sqlpath, encoding="utf-8").read())
    out = []

    def grp_rows(table, fam):
        res = {}
        for x in c.execute(f'select * from "{table}"'):
            cols = [d[0] for d in c.execute(f'select * from "{table}" limit 1').description]
            break
        for x in c.execute(f'select * from "{table}"'):
            d = dict(zip(cols, x))
            nm = re.sub(r"\s+", " ", str(d["Designation"]).strip())
            pre = re.match(r"[A-Z()]+", nm)
            pre = pre.group(0) if pre else ""
            res.setdefault(pre, []).append(d)
        return res

    names = {"MB": "MB (ISMB) medium beam", "LB": "LB (ISLB) light beam", "JB": "JB (ISJB) junior beam", "WB": "WB (ISWB) wide flange beam",
             "LB(P)": "LB(P) light beam (parallel)", "NPB": "NPB narrow parallel flange beam", "WPB": "WPB wide parallel flange beam",
             "HB": "HB (ISHB) column", "SC": "SC (ISSC) column", "PBP": "PBP bearing pile",
             "MC": "MC (ISMC) medium channel", "MPC": "MPC (ISMCP) parallel flange channel", "LC": "LC (ISLC) light channel", "JC": "JC (ISJC) junior channel"}
    for table, fam in [("Beams", "I"), ("Columns", "I"), ("Channels", "C")]:
        for pre, lst in grp_rows(table, fam).items():
            rows = []
            for d in lst:
                rows.append([re.sub(r"\s+", " ", d["Designation"].strip()).replace(" x ", "×"), d["D"], d["B"], d["tw"], d["T"], d["R1"],
                             d["Area"], d["Mass"], d["Iz"], d["Iy"], d["Zz"], d["Zy"], d["rz"], d["ry"]])
            rows.sort(key=lambda z: (z[1], z[7]))
            if pre in ("UB", "UC"):
                out.append(mseries("BS-" + pre, "BS (UK)", {"UB": "UB universal beam", "UC": "UC universal column"}[pre], "I",
                                   "BS 4-1:2005", "osdag", "pub", rows, "BS 4-1 rows as held in the Osdag database; mass equals the serial designation mass."))
            else:
                out.append(mseries("IS-" + pre.replace("(", "").replace(")", ""), "IS 808 (India)", names.get(pre, pre), fam,
                                   "IS 808:1989 (revised designations)", "osdag", "pub", rows,
                                   "IS 808:1989 values. Older ISMB/ISMC tables (IS 808:1964) have different masses for some sizes — confirm which your mill rolls."))
    for table, nm in [("EqualAngle", "Equal angle ISA"), ("UnequalAngle", "Unequal angle ISA")]:
        rows = []
        for x in c.execute(f'select Designation,a,b,t,R1,Area,Mass,Iz,Iy,rz,ry from "{table}"'):
            rows.append(["ISA " + re.sub(r"[∠\s]", "", x[0]).replace("x", "×")] + list(x[1:]))
        rows.sort(key=lambda z: (z[1], z[2], z[3]))
        out.append(mseries("IS-" + table, "IS 808 (India)", nm, "L", "IS 808:1989", "osdag", "pub", rows))
    for table, nm in [("SHS", "SHS"), ("RHS", "RHS")]:
        rows = []
        for x in c.execute(f'select D,B,T,W,A,Izz,Iyy,Zzz,Zyy from "{table}"'):
            rows.append([f"{nm} {x[0]:g}×{x[1]:g}×{x[2]:g}", x[0], x[1], x[2], x[4], x[3], x[5], x[6], x[7], x[8]])
        rows.sort(key=lambda z: (z[1], z[2], z[3]))
        out.append(mseries("IS-" + nm, "IS (India)", nm + " (IS 4923)", "RHS", "IS 4923:1997", "osdag", "pub", rows))
    rows = []
    for x in c.execute('select NB,OD,T,W,A,I,Z from "CHS"'):
        rows.append([f"CHS {x[1]:g}×{x[2]:g}", x[1], x[2], x[4], x[3], x[5], x[6], f"NB {x[0]}"])
    rows.sort(key=lambda z: (z[1], z[2]))
    out.append(mseries("IS-CHS", "IS (India)", "CHS (IS 1161)", "CHS", "IS 1161:2014", "osdag", "pub", rows))
    return out


def pipes():
    import fluids.piping as p
    out = []

    def mass(D, t):
        return round(0.0246615 * (D - t) * t, 2)

    def area(D, t):
        return round(math.pi * t * (D - t) / 100, 2)

    for sch in ["5", "10", "20", "30", "40", "STD", "60", "80", "XS", "100", "120", "140", "160", "XXS"]:
        N, Di, Do, t = p.schedule_lookup[sch]
        rows = [[f"NPS {nps_label(n)} Sch {sch}", round(D, 1), round(tt, 2), area(D, tt), mass(D, tt), None, None, nps_label(n)] for n, D, tt in zip(N, Do, t)]
        out.append(mseries("ASME-" + sch, "Pipe — ASME (steel)", f"ASME B36.10M Sch {sch}", "CHS", "ASME B36.10M-2004", "fluids", "stdf", rows,
                           "Mass by the B36.10M formula 0.0246615 (D − t) t — the method used for the standard's tabulated plain-end weights."))
    for sch in ["5S", "10S", "40S", "80S"]:
        N, Di, Do, t = p.schedule_lookup[sch]
        rows = [[f"NPS {nps_label(n)} Sch {sch}", round(D, 1), round(tt, 2), area(D, tt), mass(D, tt), None, None, nps_label(n)] for n, D, tt in zip(N, Do, t)]
        out.append(mseries("ASME-" + sch, "Pipe — ASME (stainless)", f"ASME B36.19M Sch {sch}", "CHS", "ASME B36.19M-2004", "fluids", "stdf", rows,
                           "Mass shown at 7850 kg/m³ (carbon steel basis). The calculator rescales by the selected density (304: 7900, 316: 8000)."))
    # EN 10255 M / H: nominal OD per EN 10255 with the BS 1387 wall thicknesses
    en_od = [13.5, 17.2, 21.3, 26.9, 33.7, 42.4, 48.3, 60.3, 76.1, 88.9, 114.3, 139.7, 165.1]
    inch = ["1/4", "3/8", "1/2", "3/4", "1", "1-1/4", "1-1/2", "2", "2-1/2", "3", "4", "5", "6"]
    for key, ser in [("BS1387MEDIUM", "M"), ("BS1387HEAVY", "H")]:
        DN, Di, Do, t = p.schedule_lookup[key]
        rows = [[f'DN {int(dn)} ({ins}") {ser}', D, tt, area(D, tt), mass(D, tt), None, None, f'{ins}" (DN {int(dn)})'] for dn, D, tt, ins in zip(DN, en_od, t, inch)]
        out.append(mseries("EN10255-" + ser, "Pipe — GI / MS (EN 10255 / BS 1387)", f"EN 10255 {'Medium' if ser == 'M' else 'Heavy'} (BS 1387 {'B' if ser == 'M' else 'C'} class)",
                           "CHS", "EN 10255:2004", "en10255", "calc", rows,
                           "Mass calculated with EN 10220 formula (black, plain end). Printed EN 10255 table masses run up to ≈1% higher, threaded & socketed more — use the mill certificate for billing."))
    DN, Di, Do, t = p.schedule_lookup["BS1387LIGHT"]
    rows = [[f'DN {int(dn)} ({ins}") L', D, tt, area(D, tt), mass(D, tt), None, None, f'{ins}" (DN {int(dn)})'] for dn, D, tt, ins in zip(DN, Do, t, inch)]
    out.append(mseries("BS1387-L", "Pipe — GI / MS (EN 10255 / BS 1387)", "BS 1387 Light (A class, withdrawn)", "CHS", "BS 1387:1985 (withdrawn)", "fluids", "calc", rows,
                       "OD = maximum OD per BS 1387 Light; mass calculated with EN 10220 formula."))
    for sch in ["40", "80", "120"]:
        N, Di, Do, t = p.schedule_lookup[sch + "D1785"]
        rows = [[f"PVC NPS {nps_label(n)} Sch {sch}", round(D, 1), round(tt, 2), area(D, tt), None, None, None, nps_label(n)] for n, D, tt in zip(N, Do, t)]
        out.append(mseries("PVC-" + sch, "Pipe — PVC", f"PVC ASTM D1785 Sch {sch}", "CHS", "ASTM D1785", "fluids", "dim", rows,
                           "Dimensions only. Mass needs the compound density from the manufacturer (not verified here)."))
    return out


def swg():
    import fluids.piping as p
    g = p.wire_schedules["BSWG"]
    return [[int(a), round(b, 4)] for a, b in zip(g[0], g[1]) if a == int(a) and 6 <= a <= 30]


def awg():
    rows = []
    for n in list(range(-3, 41)):
        d = 0.127 * 92 ** ((36 - n) / 39)
        lab = {-3: "4/0", -2: "3/0", -1: "2/0", 0: "1/0"}.get(n, str(n))
        rows.append([lab, round(d, 4), round(math.pi / 4 * d * d, 4)])
    return rows


def build(args):
    series = []
    series += euro(args.eurocodepy)
    series += sc_profiles(args.structuralcodes)
    series += osdag(pathlib.Path(args.osdag) / "src/osdag/data/ResourceFiles/Database/Intg_osdag.sql")
    series += aisc(args.steelpy)
    series += pipes()
    # drop empty rows / round floats
    for s in series:
        rows = []
        for row in s["rows"]:
            if not row[0]:
                continue
            row[0] = re.sub(r"\s*[xXⅹ]\s*(?=\d)", "×", str(row[0])).replace("  ", " ")
            rows.append([(round(v, 2) if isinstance(v, float) else v) for v in row])
        s["rows"] = rows
    return {
        "rev": REV,
        "src": SOURCES,
        "units": UNITS,
        "mat": [dict(zip(["id", "grp", "name", "grade", "rho", "st", "src", "note"], m)) for m in MATERIALS],
        "rebar": {"bs4449": REBAR_BS4449, "a615": REBAR_A615},
        "iec60228": IEC60228,
        "gauge": GALV_GAUGE,
        "awg": awg(),
        "swg": swg(),
        "series": series,
    }


def pkgpath(mod):
    spec = importlib.util.find_spec(mod)
    if not spec:
        sys.exit(f"missing package: pip install {mod}")
    return str(pathlib.Path(spec.origin).parent.parent)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="dashboard index.html to update")
    ap.add_argument("--osdag", required=True, help="Osdag repository checkout")
    ap.add_argument("--json", help="also write the JSON here")
    a = ap.parse_args()
    a.eurocodepy = pkgpath("eurocodepy")
    a.steelpy = pkgpath("steelpy")
    a.structuralcodes = pkgpath("structuralcodes")
    data = build(a)
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    html = pathlib.Path(a.html)
    text = html.read_text(encoding="utf-8")
    pat = re.compile(r'(<script type="application/json" id="calcData">)(.*?)(</script>)', re.S)
    if not pat.search(text):
        sys.exit('no <script type="application/json" id="calcData"> block in ' + a.html)
    text = pat.sub(lambda m: m.group(1) + js + m.group(3), text, count=1)
    html.write_text(text, encoding="utf-8")
    n = sum(len(s["rows"]) for s in data["series"])
    print(f"calcData: {len(data['series'])} series, {n} sections/pipes, {len(data['mat'])} materials, {len(js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
