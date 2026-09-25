# zd-dashboards

Static, self-contained HTML dashboards published live on Netlify and GitHub Pages.

## Live links

| Page | Netlify (short link to share) | GitHub Pages |
|---|---|---|
| Zameen Developments | https://zd-dashboard.netlify.app/ | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |
| Drawing Tracker | https://zd-dashboard.netlify.app/drawing-tracker/ | https://sajjadsj44-max.github.io/zd-dashboards/drawing-tracker/ |
| Dashboard index | https://zd-dashboard.netlify.app/index.html | https://sajjadsj44-max.github.io/zd-dashboards/ |

On Netlify the site root serves the dashboard itself (see the rewrite in
`netlify.toml`); on GitHub Pages the root serves the index page instead.

Both hosts serve the same repo and update from the same push, so either link
works. Share the Netlify one — it is shorter and easier to read out.

Public and read-only — anyone with the URL opens them in any browser, phone or
desktop, with no login and nothing to install. Viewers cannot edit anything.

Because the repo is public, everything committed here is publicly readable.
Don't commit confidential data.

## Updating a dashboard (the "live" part)

1. Replace the dashboard file, e.g. `zameen-developments/index.html`.
2. Commit and push to `main`.
3. ~1–2 minutes later the same URL serves the new version to everybody.

The URL never changes, so links already shared stay valid across every update.
If someone still sees an old copy, GitHub Pages caches HTML for up to 10
minutes — a hard refresh (Ctrl + F5, or Cmd + Shift + R) clears it immediately.

## Data sources

The Change Management app reads **two Google Sheets** over the gviz JSONP
endpoint, both of which must be shared as *Anyone with the link · Viewer* or the
dashboard cannot read them:

| What | Sheet | Read as |
|---|---|---|
| RFI / design change log | `Change Management-Cost Impact` | first tab, `gid=0` |
| Per-project cost, area, rate and dates | `Projects Summary` | first tab, then by tab name |

`SHEET_ID` and `PD_SHEET_ID` hold the two workbook ids. `SHEET3_CANDIDATES`
is tried in order: the `Projects Summary` workbook first, then a
`Sheet 3` / `Project Details` / `Projects` / `Project Data` / `Master` tab
inside the log workbook, so a project summary kept as a tab in the log
workbook still works with no code change.

The project summary needs these eight columns. Headers are matched by regex,
not by position, so the wording can vary — `Covered Area (Sft)` and
`Area, Sft` both resolve:

```
Project Name | Original Contract Cost (PKR) | Covered Area (Sft) |
Original Rate / Sft (PKR) | Contract Date | Contract Duration (Days) |
Expected Completion | Remarks
```

Rate is derived as cost ÷ area when the rate cell is blank. Project names are
matched to the log through the built-in `PROJECTS` registry, so `NEO` in the
log and `Zameen NEO` in the summary resolve to the same project.

The Drawing Tracker (`drawing-tracker/index.html`) reads one Google Sheet,
**`ZD Drawing Register (Tracking)`** (`SHEET_ID` in that file), first tab via
`gid=0`, also over the gviz JSONP endpoint — so it too needs to stay shared as
*Anyone with the link · Viewer*. Columns: `Project | Discipline | Drawing /
Revision | Status | Date Received | Category / Source Folder | Remarks /
Source | Drive Folder Link`. It was seeded on 23-Sep-2026 from the drawings
actually found in the shared "New ZD Drive" (ARX, DTR, EON, GRANDE PALLADIUM -
IVORY, GVR Multan, HIVE, JADE, MALL-35, NEO, PHOENIX, QUADRANGLE): rows with a
real drawing name and date were logged as `Received`; every project/discipline
combination without a logged drawing yet is seeded as `Pending Entry` with a
link straight to its Drive folder. The Document Controller / QS team keeps it
current by editing the sheet directly — add a row per drawing as it's
received, or change a `Pending Entry` row's status to `In Progress` /
`Waiting` / `Received`; the dashboard just reflects the sheet live, it never
invents a status.

## GRN Price Register (Rate Analysis)

