# Civil gap rate analyses — review of the 26-Sep-2026 benchmark list

Source reviewed: `QS_Rate_Analysis_Lahore_2026_All_Missing.txt` (Sajjad, 26-Sep-2026) — 130 missing civil
analyses, 3 repair analyses and 5 seed items to repair. Result: **133 new Item Library analyses
(CV-001 … CV-130, CV-R01 … CV-R03)** and **3 seed items repaired** (FN-560, EW-950, EW-960), written by
`tools/civil_gap_data.py` into the `#raCivilData` block of the dashboard.

## What was wrong with the list

1. **Input rates disagree with the library's dated rates.** The list uses cement 1,450 / bag, sand 60 / cft,
   crush 175 / cft and Grade 60 steel 262 / kg. The library holds cement 1,575 (market dashboard,
   05-Sep-2026, band 1,520–1,605), Chenab sand 80 (Phoenix GRN RCP-316, 07-Sep-2026), Ravi sand 52
   (Phoenix GRN RCP-310, 27-Aug-2026), crush 185 (04-Sep-2026) and Grade 60 steel 242 (Phoenix GRN RCP-312,
   30-Aug-2026). The list's figures come from a planning index (finishes.pk, 21-Aug-2026) that could not be
   opened from here; the library's rates were kept.
2. **Helper wage below the legal minimum.** The list uses 1,400 / day and the library used 1,300. Punjab's
   minimum wage notification of 01-May-2026 sets PKR 40,000 per month for an unskilled adult = 1,538 per day
   (26 days). `L-HELPER` is now 1,538 (applied only where the line still holds the published 1,300).
3. **Arithmetic.** Item 1 (dismantling brickwork) shows 0.055 mason-day × 2,400 + 0.020 helper-day × 1,400
   = 160, but prices it at 55. Item 8 prices a PC200-class excavator at 1,000 cft per day, which is a small
   fraction of its output; the MRS 2026 composite for machine excavation 5–15 ft is 13.02 per cft, not 60.
4. **Wrong product priced.** Welded mesh (31) and structural steel (115) are priced at the rebar rate; lean
   RMC (16) at 520 per cft when the Phoenix GRN is 270.03 delivered; PVC waterstop (53) at 450 per Rft when
   the library holds a Phoenix GRN at 170.
5. **Sources.** "WEB-2026" items name no site or date, which CLAUDE.md does not allow. Every line in the
   new block names its source and date or says `ASSUMPTION — no dated source`.
6. **Units.** The list uses mm (12 mm, 15 mm, 50 mm, 150–230 mm, 10–12 mm …). The new items are written in
   inches / feet only. Four units were changed to how the work is measured: honeycomb walling (43) and
   brick-on-edge (44) per Sft, MS grill (93) per Sft (MRS measures grills by area), and the door repair (FN-560)
   stays per Sft (the list switched it to Nos).
7. **Duplicates.** RCC sub / super-structure (17, 18) have the same build-up as the existing RCC-RMC-4000;
   they are kept as separate items because the house standard reports sub- and super-structure separately.

## How the analyses were built

