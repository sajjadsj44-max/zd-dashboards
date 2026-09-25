#!/usr/bin/env python3
"""Laboratory concrete mix designs for Rate Analysis -> "Concrete Mix Design - Lab Rate Analysis".

Transcribed on 25-Sep-2026 from 15 photos of lab-approved mix designs sent by Sajjad.
Every figure is typed exactly as printed. Anything that cannot be read, or that the
sheet does not state, is listed under "verify" -- nothing is guessed.

Writes the <script type="application/json" id="raLabMixData"> block of
zameen-developments/index.html:

    tools/lab_mix_data.py zameen-developments/index.html
    python3 -m unittest tools/test_lab_mix_data.py

Material rows: t = cem | bin | sand | agg | water | adm, n = name, kg = kg per 1 m3 as
printed, code = Rate Database line ("@sand" / "@agg" = the Rate Analysis default sand /
crush from Data & Settings, used when the sheet does not name a source).
"""
import json, re, sys

REV = "2026-09-25-lab1"
TODAY = "2026-09-25"

# ---- Lab A: Excel ACI-211.1 workbook (photos 1-6) --------------------------------------
XL_LAB = "Not shown — Excel ACI-211.1 mix-design workbook (sheet tabs 'TM … psi WCH')"
XL_VERIFY = [
    "Laboratory name is not shown on the photo",
    "Concrete strength (psi) is not shown on this sheet. Photo 4 shows workbook tabs "
    "'TM 5000psi WCH (7)', 'TM 4000psi WCH (8)', 'TM 3000psi WCH (9)'; which tab this sheet is cannot be confirmed",
    "Date of mix / trial not shown",
    "Sand and crush sources not shown — linked to the Rate Analysis default sand and crush",
]


def xl(no, cem, w_unc, w, adm_unc, adm, ca_unc, ca, c20_unc, c20, c12_unc, c12, fa_unc, fa,
       tot_unc, tot, batch, vols, slump=None, abs_wt=1036.20):
    info = [
        "Method: ACI 211.1 absolute volume (ACI Table 211-A1.5.3.6, volume base of coarse aggregate 0.66), "
        "dry-rodded unit wt × volume base = absolute wt of total aggregates %s kg" % abs_wt,
        "Uncorrected weights per 1 m³ (kg): cement %s · water %s · admixture %s · combined C.A. %s "
        "(20 mm %s + 12 mm %s + pan/5 mm 0.0) · sand-1 %s · total %s" % (
            cem, w_unc, adm_unc, ca_unc, c20_unc, c12_unc, fa_unc, tot_unc),
        "Corrected weights per 1 m³ (kg) used here: cement %s · water %s · admixture %s · C.A. %s "
        "(20 mm %s + 12 mm %s + pan/5 mm 0) · sand-1 %s · total %s" % (cem, w, adm, ca, c20, c12, fa, tot),
        "Trial batch 0.014 m³ weights (kg): " + batch,
        "Absolute volumes (m³): " + vols,
    ]
    if slump:
        info.append(slump)
    mats = [
        {"t": "cem", "n": "Cement (1)", "kg": cem, "code": "CEM"},
        {"t": "water", "n": "Water (corrected)", "kg": w, "code": "WATER"},
    ]
    if adm:
        mats.append({"t": "adm", "n": "Admixture (product not named on sheet)", "kg": adm, "code": "ADMIX-SP",
                     "flag": "Admixture product not named — linked to ADMIX-SP"})
    mats += [
        {"t": "agg", "n": "1 — C.A. 20 mm (3/4\")", "kg": c20, "code": "@agg"},
        {"t": "agg", "n": "2 — C.A. 12 mm (1/2\")", "kg": c12, "code": "@agg"},
        {"t": "sand", "n": "F.A. (Sand-1)", "kg": fa, "code": "@sand"},
    ]
    return {
        "id": "LMX-XL-%02d" % no, "photos": [no], "lab": XL_LAB, "project": "",
        "psi": None, "grade": "PSI not shown",
        "ref": "ACI-211.1 workbook sheet — cement %s kg/m³ (photo %d)" % (cem, no),
        "date": "", "method": "ACI 211.1 (absolute volume)", "basis": "Corrected weights per 1 m³",
        "yld": 1, "total": tot, "mats": mats, "info": info,
        "verify": list(XL_VERIFY) + ([] if adm else ["No admixture on this sheet (0.0 kg)"]),
    }