QS Cost Control → **GRN Price Register** lists every item received on site with
the rate of its latest GRN, the vendor, the number of receipts and the low–high
range, plus the full receipt history per item. Seeded on 23-Sep-2026 from the ERP
material receiving exports of **Quadrangle** (3,138 receipts, Mar-2021 to
Aug-2025) and **Phoenix** (770 receipts, Nov-2022 to 07-Sep-2026): 1,775 items in
total. Rates billed per cubic metre, metre or square metre are converted to Cft,
Rft and Sft; the GRN unit and rate stay in the history. **+ Rate DB** copies an
item's latest GRN rate into the Rate Database as a verified line, with
`<Site> GRN RCP-n, DD-Mon-YYYY — <vendor>` in its remarks and the same date as
its effective date.

The data is embedded in `zameen-developments/index.html` (the
`<script type="application/json" id="raGrnData">` block). To add another site or
a newer export, run:

```sh
pip install openpyxl                      # once
tools/grn_register.py NEW_RECEIVING.xlsx  # one or more exports
```

Receipts already in the register are skipped, so a cumulative export can be
re-run safely. The raw exports are not committed.

## KPK MRS Rates (Rate Analysis)

QS Cost Control → **KPK MRS Rates** lists all 4,584 items of the Khyber
Pakhtunkhwa Finance Department (MRS Cell) **Market Rate System MRS-2025 (1st
Bi-Annual)**, notified 07-Oct-2025 (No.MRS/FD/4-2/NOTIFICATION/2025), Peshawar
base rates. Items are kept separate by their 28 chapters (item types: carriage,
earthwork, concrete, brick masonry … electrical, photovoltaic, repair &
maintenance). Each item has its British and metric unit, labour and composite
rate exactly as printed, the specification reference, the MRS remarks and the
PDF page number. Units default to British (Cft / Sft / Rft); the metric column
is available as printed. A district or merged-area location factor (from the
schedule's own factor tables) can be applied to every rate shown. The filtered
CSV carries `KPK MRS-2025 (1st Bi-Annual), 07-Oct-2025 — item <code> …` in its
Source / remarks column and 2025-10-07 as its effective date.

Composite rates include 23.5% (4% KP sales tax, 2% overheads, 7.5% income tax,
10% contractor's profit). They are KPK government schedule rates, not Lahore
market rates — a benchmark, not a substitute for a dated Lahore quote or GRN.

The data is embedded in `zameen-developments/index.html` (the
`<script type="application/json" id="raKpkData">` block). To load a newer
bi-annual edition:

```sh
pip install pymupdf                       # once
tools/kpk_mrs.py "KPK Market Rate System 2026 (1st Bi Annual).pdf" \
    --edition "MRS-2026 (1st Bi-Annual)" --notified YYYY-MM-DD \
    --notification "No.MRS/FD/..."
```

The PDF is not committed.

### Daily rate watch

`.github/workflows/rate-watch.yml` runs `tools/rate_watch.py` every day at 06:30
Pakistan time (and on demand from the Actions tab):

- **KPK** — reads the KPK Finance Department's Market Rate System page. When an
  edition newer than the one in the tab is listed, it downloads the PDF, parses it
  and checks it (3,000+ items, 20+ chapters, 97%+ British/metric agreement). The
  notification date comes from the notification; if that is a scan, the PDF's issue
  date is used and the tab shows a "confirm" warning.
- **Punjab (Lahore)** — reads the Punjab Finance Department market-rate and
  input-rate pages and records every Lahore PDF. These are listed on the tab; their
  rates are not parsed yet.

Anything new is committed to the `rate-watch/update` branch and offered as a
**pull request** — the live dashboard changes only when you merge it (check the
deploy preview first). A new KPK edition that fails the checks opens an issue with
the link instead and is retried daily. A run marked failed in the Actions tab means
the KPK site could not be reached or read that day. The Punjab site does not
answer GitHub's servers (first dry run, 24-Sep-2026: all three pages timed out), so
a Punjab timeout is only a warning on the run; the KPK site answered normally. State is kept in `data/rate-watch.json`.

For the bot to open pull requests, enable *Settings → Actions → General → Allow
GitHub Actions to create and approve pull requests* (otherwise it opens an issue
pointing at the branch).

## Punjab MRS Rates (Rate Analysis)

QS Cost Control → **Punjab MRS Rates** is a read-only register of the Punjab
Finance Department's **Market Rates System (MRS)**, next to the GRN Price
Register. Loaded on 23-Sep-2026 from the **1st Bi-Annual 2026, District
Rawalpindi** edition (valid 01-Jan-2026 to 30-Jun-2026; `Punjab rates
385_20260110213957.pdf` from Google Drive): **1,539 rate lines** from the
building-construction chapters — Loading/Unloading, Earthwork, Dismantling,
Concrete, Brickwork, Stone Masonry, Roofing, Flooring, Surface Rendering, Wood
Work, Painting & Varnishing, Plumbing/Sanitary/Gas, Iron Work and Miscellaneous.

Each line shows the MRS labour and composite (labour + material) rate in house
units — per 100 Sft, per 1000 Cft, per Cwt (→ Kg) and so on are converted — with
the figure and unit as printed and its chapter, item, line and page, so it can
be checked against the PDF. Search, filter by chapter, unit or metric check, and
export CSV. **+ Rate DB** copies one line (composite or labour share) into the
Rate Database as a market-indication (`I`) rate — a published schedule, not a PO
or GRN — with location, effective date and the MRS reference in its remarks
(`Punjab MRS 1st Bi-Annual 2026 (Rawalpindi), 01-Jan-2026 — Ch.6 item 9, line
19 (Concrete), p.39; ...`). The register itself never changes the Rate Database
or any analysis until a line is added that way.

**Checked against the PDF.** MRS prints every rate twice on the same row, in
British and metric units. The loader converts one to the other for every line:
**1,453** lines agree, **26** are lines where the schedule's own two figures
disagree (e.g. p.65 Multani tiles, 1,261.55 per Sft beside 4,137.80 per Sqm) —
those carry a ⚠ check mark with the metric figure, and that note travels into
the remarks if one is added to the Rate Database — and 60 use units that have
no metric counterpart (Job, Point, Letter ...). Every figure was also found on
its cited page by a second PDF reader.

The edition's period has lapsed, so the tab says so: treat these as a benchmark
and prefer a current, dated Lahore rate for a live BOQ (see `CLAUDE.md`). To
load a newer edition or another district — edition, district, period and
chapter pages are read from the PDF itself:

```sh
pip install pdfplumber                       # once
tools/mrs_register.py MRS.pdf                # building chapters (default)
tools/mrs_register.py MRS.pdf --chapters all # or e.g. 2-13,19,24,25,26
python3 -m unittest tools/test_mrs_register.py          # parser tests
MRS_PDF=MRS.pdf python3 -m unittest tools/test_mrs_register.py   # + end-to-end
```

Left out by default: Ch.1 Carriage — its mile and km bands are printed over each
other in the PDF and cannot be read back reliably — Ch.5 Mortar (a material
consumption table, no rates), and the non-building chapters (canals, sheet
piling, roads, drainage, sewerage, wells, tubewells, electrical, HVAC; HVAC's
table layout is different and reads as 0 lines even with `--chapters all`). The
data lives in the `<script type="application/json" id="raMrsData">` block of
`zameen-developments/index.html`.

## Concrete design mixes (Rate Analysis)

Rate Analysis → Item Library now carries **24 generated design-mix RCC items**
(per Cft), built from two lab mix-design sheets received 23-Sep-2026:

- **Al Rafiq Ready Mix — Summary of concrete mix design** (20 rows, 1000–9000 psi;
  cement + fly ash, silica fume from 8000 psi, SP 224/150 or SP 534/40):
  `RCC-DM-AR-<psi>`; the second 6500 and 7000 psi rows (10mm-heavy, SP 534/40)
  are `RCC-DM-AR-6500B` / `-7000B`.
- **Concrete Mix Design ACI-211** lab sheet (1500, 4000, 4500, 6000 psi):
  `RCC-DM-ACI-<psi>`.

Batch weights per m³ are held in `RA_DMIX` and converted per Cft (÷ 35.3147):
cement ÷ 50 kg/bag; fly ash, silica and admixture in Kg; sand and crush in Cft
from the Al Rafiq sheet's own CFT columns (46.65 kg/cft sand, 41.00 kg/cft
crush — the same densities are used for the ACI sheet, flagged as an assumption);
water as an optional allowance. Labour and plant follow nominal-mix RCC. Sand and
crush sources can be changed on the item's parameter panel.

Two rate lines were added: `ADMIX-SP` (FosPak SP 568, 185/kg, Quadrangle GRN
RCP-1847, 24-Jul-2024 — latest GRN, no current Lahore rate found) and `FLYASH`
at 1.758/kg, **ASSUMPTION — no dated source**: the top of a Pakistan range of
Rs 2–1,758 per metric ton from a 23-Sep-2026 web-search summary (no seller, no
date). It is probably low, since fly-ash bricks sell at Rs 13–18 each. Replace it
with a dated quotation before pricing a live BOQ.

## Concrete Mix Design – Lab Rate Analysis (Rate Analysis)

Rate Analysis → **Concrete Mix Design – Lab Rate Analysis** keeps every laboratory mix design as its
own record, priced from the Rate Database. Seeded on 25-Sep-2026 from **15 photos → 21 records**
(photo 8 is a duplicate of photo 7):

| Source (as on the photos) | Records | Grades |
|---|---|---|
| Excel ACI-211.1 workbook, lab not shown (photos 1–6) | `LMX-XL-01`…`06` | psi not shown (cement 150–530 kg/m³) |
| J7 Group QA/QC, Batching Plant Multi Garden B-17 (photos 7–8) | `LMX-J7-<psi>` | 3000, 4000, 4500, 5000, 5500 |
| ACI-211.1 5000 psi sheet, mixed 05-04-26, lab not shown (photo 9) | `LMX-ACI5K-01` | 5000 |
| Ready-mix plant sheets, DHA Multan, BS 882 grading (photos 10–14) | `LMX-MUL-<psi>`, `LMX-MUL-136` | 1000, 4000, 4500, 6000, 1:3:6 |
| "Concrete Mix Design ACI-211" batch-weight sheet (photo 15) | `LMX-ACI-<psi>` | 1500, 4000, 4500, 6000 |

Designs of the same psi from different labs stay separate. Figures are typed as printed (the
Excel sheets' corrected weights are used; the uncorrected weights, volumes and slumps are kept in
each record's notes). Anything a sheet does not show (lab name, psi, date, cut-off mix codes,
unnamed admixtures, sand / crush sources) is listed under **Needs Verification** on the record.

Each record: lab kg/m³ → bags, Cft (sand 46.65 / crush 41.00 kg/cft, the Al Rafiq sheet
densities the Item Library design mixes use; editable per record), litres; linked Rate Database
line, qty in its unit, rate, amount per m³ and per Cft, and totals for a chosen volume in Cft.
Clicking a rate updates the shared Rate Database line (source and date required). Labour,
machinery, batching, mixing, transport, pumping, wastage, overheads and profit are separate
editable components at 0 until entered. Records can be added, edited, duplicated, archived and
deleted (deleted seed records are not re-added; *Restore* brings them back); print / PDF, Excel
and CSV per record, plus a register CSV. Records are stored in the rate library (`RA.labMix`,
browser storage key `SAJ_QSCOST_v1`) and travel with Backup JSON.

The seed is the `<script type="application/json" id="raLabMixData">` block. To change a
transcription, edit `tools/lab_mix_data.py`, then:

```sh
tools/lab_mix_data.py zameen-developments/index.html
python3 -m unittest tools/test_lab_mix_data.py
```

A new seed revision refreshes only records nobody has edited.

## MEP rate analyses (Rate Analysis)

Rate Analysis → Item Library carries **423 MEP items** (Electrical 129, HVAC 130,
Plumbing 73, ELV 47, Fire Fighting 44), built on 24-Sep-2026 from the **MAK
Contractors & Associates final bill for Mall-35 MEP** (`MAK Final Bill Checking.xlsx`,
Final IPC-09, May-2025: electrical, plumbing, HVAC and all Non-BOQ additional scopes).

MAK worked on an installation-only contract (MEP Works Agreement, 25-Sep-2023: material
and equipment by the Employer; rates include 7.5% income tax and exclude PRA). So each
item is built up as:

- **A. Material:** the latest GRN from the GRN Price Register (same `GRN-…` codes its
  **+ Rate DB** button uses), or an existing Rate Database line (`SAN-WC`, `SAN-WB`).
  Pipe fittings and tray accessories are a share of the pipe / tray value, taken from the
  Quadrangle receipts: PPRC 1.054, uPVC 0.980, MS 0.483, tray (without covers) 0.224.
  Insulation sheet and GI sheet are converted to per Sft. Each conversion is written in
  the line's remarks.
- **Wire and small cable (refreshed 24-Sep-2026):** single-core wire and earth cable
  1.5–70 mm², 2C 1.5 mm² speaker cable and RG-6 / RG-11 use the **Pakistan Cables suggested
  retail price list, 03-Jun-2026** (90 metre coil, registered price including 18% GST,
  ÷ 295.276 ft), cross-checked against the **Fast Cables retail price list, 10-Jan-2026**
  (within about 5%). Both PDFs are in Google Drive. A **30% trade discount** (supplied by
  Sajjad, 24-Sep-2026; `TRADE_DISC` in `tools/mep_rates.py`) is taken off the list price,
  giving for example 1C 25 mm² 378.52/Rft net (list 540.75; last GRN 227.10 on Quadrangle
  RCP-2297, 25-Jan-2025). Each line's remarks give the list price, the discount, the Fast
  cross-check and the last GRN, and the line is marked `I` (market indication). Neither
  list covers 600/1000 V power cable, GI sheet, insulation or pipe, so those stay on GRN.
- **B. Wastage:** cables 3%, pipes / conduit / duct / insulation 5%, fixtures 0%.
- **C. Labour:** `MAK-<item>` = the MAK rate for that item, read from the bill rows.
  BOQ rates are dated 25-Sep-2023 (the contract). Non-BOQ rates are dated 31-May-2025,
  because the certificate gives only the month.
- **G / H:** house overhead 8% and profit 10%. MAK's rate already includes MAK's own
  margin. Set both to 0 to get Zameen's direct cost.

Per-point wiring quantities (for example 45 ft of run from the DB to a switch board, or 60
ft of Cat-6 per data point) are assumptions stated in the line notes, because the bill's
measurement sheets count points but do not give lengths. Materials with no GRN (97
lines, for example PICVs, patch panels, speakers and 8"–12" MS pipe) are kept at 0 and
marked `ASSUMPTION — no dated source`. The item then shows an unpriced gap. **133 of the
138 priced materials come from GRNs more than 12 months old** (Quadrangle 2022–2025),
and their remarks say "reconfirm before use". Employer-supplied equipment (panels,
chillers, AHUs, FCUs, pumps, fans) is installation only. Where one exists, the note gives
the Quadrangle GRN supply price for reference.

Every item's spec names the bill item and row it came from. Its note gives the Mall-35
contract and final-bill quantities. Where several bill rows share one rate, they are
grouped into one item (all DBs at 14,550; all FCU sizes at 2,659.38). Non-BOQ rows that
repeat a BOQ rate rounded to 2 dp were left out of those groups.

The data is in the `<script type="application/json" id="raMepData">` block. Saved
libraries get the new lines and items on their next load (missing codes only; nothing
already in the library is changed, except that a line or item still at a previously
published version is moved to the new one — the block keeps those versions in `prevRates` /
`prevItems`, and anything edited by hand is left alone). To rebuild from a newer bill or GRN register:

```sh
pip install openpyxl
tools/mep_rates.py "MAK Final Bill Checking.xlsx"
MAK_BILL="MAK Final Bill Checking.xlsx" python3 -m unittest tools/test_mep_rates.py
```

The build stops if any rows grouped into one item carry different rates. The bill
workbook is not committed.

## Calculator tab

Sidebar → **Calculator** (after Admin) is a QS / civil / structural / MEP calculator
module, added 25-Sep-2026. Every calculation shows **Input → Formula → Working
(substituted values) → Result → Unit**, multi-unit results (kg / ton / lb, kg/m / kg/ft,
SFT / m², CFT / m³, litres / gallons) and a source panel naming the standard, whether the
value is a **published table value** or **calculated**, and the density used
(**Standard density** or **User-defined density** — never changed silently).

- **Steel:** rebar (d²/162, exact, BS 4449 table, ASTM A615 bar No. / sutar; weight ↔
  length), plate / sheet, flat, round, square / rectangular / hex bar, MS / GI pipe, SHS /
  RHS / CHS (sharp, EN 10210 or EN 10219 corner radii), any standard section, welded plate
  girder, angle, channel, I / H, tee, C / Z purlin, and a general any-shape calculator.
- **Section database:** 3,652 sections and pipes in 70 series — IS 808:1989 (MB/ISMB,
  LB, JB, WB, HB, SC, NPB, WPB, PBP, MC/ISMC, MPC, LC, JC, ISA equal / unequal), IS 4923
  SHS / RHS, IS 1161 CHS, BS 4-1 UB / UC, EN IPE / HEA / HEB / HEM, UPN, UPE, IPN, HD, HP,
  EN 10056 angles, EN 10210 SHS / RHS / CHS, AISC v16 W / S / M / HP / C / MC / L / WT /
  HSS / Pipe, ASME B36.10M / B36.19M schedules, EN 10255 (BS 1387) medium / heavy,
  BS 1387 light, ASTM D1785 PVC. Search → select → shape, dimensions, kg/m, kg/ft,
  properties, source.
- **Civil & finishes:** concrete (PCC / RCC with deductions, nominal mix, steel kg/m³),
  material mix, excavation (side slopes, prismoidal), brickwork, blockwork, stone
  masonry, plaster, screed, formwork, tile / marble, paint / putty, waterproofing,
  skirting, boards, grout / adhesive, sealant. Dimensions are shown as
  `Nos × L × W × H` strings and openings as separate negative rows.
- **MEP:** pipe volume / weight (any material, schedules), tank volume (incl. part-filled
  horizontal cylinder), flow ↔ velocity, length takeoff, insulation, electrical load
  (1φ / 3φ), Ohm's law, cable conductor weight, voltage-drop estimate (IEC 60228 DC
  resistance), AWG ↔ mm², cable tray, HVAC duct area / weight / air volume.