* **Built-up (53 items):** quantities × rate lines, A–H. Materials use the library's own lines or the GRN
  register; labour uses the **Punjab MRS 1st Bi-Annual 2026 (Rawalpindi)** labour-only rate for the same
  operation (the same `MRS-C…` codes the MRS register's *+ Rate DB* button creates). The MRS edition's period
  ended 30-Jun-2026, so those lines say "edition lapsed, reconfirm before use".
* **MRS composite (30 items):** where no current material price was found but the MRS prints a composite
  rate for the same item (terrazzo, rolling shutter, uPVC door, kerb stone, deodar door …), that composite is
  one line. Materials in it are at January-2026 prices.
* **Web installed rate (9 items):** SPC, laminate, uPVC window, aluminium door, glass railing, shower
  enclosure, POP and PVC ceilings, epoxy floor — a dated web search result (site and range in the remarks),
  mid-range figure.
* **Assumption (41 items):** nothing dated was found (hoarding, dewatering, shoring, couplers, AAC, curtain
  wall, ACP, septic tank …). Your figure is kept as one line `BM-CV-<n>` marked
  `ASSUMPTION — no dated source`, so the item shows **Assumed** until a quotation replaces it.
  `TOPSOIL` (grassing, CV-128) has no figure at all and is left at 0 — that item shows as incomplete.

Web searches (26-Sep-2026) found usable figures for: Punjab minimum wage, B-class bricks, fly-ash bricks,
bitumen, distemper, tuff pavers, Dhaka grass, SPC, laminate, uPVC windows, aluminium doors, glass railing,
shower enclosures, POP / PVC ceilings, epoxy flooring and fire doors. Supplier and price-list sites could not be
opened from the build environment (egress policy), so figures come from search summaries.

## Shared lines changed

| Line | Was | Now | Source |
|---|---|---|---|
| L-HELPER | 1,300 / day (ASSUMPTION) | 1,538 / day | Punjab Minimum Wages notification, 01-May-2026 |
| BRK-2 | 15 / Nos (ASSUMPTION) | 12.5 / Nos | Web search 26-Sep-2026 — Lahore B-class 11,000–14,000 per 1,000 |

`L-HELPER` is used by nearly every civil item, so their rates rise by 238 × the helper-days in each
(e.g. +11.74 per cft on RCC-RMC-4000). Both lines move only if they still hold the published value.

## Seed items repaired

* **FN-560** flush door — adds the galvanised steel door frame for a 9" wall (Quadrangle GRN RCP-2682,
  18-Aug-2025, 8,500 each ÷ 21 Sft).
* **EW-950** paver block — adds the paver itself (tuff tile, 150 per Sft, web search 26-Sep-2026).
* **EW-960** manhole — adds the materials of a 3 × 3 ft internal, 5 ft deep brick manhole: 9" brick walls
  1:6, 6" PCC 1:4:8 base, ½" plaster, RCC cover slab and a 24" C.I. cover (MRS composite).
* **FN-550 / QS-GYP-P01** gypsum ceiling and partition — **not repaired**: no dated price for gypsum board or
  GI channels was found (only installed-rate ranges), so the QE-GYP-* lines stay at 0 and the items stay
  incomplete. The list's 190 / 360 per Sft are installed rates with no source.

## Rates side by side

Direct cost = A + B + C + D (+E, F), comparable with the list, which excludes OH & P. The dashboard adds 8%
overheads and 10% profit.