SLUMP_1_6 = ("Fresh concrete: temperature 20 °C; slump initial 'Collapse' (as shown), at 15 min 190 mm "
             "(7.480\"), at 30 min 170 mm (6.693\"), at 45 min 150 mm (5.906\")")

RECS = [
    xl(1, 200, 209.3, 181, 0.0, 0, 1036.2, 1048, 207.2, 209, 829.0, 839, 816.3, 833, 2261.8, 2262,
       "2.80 / 2.53 / 0.00 / 14.67 (2.93 + 11.74 + 0.00) / 11.66 — total 31.665",
       "paste 0.273492 · C.A. 0.395889 · F.A. 0.330619", SLUMP_1_6),
    xl(2, 150, 223.3, 195, 0.0, 0, 1036.2, 1048, 207.2, 209, 829.0, 839, 820.9, 837, 2230.4, 2231,
       "2.10 / 2.73 / 0.00 / 14.67 (2.93 + 11.74 + 0.00) / 11.72 — total 31.227",
       "cement 0.047619 · water 0.204000 · admixture 0 · air 0.020000 · paste 0.271619 · "
       "C.A. 0.395889 (C.A.-1 0.079178, C.A.-2 0.316711) · F.A. 0.332492"),
    xl(3, 320, 185.1, 158, 3.2, 3.2, 1036.2, 1048, 207.2, 209, 829.0, 839, 773.9, 789, 2318.4, 2319,
       "4.48 / 2.21 / 0.04 / 14.67 (2.93 + 11.74 + 0.00) / 11.05 — total 32.459",
       "water 0.166400 · admixture 0.002689 · air 0.020000 · paste 0.290676 · C.A.-2 0.316711 · F.A. 0.313435"),
    xl(4, 530, 201.5, 178, 5.3, 5.3, 1036.2, 1048, 207.2, 209, 829.0, 839, 557.8, 569, 2330.8, 2331,
       "7.42 / 2.50 / 0.07 / 14.67 (2.93 + 11.74 + 0.00) / 7.96 — total 32.631",
       "cement 0.168254 · water 0.185500 · admixture 0.004454 · air 0.020000 · paste 0.378208 · "
       "C.A. 0.39588 (C.A.-1 0.07917, C.A.-2 0.31671) · F.A. 0.225903"),
    xl(5, 400, 194.9, 175, 4.0, 4.0, 1029.6, 1042, 205.9, 208, 823.7, 834, 701.9, 710, 2330.4, 2331,
       "5.60 / 2.44 / 0.06 / 14.58 (2.91 + 11.67 + 0.00) / 9.95 — total 32.627",
       "water 0.172000 · admixture 0.003361 · air 0.020000 · paste 0.322345 · C.A.-2 0.314694 · F.A. 0.284287",
       "Fresh concrete: temperature 20 °C (slump row cut off in photo)", abs_wt=1029.60),
    xl(6, 475, 204.9, 185, 4.8, 4.8, 1036.2, 1048, 207.2, 209, 829.0, 839, 637.4, 645, 2358.2, 2358,
       "6.65 / 2.59 / 0.07 / 14.67 (2.93 + 11.74 + 0.00) / 9.03 — total 33.018",
       "water 0.185250 · admixture 0.003992 · air 0.020000 · paste 0.360035 · C.A.-2 0.315987 · F.A. 0.244981",
       SLUMP_1_6),
]