- **Item-wise calculators (BOQ items):** 81 ready-made items in 12 trades (earthwork,
  grey-structure concrete, masonry, reinforcement, plaster & mortar, flooring, painting,
  waterproofing, ceiling, plumbing, electrical, HVAC) — e.g. PCC 1:4:8 lean, DPC 1½",
  RCC slab / beam / column / footing / lintel, 9" brickwork 1:6, 6" blockwork, brick
  soling, internal / external / ceiling plaster, 600×600 tiles, emulsion system, rebar
  by sutar, binding wire. Each is a preset of a calculator above; every value stays editable.
- **More grey-structure / finishes tools:** material weight CFT ↔ kg (RCC, PCC, brick
  masonry, mortar, cement, sand, steel …), filling / backfilling (compaction allowance,
  truck trips), bar bending schedule (weight per diameter), steel from concrete volume
  (kg/CFT, kg/m³, %), binding wire (ties in slab mesh or beams / columns × wire length per
  tie × SWG weight, or kg per ton), brick soling / on-edge, staircase concrete,
  false-ceiling grid, pipe slope / fall, **coat-wise painting system** (primer, putty and
  paint coats each with their own TDS coverage), **tile bond (tile adhesive)** — kg and bags
  from the bag / TDS consumption, bed thickness or notched-trowel size, with back-buttering —
  and a coverage-material tool (SBR bond coat,
  sealer, epoxy, anti-termite, curing compound).