| Code | Item | File unit / rate | New unit | Direct cost | With OH 8% + profit 10% | Basis |
|---|---|---|---|---:|---:|---|
| CV-001 | Dismantling brick masonry in cement or lime mortar | Cft 55 | Cft | 69.03 | 81.45 | Built-up |
| CV-002 | Dismantling reinforced cement concrete | Cft 180 | Cft | 292.34 | 344.96 | Built-up |
| CV-003 | Hacking and removing existing cement or lime plaster from walls and ce | Sft 35 | Sft | 6.77 | 7.99 | Built-up |
| CV-004 | Dismantling glazed | Sft 45 | Sft | 37.36 | 44.09 | Built-up |
| CV-005 | Loading | Cft 55 | Cft | 55.00 | 64.90 | Assumption (your figure) |
| CV-006 | Providing | Rft 900 | Rft | 900.00 | 1,062.00 | Assumption (your figure) |
| CV-007 | Setting out and survey with total station / auto-level | Ls 25,000 | Job | 25,000.00 | 29,500.00 | Assumption (your figure) |
| CV-008 | Bulk excavation for basement by excavator in ordinary soil | Cft 60 | Cft | 13.02 | 15.36 | MRS 2026 composite |
| CV-009 | Loading and disposal of surplus excavated earth off site | Cft 45 | Cft | 45.00 | 53.10 | Assumption (your figure) |
| CV-010 | Dewatering excavation by diesel pump sets including operator | Day 22,000 | Day | 22,000.00 | 25,960.00 | Assumption (your figure) |
| CV-011 | Shoring / sheet piling to excavation sides including walers and struts | Sft 2,500 | Sft | 2,500.00 | 2,950.00 | Assumption (your figure) |
| CV-012 | Compaction of natural sub-grade in 6" depth | Sft 35 | Sft | 5.57 | 6.57 | Built-up |
| CV-013 | Supplying and filling Ravi sand under floors in 6" layers | Cft 95 | Cft | 76.22 | 89.94 | Built-up |
| CV-014 | Dry brick soling of 1st class bricks laid flat on ½" sand bed | Sft 105 | Sft | 92.93 | 109.66 | Built-up |
| CV-015 | Providing and laying polythene sheet 1000 gauge (0.01" thick) under PC | Sft 25 | Sft | 15.27 | 18.01 | Built-up |
| CV-016 | Providing and laying ready-mix lean concrete (≈1:4:8) in blinding / su | Cft 520 | Cft | 394.64 | 465.67 | Built-up |
| CV-017 | Providing and laying reinforced cement concrete 4000 psi ready-mix in  | Cft 850 | Cft | 506.95 | 598.20 | Built-up |
| CV-018 | Providing and laying reinforced cement concrete 4000 psi ready-mix in  | Cft 880 | Cft | 506.95 | 598.20 | Built-up |
| CV-019 | Providing and laying reinforced cement concrete 1:2:4 site-mixed in li | Cft 900 | Cft | 685.45 | 808.83 | Built-up |
| CV-020 | Providing and laying water-resisting reinforced cement concrete 4000 p | Cft 1,020 | Cft | 514.81 | 607.47 | Built-up |
| CV-021 | Providing and laying reinforced cement concrete 1:2:4 in coping | Cft 900 | Cft | 685.45 | 808.83 | Built-up |
| CV-022 | Providing | Sft 300 | Sft | 371.76 | 438.67 | Built-up |
| CV-023 | Providing and laying cement concrete 1:2:4 floor topping 2" thick | Sft 155 | Sft | 150.73 | 177.86 | Built-up |
| CV-024 | Power-trowel finishing of concrete floor with dry-shake metallic / qua | Sft 240 | Sft | 240.00 | 283.20 | Assumption (your figure) |
| CV-025 | Formwork to lintels | Sft 75 | Sft | 174.53 | 205.95 | Built-up |
| CV-026 | Formwork to water-tank walls including through-ties | Sft 90 | Sft | 145.08 | 171.19 | Built-up |
| CV-027 | Formwork to slab edges up to 9" deep | Rft 100 | Rft | 85.41 | 100.78 | Built-up |
| CV-028 | Formwork to circular columns with purpose-made curved shutters | Sft 130 | Sft | 130.00 | 153.40 | Assumption (your figure) |
| CV-029 | Steel panel formwork including hire / depreciation | Sft 105 | Sft | 105.00 | 123.90 | Assumption (your figure) |
| CV-030 | Fair-face formwork with film-faced plywood for exposed concrete | Sft 110 | Sft | 110.00 | 129.80 | Assumption (your figure) |
| CV-031 | Supplying and fixing welded wire mesh / reinforcement fabric including | Kg 285 | Kg | 285.00 | 336.30 | Assumption (your figure) |
| CV-032 | Supplying and installing mechanical rebar couplers including threading | No 900 | Nos | 900.00 | 1,062.00 | Assumption (your figure) |
| CV-033 | Drilling and chemically anchoring rebar dowels with injection epoxy | No 750 | Nos | 750.00 | 885.00 | Assumption (your figure) |
| CV-034 | Providing and laying 1st class brick masonry in ground-floor walls 9"  | Cft 350 | Cft | 369.88 | 436.46 | Built-up |
| CV-035 | Providing and laying 1st class brick masonry in foundation and plinth | Cft 340 | Cft | 359.59 | 424.32 | Built-up |
| CV-036 | Providing and laying 1st class brick masonry in walls | Cft 410 | Cft | 395.62 | 466.83 | Built-up |
| CV-037 | Providing and laying 1st class brick masonry in walls | Cft 370 | Cft | 375.60 | 443.21 | Built-up |
| CV-038 | Providing and laying 1st class brick masonry in parapet walls (separat | Cft 350 | Cft | 369.88 | 436.46 | Built-up |
| CV-039 | Providing and laying 1st class brick masonry in ledge / low walls (sep | Cft 360 | Cft | 369.88 | 436.46 | Built-up |
| CV-040 | Providing and laying AAC / lightweight block masonry in thin-bed adhes | Cft 520 | Cft | 520.00 | 613.60 | Assumption (your figure) |
| CV-041 | Providing and laying fly-ash brick masonry in cement sand mortar 1:6 | Cft 300 | Cft | 338.11 | 398.97 | Built-up |
| CV-042 | Providing and laying 2nd class brick masonry in cement sand mortar 1:6 | Cft 245 | Cft | 300.00 | 354.00 | Built-up |
| CV-043 | Providing and laying perforated (honeycomb) 1st class brick walling ha | Cft 270 | Sft | 149.52 | 176.43 | MRS 2026 composite |
| CV-044 | Providing and laying brick-on-edge work in cement sand mortar 1:6 over | Cft 290 | Sft | 186.54 | 220.12 | Built-up |
| CV-045 | Providing and laying random rubble stone masonry (uncoursed) in cement | Cft 650 | Cft | 351.33 | 414.57 | MRS 2026 composite |
| CV-046 | Cement pointing struck joints 1:3 on brick walls up to 20 ft height in | Sft 80 | Sft | 50.89 | 60.05 | MRS 2026 composite |
| CV-047 | Providing and laying damp proof course 1½" thick cement concrete 1:2:4 | Sft 145 | Sft | 136.29 | 160.83 | Built-up |
| CV-048 | Providing and applying two-coat cementitious waterproofing coating to  | Sft 95 | Sft | 69.89 | 82.47 | Built-up |
| CV-049 | Providing and applying liquid PU waterproofing membrane with primer an | Sft 140 | Sft | 140.00 | 165.20 | Assumption (your figure) |
| CV-050 | Basement tanking with bituminous membrane | Sft 280 | Sft | 280.00 | 330.40 | Assumption (your figure) |
| CV-051 | Mud phuska roof treatment: 4" earth | Sft 280 | Sft | 339.85 | 401.03 | MRS 2026 composite |
| CV-052 | Roof insulation with 1" thermopore sheet under a single layer of brick | Sft 240 | Sft | 197.52 | 233.07 | MRS 2026 composite |
| CV-053 | Providing and fixing PVC water stopper 8" wide in construction joints  | Rft 450 | Rft | 225.81 | 266.45 | Built-up |
| CV-054 | Filling expansion joints ½"–1" wide with backer rod and sealant | Rft 250 | Rft | 197.01 | 232.47 | Built-up |
| CV-055 | Providing and applying crystalline waterproofing slurry two coats to c | Sft 180 | Sft | 84.60 | 99.83 | Built-up |
| CV-056 | Crack / leakage injection grouting with PU or epoxy resin through port | Rft 1,200 | Rft | 1,200.00 | 1,416.00 | Assumption (your figure) |
| CV-057 | Cement sand plaster 1:4 | Sft 75 | Sft | 54.96 | 64.85 | Built-up |
| CV-058 | External cement sand plaster 1:5 | Sft 78 | Sft | 72.89 | 86.01 | Built-up |
| CV-059 | External cement sand plaster 1:6 | Sft 72 | Sft | 70.50 | 83.19 | Built-up |
| CV-060 | Cement sand plaster 1:4 | Rft 55 | Rft | 40.63 | 47.94 | Built-up |
| CV-061 | Providing and fixing MS diamond wire mesh 6" wide over RCC / masonry j | Rft 55 | Rft | 26.55 | 31.33 | MRS 2026 composite |
| CV-062 | Making grooves in plaster with ½"×½" aluminium trim | Rft 80 | Rft | 67.95 | 80.18 | MRS 2026 composite |
| CV-063 | Providing and applying textured silica-sand coating / colorcrete to ex | Sft 120 | Sft | 179.50 | 211.81 | MRS 2026 composite |
| CV-064 | Applying SBR bonding coat (SBR-cement slurry) on concrete before plast | Sft 55 | Sft | 26.74 | 31.56 | Built-up |
| CV-065 | Ready-mix gypsum plaster ½" thick | Sft 120 | Sft | 120.00 | 141.60 | Assumption (your figure) |
| CV-066 | Double scaffolding for external elevation work including erection | Sft 75 | Sft | 75.00 | 88.50 | Assumption (your figure) |
| CV-067 | Cement sand screed 1:4 | Sft 110 | Sft | 110.31 | 130.16 | Built-up |
| CV-068 | Cement sand screed 1:4 | Sft 170 | Sft | 186.59 | 220.17 | Built-up |
| CV-069 | Providing and laying foam concrete 3" thick on roof to falls | Sft 220 | Sft | 183.50 | 216.53 | MRS 2026 composite |
| CV-070 | Self-levelling underlayment ⅛"–3/16" with primer | Sft 250 | Sft | 250.00 | 295.00 | Assumption (your figure) |
| CV-071 | Providing and laying in-situ terrazzo / mosaic flooring 1½" thick with | Sft 500 | Sft | 312.42 | 368.66 | MRS 2026 composite |
| CV-072 | Providing and laying terrazzo tiles 12"×12"×1" grey | Sft 400 | Sft | 342.95 | 404.68 | MRS 2026 composite |
| CV-073 | Providing and laying chips / grit flooring 1½" thick (grey cement | Sft 380 | Sft | 315.82 | 372.67 | MRS 2026 composite |
| CV-074 | Providing and laying ¾" granite flooring on 1" cement sand bed 1:4 | Sft 750 | Sft | 926.81 | 1,093.64 | Built-up |
| CV-075 | Providing and laying ¾" marble to stair treads and risers on cement sa | Sft 700 | Sft | 493.38 | 582.19 | Built-up |
| CV-076 | Providing and fixing ¾" marble threshold / window sill 6" wide on ceme | Rft 450 | Rft | 244.29 | 288.27 | Built-up |
| CV-077 | Providing and laying non-skid chequered porcelain tiles 12"×12" to bat | Sft 240 | Sft | 276.80 | 326.62 | MRS 2026 composite |
| CV-078 | Providing and laying terracotta floor tiles on cement mortar | Sft 420 | Sft | 420.00 | 495.60 | Assumption (your figure) |
| CV-079 | Providing and laying full-body homogeneous / vitrified tiles 24"×24" o | Sft 400 | Sft | 450.65 | 531.77 | MRS 2026 composite |
| CV-080 | Epoxy floor coating | Sft 250 | Sft | 200.00 | 236.00 | Web installed rate |
| CV-081 | Supplying and installing SPC vinyl plank flooring with underlay and tr | Sft 300 | Sft | 483.25 | 570.24 | Web installed rate |
| CV-082 | Supplying and installing laminate wooden flooring 5/16" thick AC3 with | Sft 360 | Sft | 477.50 | 563.45 | Web installed rate |
| CV-083 | Providing and fixing 4" porcelain tile skirting on adhesive | Rft 150 | Rft | 139.57 | 164.69 | Built-up |
| CV-084 | Providing and fixing MS angle 1½"×1½"×¼" edge-protector nosing to stai | Rft 500 | Rft | 424.80 | 501.26 | MRS 2026 composite |
| CV-085 | Providing and fixing deodar wood chowkat 4½"×3" wrought | Rft 520 | Rft | 1,344.89 | 1,586.97 | MRS 2026 composite |
| CV-086 | Providing and fixing 1st class deodar wood panelled door 1¾" thick wit | Sft 2,500 | Sft | 2,998.95 | 3,538.76 | MRS 2026 composite |
| CV-087 | Supplying and fixing steel fire-rated door 60 min 3'-0"×7'-0" with fra | Sft 4,500 | Sft | 3,225.68 | 3,806.31 | Built-up |
| CV-088 | Providing and fixing MS single-leaf door of angle-iron frame and MS sh | Sft 1,300 | Sft | 1,083.75 | 1,278.83 | MRS 2026 composite |
| CV-089 | Supplying and installing uPVC sliding window with clear glass and hard | Sft 2,800 | Sft | 2,850.00 | 3,363.00 | Web installed rate |
| CV-090 | Providing and fixing premium uPVC door with uPVC chowkat and hardware | Sft 3,800 | Sft | 1,719.55 | 2,029.07 | MRS 2026 composite |
| CV-091 | Supplying and installing powder-coated aluminium sliding door with gla | Sft 3,000 | Sft | 1,400.00 | 1,652.00 | Web installed rate |
| CV-092 | Providing and fixing 24 SWG GI sheet rolling shutter with MS channel g | Sft 1,900 | Sft | 730.35 | 861.81 | MRS 2026 composite |
| CV-093 | Providing and fixing MS window grill of ⅜" square bars with frame | Kg 320 | Sft | 1,044.65 | 1,232.69 | MRS 2026 composite |
| CV-094 | Built-in wardrobe in MDF / laminate with hardware | Rft 5,500 | Rft | 5,500.00 | 6,490.00 | Assumption (your figure) |
| CV-095 | Kitchen cabinets base and wall units in MDF / laminate with hardware | Rft 6,500 | Rft | 6,500.00 | 7,670.00 | Assumption (your figure) |
| CV-096 | Bathroom vanity cabinet with top and basin cut-out | No 45,000 | Nos | 45,000.00 | 53,100.00 | Assumption (your figure) |
| CV-097 | Supplying and installing ½" toughened glass balustrade with fittings | Rft 4,500 | Rft | 6,000.00 | 7,080.00 | Web installed rate |
| CV-098 | Aluminium and glass curtain wall system with anchors and gaskets | Sft 4,500 | Sft | 4,500.00 | 5,310.00 | Assumption (your figure) |
| CV-099 | ACP external cladding on aluminium framing | Sft 750 | Sft | 750.00 | 885.00 | Assumption (your figure) |
| CV-100 | Supplying and installing framed toughened glass shower enclosure | No 40,000 | Nos | 36,500.00 | 43,070.00 | Web installed rate |
| CV-101 | Preparing surface and painting wood / steel with one priming coat and  | Sft 60 | Sft | 52.83 | 62.33 | Built-up |
| CV-102 | Preparing steel surface and applying one coat of red-oxide anti-rust p | Sft 35 | Sft | 14.77 | 17.43 | Built-up |
| CV-103 | PU lacquer / wood polish | Sft 120 | Sft | 120.00 | 141.60 | Assumption (your figure) |
| CV-104 | Distempering new surface two coats over chalk priming coat | Sft 30 | Sft | 15.30 | 18.06 | Built-up |
| CV-105 | Preparing surface and applying fine textured acrylic (Sandtex) coating | Sft 140 | Sft | 84.20 | 99.36 | MRS 2026 composite |
| CV-106 | Epoxy paint two coats to walls / steel including preparation | Sft 120 | Sft | 120.00 | 141.60 | Assumption (your figure) |
| CV-107 | White washing new surface three coats | Sft 18 | Sft | 9.72 | 11.46 | MRS 2026 composite |
| CV-108 | Bitumen coating two coats to plastered / concrete surfaces at 14 lb pe | Sft 55 | Sft | 19.67 | 23.21 | Built-up |
| CV-109 | Plain POP false ceiling with framing and basic cornice | Sft 180 | Sft | 150.00 | 177.00 | Web installed rate |
| CV-110 | PVC / WPC panel ceiling on support frame with trims | Sft 180 | Sft | 117.00 | 138.06 | Web installed rate |
| CV-111 | Vinyl-faced gypsum ceiling tiles 2'×2' on exposed grid | Sft 220 | Sft | 220.00 | 259.60 | Assumption (your figure) |
| CV-112 | Metal linear ceiling with carriers and suspension | Sft 450 | Sft | 450.00 | 531.00 | Assumption (your figure) |
| CV-113 | Gypsum board bulkhead on GI framing | Rft 500 | Rft | 500.00 | 590.00 | Assumption (your figure) |
| CV-114 | Providing and fixing stair railing of MS box section 1½"×3" 16 SWG wit | Rft 1,600 | Rft | 1,590.00 | 1,876.20 | MRS 2026 composite |
| CV-115 | Fabrication and erection of structural steel work in angles | Kg 360 | Kg | 353.33 | 416.92 | MRS 2026 composite |
| CV-116 | MS cat ladder of angle / flat / round bars | Rft 1,400 | Rft | 1,400.00 | 1,652.00 | Assumption (your figure) |
| CV-117 | Providing and fixing MS double-leaf main gate of angle-iron frame and  | Sft 1,800 | Sft | 1,480.80 | 1,747.34 | MRS 2026 composite |
| CV-118 | Boundary wall 9" brick with plaster both sides and paint | Sft 1,200 | Sft | 1,200.00 | 1,416.00 | Assumption (your figure) |
| CV-119 | Providing and fixing precast K-2 edge kerb stone embedded in PCC 1:2:4 | Rft 900 | Rft | 571.05 | 673.84 | MRS 2026 composite |
| CV-120 | Road sub-base of compacted gravel in 6" layers | Cft 180 | Cft | 166.43 | 196.39 | Built-up |
| CV-121 | Road base of graded crushed aggregate in 6" layers | Cft 230 | Cft | 258.01 | 304.45 | Built-up |
| CV-122 | Asphalt wearing course 2" compacted with tack coat | Sft 280 | Sft | 280.00 | 330.40 | Assumption (your figure) |
| CV-123 | RCC road slab 6" with mesh reinforcement | Sft 650 | Sft | 650.00 | 767.00 | Assumption (your figure) |
| CV-124 | Septic tank | No 250,000 | Nos | 250,000.00 | 295,000.00 | Assumption (your figure) |
| CV-125 | Soakage pit with honeycomb brick lining | No 180,000 | Nos | 180,000.00 | 212,400.00 | Assumption (your figure) |
| CV-126 | Providing and fitting 4" gully trap with PVC grating and masonry chamb | No 9,500 | Nos | 1,711.00 | 2,018.98 | MRS 2026 composite |
| CV-127 | Storm-water drain | Rft 1,800 | Rft | 1,800.00 | 2,124.00 | Assumption (your figure) |
| CV-128 | Grassing with fine Dhaka grass on 3" topsoil | Sft 160 | Sft | 41.16 | 48.56 | Built-up |
| CV-129 | Masonry / RCC planter with waterproofing and finish | No 15,000 | Nos | 15,000.00 | 17,700.00 | Assumption (your figure) |
| CV-130 | Providing and fixing ¾" sand stone cladding 12"×24" on walls over pre- | Sft 650 | Sft | 329.10 | 388.34 | MRS 2026 composite |
| CV-R01 | Crack treatment to plaster / concrete: chasing | Rft 180 | Rft | 180.00 | 212.40 | Assumption (your figure) |
| CV-R02 | Epoxy injection crack repair through injection ports | Rft 1,200 | Rft | 1,200.00 | 1,416.00 | Assumption (your figure) |
| CV-R03 | Hacking old plaster and re-plastering external walls with cement sand  | Sft 120 | Sft | 64.69 | 76.33 | Built-up |
| FN-560 (repaired) | Supply and fix wooden flush door shutter with frame, hardware and fini | — | Sft | 1,951.95 | 2,303.30 | Built-up |
| EW-950 (repaired) | Supply and lay concrete paver block on sand bed, including edge restra | — | Sft | 234.54 | 276.76 | Built-up |
| EW-960 (repaired) | Construct brick masonry manhole with RCC cover, plastered internally | — | Nos | 47,097.50 | 55,575.05 | Built-up |

## Quotations needed first

The assumption lines with the most money behind them: shoring (CV-011), curtain wall (CV-098), septic tank
(CV-124), soakage pit (CV-125), kitchen cabinets and wardrobes (CV-094, CV-095), vanity (CV-096), storm-water
drain (CV-127), injection grouting and epoxy repair (CV-056, CV-R02), AAC blocks (CV-040), topsoil (CV-128), and
gypsum board with GI sections (FN-550, QS-GYP-P01, CV-113).

## Rebuild

```sh
tools/civil_gap_data.py --as-of 2026-09-26          # rewrite the #raCivilData block
python3 -m unittest tools/test_civil_gap_data.py    # data rules (sources, units, MRS match, worked examples)
python3 -m http.server 8765 &                       # then, with playwright installed:
node tools/test_civil_gap.js                        # fresh and saved-library merge, no page errors
```