# ---- Lab B: J7 Group QA/QC (photos 7 and 8 are the same sheet) --------------------------
J7_LAB = "J7 Group QA/QC — Concrete Batching Plant, Multi Garden (B-17)"
J7_ROWS = [  # psi, cement, water, admix kg, dosage %, 1/2", 3/8", 1/4", sand, TM, TM date
    (3000, 325, 192, 3.25, "1.0", 105, 738, 211, 760, "16", "2024-01-17"),
    (4000, 425, 192, 5.61, "1.32", 105, 738, 211, 671, "11", "2024-01-13"),
    (4500, 465, 186, 6.51, "1.4", 105, 738, 211, 649, "15", "2024-01-17"),
    (5000, 515, 191, 7.29, "1.42", 105, 738, 211, 593, "12", "2024-01-15"),
    (5500, 530, 191, 7.5, "1.42", 105, 738, 211, 579, "13", "2024-01-15"),
]
for psi, cem, w, ad, pct, c12, c38, c14, sand, tm, d in J7_ROWS:
    v = ["Crush and sand sources not shown — linked to the Rate Analysis default sand and crush",
         "Crush 1/4\" has no separate Rate Database line — priced at the default crush line; confirm"]
    calc = round(float(pct) / 100 * cem, 2)
    if abs(calc - ad) > 0.01:
        v.append("Admixture printed %s kg; %s%% × %s kg cement = %s kg — printed value used" % (ad, pct, cem, calc))
    dd = d.split("-")
    RECS.append({
        "id": "LMX-J7-%d" % psi, "photos": [7, 8], "lab": J7_LAB, "project": "J7 Group Emporium Mall B-17",
        "psi": psi, "grade": "%d psi" % psi,
        "ref": "Summary of Concrete Batch Weights 1 m³ — TM # %s (%s-%s-%s)" % (tm, dd[2], dd[1], dd[0]),
        "date": d, "method": "Batching-plant trial mix (TM)", "basis": "Batch weights per 1 m³",
        "yld": 1, "total": round(cem + w + ad + c12 + c38 + c14 + sand, 2),
        "mats": [
            {"t": "cem", "n": "Cement", "kg": cem, "code": "CEM"},
            {"t": "water", "n": "Water", "kg": w, "code": "WATER"},
            {"t": "adm", "n": "Admixture Imp.540 M (%s%% by cement, Sg 1.18)" % pct, "kg": ad, "sg": 1.18,
             "code": "ADMIX-SP", "flag": "Imp.540 M has no Rate Database line — priced at ADMIX-SP (FosPak SP 568); confirm"},
            {"t": "agg", "n": "Crush 1/2\"", "kg": c12, "code": "@agg"},
            {"t": "agg", "n": "Crush 3/8\"", "kg": c38, "code": "@agg"},
            {"t": "agg", "n": "Crush 1/4\"", "kg": c14, "code": "@agg"},
            {"t": "sand", "n": "Sand", "kg": sand, "code": "@sand"},
        ],
        "info": [
            "Sheet: J7 Group Emporium Mall B-17 — Summary of Concrete Batch Weights 1 (M)³, Concrete Batching Plant "
            "Multi Garden (B-17). Remarks column: TM # %s (%s)" % (tm, "-".join(reversed(dd))),
            "Prepared by QA/QC Manager 08-03-24 · Reviewed by Project Manager · Approved by Director Engineering Division (signed)",
            "Handwritten note: 1- Applicable to all J7 Group projects. 2- Under strict observation, QA/QC team to "
            "observe performance and report monthly with recommendations",
            "Photos 7 and 8 are the same sheet (duplicate photo) — entered once",
        ],
        "verify": v,
    })