- **Libraries:** two-way unit converter (NIST SP 811 exact factors, incl. RFT / SFT / CFT,
  Marla / Kanal both conventions, brass, maund), conversion library, formula library,
  constants / unit weights (materials with status and source; BS 4449, ASTM A615,
  IEC 60228, gauge and AWG tables), density settings, and **custom calculations** (your
  own named formula, inputs, units and optional density).
- Search answers directly: `10 cft to m3`, `5 marla in sft` (both conventions),
  `100 cft rcc to kg`, `500 kg cement in cft`. It knows site terms (sariya, eent, chunai,
  bajri, ret, khudai, bharai, rang, taar, masala …) and tolerates typos.
- Search box (in the tab and in the dashboard-wide search) understands `20mm rebar`,
  `#5`, `ISMB 300`, `MS pipe 4 inch`, `10mm plate`, `25x25 angle`, `RHS 100x50x5`,
  `W12x26`, `brickwork`, `paint`, `cable`. Favourites (★), recent calculations (reopen /
  copy / delete / clear), copy, print / PDF, CSV and Excel export. Favourites, history,
  last inputs, density overrides and custom calculators live in the viewer's browser only.

**Data rules.** Nothing standardised is typed into the UI code. Section and pipe tables
come from `tools/calc_data.py`, which reads published machine-readable sources
(eurocodepy, AISC Shapes Database v16 via steelpy, Osdag's IS 808 database, fluids'
ASME tables, structuralcodes EN dimensions) and writes the
`<script type="application/json" id="calcData">` block. Where only dimensions are
published (UPN, UPE, IPN, HD, HP, EN angles) the mass is computed from the exact profile
(fillets, toe radii, taper) at 7850 kg/m³ and labelled *calculated* — checked against
catalogue values (UPN 100 13.47 vs 13.5 cm², IPN 300 69.00 vs 69.0 cm²). Values that
could not be verified are not invented: plastic pipe densities, paint coverage, grout
density, membrane consumption, putty / primer / paint coverage per coat, binding-wire
length per tie, soil / aggregate density and overall cable weight must be entered from the product
data sheet, and the calculator refuses to calculate until they are. QS conventions (dry-
volume factors 1.54 / 1.27, joint thickness, wastage) are editable and badged
*convention*. To rebuild the data:

```sh
pip install eurocodepy steelpy structuralcodes fluids shapely numpy
git clone --depth 1 https://github.com/osdag-admin/Osdag.git /tmp/osdag
tools/calc_data.py --osdag /tmp/osdag zameen-developments/index.html
```

## Netlify

Netlify is connected to this repo and redeploys on every push to `main`, in
parallel with GitHub Pages. `netlify.toml` holds the whole configuration:
publish the repo root, no build command, and revalidate HTML on every request
so an updated dashboard reaches viewers on their next load.

To connect it (once): Netlify → `Add new site` → `Import an existing project` →
`GitHub` → pick `sajjadsj44-max/zd-dashboards` → branch `main` → `Deploy`.
Leave build command and publish directory blank; `netlify.toml` supplies them.
Then `Site configuration` → `Change site name` → `ZD-Dashboard`
(Netlify lowercases it into the URL, giving `zd-dashboard.netlify.app`).

## How publishing is wired

Pages `Source` is set to **GitHub Actions**, so
`.github/workflows/deploy-pages.yml` does the publishing on every push to `main`:

- **`deploy`** packages the repo and deploys it to Pages.
- **`mirror`** force-pushes `main` onto a `gh-pages` branch, so switching
  `Source` to *Deploy from a branch* (`main` or `gh-pages`, `/ (root)`) would
  also serve the current site without editing the workflow.