# ---- Lab C: ACI-211.1 5000 psi sheet, date of mixing 05-04-26 (photo 9) ----------------
RECS.append({
    "id": "LMX-ACI5K-01", "photos": [9], "lab": "Not shown — 'Concrete Mix Design (5000 PSI) Method ACI-211.1' sheet",
    "project": "", "psi": 5000, "grade": "5000 psi",
    "ref": "Concrete Mix Design (5000 PSI), Method ACI-211.1 — date of mixing 05-04-26",
    "date": "2026-04-05", "method": "ACI 211.1 (absolute volume)", "basis": "Corrected weights per 1 m³",
    "yld": 1, "total": 2439,
    "mats": [
        {"t": "cem", "n": "Cement OPC", "kg": 550, "code": "CEM"},
        {"t": "water", "n": "Water", "kg": 187, "code": "WATER"},
        {"t": "agg", "n": "C/Agg 19 mm to 12 mm (3/4\"–1/2\"), 40% — Sargodha", "kg": 418.60, "code": "CRSH-SG"},
        {"t": "agg", "n": "C/Agg 12 mm to 05 mm (1/2\"–3/16\"), 60% — Sargodha", "kg": 627.90, "code": "CRSH-SG"},
        {"t": "sand", "n": "Fine aggregate (sand) — Lawrencepur", "kg": 647.70, "code": "SAND-LP"},
        {"t": "adm", "n": "Admixture Sika-520BA / Vertex G-880 (1.2 L per 100 kg cement, Sg 1.165)", "kg": 7.69,
         "sg": 1.165, "code": "ADMIX-SP",
         "flag": "Sika-520BA / Vertex G-880 has no Rate Database line — priced at ADMIX-SP (FosPak SP 568); confirm"},
    ],
    "info": [
        "Sources: coarse agg Sargodha ('Sargdha'), fine agg Lawrencepur ('Lawrance Pur'), cement OPC",
        "Design data: W/C 0.34 · design cement 550 kg/m³ · max water 187 kg · admixture 7.69 kg · air 2.00% · "
        "FM of sand 2.40 · Sg cement 3.150, admixture 1.165, F.A. 2.650, C.A. 2.857 · unit wt C.A. 1.610 · "
        "C/Agg factor (Table A1.5.3.6) 0.650",
        "Volumes (m³): cement 0.174603 · water 0.187000 · admixture 0.007689 · air 0.020000 · paste 0.389292 · "
        "C.A. 0.366293 · F.A. 0.244415 (sum 1.000000)",
        "Wt of C.A. 1046.50 kg; absorption C.A. 0.96% (10.05 kg), F.A. 1.30% (8.42 kg), total 18.47",
        "Density of mix 2439 kg/m³ (uncorrected = corrected)",
    ],
    "verify": ["Laboratory name is not shown on the photo",
               "'Required Strength (20% Extra)' value is blank on the sheet",
               "Corrected weights equal the uncorrected weights — no moisture correction applied on the sheet"],
})

# ---- Lab D: ready-mix plant sheets, DHA Multan (photos 10-14) ---------------------------
MUL_LAB = "Not shown — ready-mix plant mix-design sheets, DHA Multan (BS 882:1992 grading)"
MUL_INFO = ("Grading (same on every sheet): 20 mm aggregate + 10 mm aggregate combined within BS 882:1992 Table 5 "
            "limits; 5 mm sand + dune sand combined within Table 4 limits. Stamp tolerance per table 23 of 206:2013. "
            "Sources 'as per customer demand' — coarse: Margala / Sargodha / Sakhi Sarwar; fine: Margala / "
            "Lawrencepur / Zinda Pir / Sakhi Sarwar; admixture: Sika 512 Pk / Ultra Sp 437 / Sika 520 BA / Ultra 470 / "
            "Fospak 511 / Fospak 560; cement: DG / Maple Leaf / Lucky / Fauji / Bestway")