Note for future changes: do not add `actions/configure-pages` with
`enablement: true`. The workflow `GITHUB_TOKEN` cannot create a Pages site
(`Resource not accessible by integration`) and it is not needed — the site
already exists.

## Publishing a new dashboard version

The published file is a hardened build, not the authoring copy. Regenerate it
rather than committing a new export directly:

```sh
npm install terser clean-css-cli          # once
tools/harden.py NEW_VERSION.html zameen-developments/index.html
```

`tools/harden.py` states authorship in the markup, metadata, sidebar and at
runtime, then minifies the stylesheet and scripts. Pass `--no-minify` to inject
the ownership markers while keeping sources readable.

A published single-file dashboard can always be saved by anyone who can view it;
that is how the web works and no setting changes it. The build exists to make an
unattributed copy awkward to produce and easy to disprove, not to prevent
copying.

The authoring copy is kept outside this repo (see `.gitignore`) so a clean,
readable version is not published beside the hardened one.

## Adding a new dashboard

Create `<dashboard-name>/index.html`, then add a card for it in the root
`index.html`. Keep the filename `index.html` so the short folder URL works.

Each dashboard is one self-contained HTML file. External libraries (Chart.js,
PapaParse) load from the jsDelivr CDN at runtime, so viewers need an internet
connection.

## Repo layout

```
index.html                          landing page listing all dashboards
netlify.toml                        Netlify publish settings and cache headers
zameen-developments/index.html      Zameen Developments dashboard
drawing-tracker/index.html          Drawing Tracker dashboard
tools/grn_register.py               merge GRN receiving exports into the GRN Price Register
tools/mrs_register.py               load a Punjab MRS PDF into the Punjab MRS Rates register
tools/test_mrs_register.py          tests for the MRS loader
tools/mep_rates.py                  build the MEP rate analyses from the MAK final bill + GRN register
tools/test_mep_rates.py             tests for the MEP rate analyses
tools/lab_mix_data.py               lab concrete mix designs for the Lab Rate Analysis tab
tools/test_lab_mix_data.py          tests for the lab mix-design transcription
tools/kpk_mrs.py                    load the KPK MRS PDF into the KPK MRS Rates tab
tools/rate_watch.py                 daily check for new KPK / Punjab (Lahore) rate schedules
tools/calc_data.py                  build the Calculator tab's section / pipe / material data block
.github/workflows/rate-watch.yml    runs the rate watch daily and offers updates as a pull request
.github/workflows/deploy-pages.yml  deploy to Pages + mirror main onto gh-pages
.nojekyll                           serve files as-is (no Jekyll processing)
```