MUL = [  # photo, psi, grade, binder, 20mm, 10mm, sand name, sand code, sand kg, admix2, water, temp, slump, code
    (10, 1000, "1000 psi", 200, 650, 420, "Lawrencepur sand", "SAND-LP", 850, 0, 210, "= 32", "—",
     "Location and mix code cut off at top of photo"),
    (11, 6000, "6000 psi", 550, 628, 416, "Lawrencepur sand", "SAND-LP", 590, 5.0, 212, "≤ 32",
     "initial 175 mm (6.890\") · 30 min 155 mm (6.102\") · 60 min 115 mm (4.528\") · 90 min 85 mm (3.346\")",
     "Mix code partly cut off (reads LC-06 or LC-08)"),
    (12, 4500, "4500 psi", 475, 630, 420, "Lawrencepur sand", "SAND-LP", 662, 4.7, 208, "≤ 32",
     "initial 190 mm (7.480\") · 30 min 165 mm (6.496\") · 60 min 125 mm (4.921\") · 90 min 90 mm (3.543\")",
     "Location and mix code cut off at top of photo"),
    (13, 4000, "4000 psi", 450, 630, 420, "Lawrencepur sand", "SAND-LP", 690, 4.3, 206, "≤ 32",
     "initial 185 mm (7.283\") · 30 min 160 mm (6.299\") · 60 min 130 mm (5.118\") · 90 min 100 mm (3.937\")",
     "Location and mix code cut off at top of photo"),
    (14, None, "1:3:6 nominal", 250, 642, 420, "Zinda Pir sand", "", 810, 0, 213, "≤ 32", "—",
     "Location and mix code cut off at top of photo"),
]
for ph, psi, grade, b, a20, a10, sn, sc, sk, ad, w, temp, slump, cut in MUL:
    mats = [
        {"t": "cem", "n": "OPC", "kg": b, "code": "CEM"},
        {"t": "agg", "n": "20 mm (3/4\") crushed aggregate", "kg": a20, "code": "@agg"},
        {"t": "agg", "n": "10 mm (3/8\") crushed aggregate", "kg": a10, "code": "@agg"},
        dict({"t": "sand", "n": sn, "kg": sk, "code": sc},
             **({} if sc else {"flag": "Zinda Pir sand has no Rate Database line — rate needed"})),
    ]
    if ad:
        mats.append({"t": "adm", "n": "Admixture-2 (product not named)", "kg": ad, "code": "ADMIX-SP",
                     "flag": "Admixture-2 product not named — priced at ADMIX-SP (FosPak SP 568); confirm"})
    mats.append({"t": "water", "n": "Free water", "kg": w, "code": "WATER"})
    v = ["Laboratory / plant name is not shown on the photo", cut, "Date not shown"]
    if psi:
        v.append("Crush source 'as per customer demand' (Margala / Sargodha / Sakhi Sarwar) — linked to the default crush")
    else:
        v.append("Mix class printed as '1:3:6 Ratio' — no psi stated")
        v.append("Crush source 'as per customer demand' — linked to the default crush")
    RECS.append({
        "id": "LMX-MUL-%s" % (psi or "136"), "photos": [ph], "lab": MUL_LAB, "project": "DHA Multan",
        "psi": psi, "grade": grade,
        "ref": "Mix class %s — total binder %d kg/m³ (photo %d)" % (grade.replace(" nominal", " ratio"), b, ph),
        "date": "", "method": "Ready-mix plant design (BS 882:1992 grading)", "basis": "Batch weights per 1 m³",
        "yld": 1, "total": round(b + a20 + a10 + sk + ad + w, 2), "mats": mats,
        "info": ["Total binder %d kg/m³ (OPC %d, GGBS 0, micro silica 0) · air content 2%% · "
                 "fresh concrete temperature %s °C" % (b, b, temp),
                 "Blending sand — · Admixture (Sika 512 Pk) — · Admixture-2 %s" % (ad or "—"),
                 "Slump ranges: " + slump, MUL_INFO],
        "verify": v,
    })

# ---- Lab E: 'Concrete Mix Design ACI-211' batch weight sheet (photo 15) ----------------
ACI = [  # psi, cement, sand, 1/2, 3/8, 2/8, admix, water, total
    (1500, 180, 810, None, None, None, 0, 180, 2390),
    (4000, 350, 780, 392, 550, 165, 4.6, 160, 2401),
    (4500, 400, 740, 340, 540, 220, 4.8, 168, 2412),
    (6000, 520, 660, 321, 588, 160, 6.2, 178, 2433),
]
for psi, cem, sand, c12, c38, c28, ad, w, tot in ACI:
    if c12 is None:
        agg = [{"t": "agg", "n": "Crush 1/2\" + 3/8\" + 2/8\" (\"1220 KG mix\")", "kg": 1220, "code": "@agg"}]
    else:
        agg = [{"t": "agg", "n": "Crush 1/2\"", "kg": c12, "code": "@agg"},
               {"t": "agg", "n": "Crush 3/8\"", "kg": c38, "code": "@agg"},
               {"t": "agg", "n": "Crush 2/8\" (1/4\")", "kg": c28, "code": "@agg"}]
    mats = [{"t": "cem", "n": "Cement", "kg": cem, "code": "CEM"},
            {"t": "sand", "n": "Sand", "kg": sand, "code": "@sand"}] + agg
    if ad:
        mats.append({"t": "adm", "n": "Admixture (product not named)", "kg": ad, "code": "ADMIX-SP",
                     "flag": "Admixture product not named — priced at ADMIX-SP (FosPak SP 568); confirm"})
    mats.append({"t": "water", "n": "Water", "kg": w, "code": "WATER"})
    RECS.append({
        "id": "LMX-ACI-%d" % psi, "photos": [15], "lab": "Not shown — 'Concrete Mix Design ACI-211' batch weight sheet",
        "project": "", "psi": psi, "grade": "%d psi" % psi,
        "ref": "Concrete Mix Design ACI-211 — batch weight for 1 m³, %d psi column" % psi,
        "date": "", "method": "ACI 211", "basis": "Batch weights per 1 m³", "yld": 1, "total": tot, "mats": mats,
        "info": ["Printed total weight %d kg; signed blocks: QA/QC Manager, Lab Incharge" % tot,
                 "Same sheet as the Item Library items RCC-DM-ACI-%d (added 23-Sep-2026)" % psi],
        "verify": ["Laboratory name is not shown on the photo", "Date not shown",
                   "Sand and crush sources not shown — linked to the Rate Analysis default sand and crush"]
                  + (["Crush 2/8\" has no separate Rate Database line — priced at the default crush line; confirm"]
                     if c12 else []),
    })

PHOTOS = [
    [1, "Excel ACI-211.1 sheet — cement 200", ["LMX-XL-01"]],
    [2, "Excel ACI-211.1 sheet — cement 150", ["LMX-XL-02"]],
    [3, "Excel ACI-211.1 sheet — cement 320", ["LMX-XL-03"]],
    [4, "Excel ACI-211.1 sheet — cement 530", ["LMX-XL-04"]],
    [5, "Excel ACI-211.1 sheet — cement 400", ["LMX-XL-05"]],
    [6, "Excel ACI-211.1 sheet — cement 475", ["LMX-XL-06"]],
    [7, "J7 Group Emporium Mall B-17 batch weight summary", ["LMX-J7-3000", "LMX-J7-4000", "LMX-J7-4500",
                                                            "LMX-J7-5000", "LMX-J7-5500"]],
    [8, "Duplicate of photo 7 (same sheet)", []],
    [9, "Concrete Mix Design (5000 PSI) ACI-211.1, 05-04-26", ["LMX-ACI5K-01"]],
    [10, "Ready-mix sheet — 1000 psi", ["LMX-MUL-1000"]],
    [11, "Ready-mix sheet — 6000 psi, DHA Multan", ["LMX-MUL-6000"]],
    [12, "Ready-mix sheet — 4500 psi", ["LMX-MUL-4500"]],
    [13, "Ready-mix sheet — 4000 psi", ["LMX-MUL-4000"]],
    [14, "Ready-mix sheet — 1:3:6 ratio", ["LMX-MUL-136"]],
    [15, "Concrete Mix Design ACI-211 batch weights (1500/4000/4500/6000)", ["LMX-ACI-1500", "LMX-ACI-4000",
                                                                           "LMX-ACI-4500", "LMX-ACI-6000"]],
]

DATA = {
    "rev": REV, "received": TODAY,
    "source": "15 photos of lab-approved concrete mix designs sent by Sajjad, transcribed 25-Sep-2026",
    "dens": {"sand": 46.65, "agg": 41.00,
             "src": "Al Rafiq Ready Mix mix-design summary CFT columns (received 23-Sep-2026) — the same "
                    "kg → Cft conversion the Item Library design mixes use; an assumption for other labs' materials"},
    "photos": PHOTOS, "recs": RECS,
}


def check():
    ids = [r["id"] for r in RECS]
    assert len(ids) == len(set(ids)), "duplicate id"
    mapped = sorted(i for p in PHOTOS for i in p[2])
    assert mapped == sorted(ids), "photo register does not cover every record"
    for r in RECS:
        s = sum(m["kg"] for m in r["mats"])
        # printed totals are rounded sums; allow 1.5 kg
        assert abs(s - r["total"]) <= 1.5, (r["id"], s, r["total"])
    return True


def write(path):
    check()
    html = open(path, encoding="utf-8").read()
    blob = json.dumps(DATA, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tag = '<script type="application/json" id="raLabMixData">'
    new = tag + blob + "</script>"
    if tag in html:
        html = re.sub(re.escape(tag) + r".*?</script>", lambda m: new, html, count=1, flags=re.S)
    else:
        anchor = '<script type="application/json" id="raKpkData">'
        assert anchor in html
        html = html.replace(anchor, new + "\n" + anchor, 1)
    open(path, "w", encoding="utf-8").write(html)
    print("%d records from %d photos written to %s" % (len(RECS), len(PHOTOS), path))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    write(sys.argv[1])
