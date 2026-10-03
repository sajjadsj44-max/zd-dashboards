# zd-dashboards

Static, self-contained HTML dashboards published live on Netlify and GitHub Pages.

## Live links

| Page | Netlify (short link to share) | GitHub Pages |
|---|---|---|
| Zameen Developments | https://zd-dashboard.netlify.app/ | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |
| Drawing Tracker | https://zd-dashboard.netlify.app/drawing-tracker/ | https://sajjadsj44-max.github.io/zd-dashboards/drawing-tracker/ |
| PDF Takeoff | https://zd-dashboard.netlify.app/takeoff/ | https://sajjadsj44-max.github.io/zd-dashboards/takeoff/ |
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

**Purchase orders (Phoenix).** The Sage 300 report *P/O Purchase Order List
(POPODET1)*, printed to PDF, links each Phoenix receipt to its PO: the register,
History and both CSVs show the PO number and PO date beside the GRN. A PO
received in one GRN that the register does not hold yet is added from the PO
list at its unit cost, **dated by the PO date** (the report has no GRN date) and
marked <kbd>PO date</kbd> on screen, in the CSVs (*Date is*) and in the
**+ Rate DB** remarks. The next receiving export that holds the same GRN line
replaces the PO date with the GRN date. Loaded on 03-Oct-2026 from
`POPODET1-20261002-180044.pdf` (362 POs): 789 Phoenix receipts carry their PO
and 19 receipts were added for GRNs RCP-3, RCP-4 and RCP-318 to RCP-328, so the
register runs to 28-Sep-2026.

```sh
pip install pdfplumber                       # once
tools/po_register.py POPODET1.pdf            # --site Phoenix by default
```

The report's dates are read by column position (Posted On, Purchase Order Date,
Arrival Date), because long vendor names overprint the Posted On date in the
PDF text. A PO received in several GRNs whose last GRN is missing is listed,
not added, since the report does not split its quantity by GRN.

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

## QS Rate Analysis Engine (Rate Analysis)

Added 26-Sep-2026. The brief it was built against, including what was changed in the original
prompt and why, is in [`docs/qs-rate-engine-brief.md`](docs/qs-rate-engine-brief.md).

- **19 QS categories** (Civil Works … Miscellaneous and Specialized Works), each with its own
  sub-categories. Every item is classified by rule, and the category and sub-category can be
  overridden per item. A Category / Sub-category filter above the item search controls the item
  dropdown and the search results. The same filters are on the Item Library, the Register, the
  Audit view and the Rate Database ("used in category"). Opening an item from another category
  switches the filter to that item's category.
- **Material-based builders** replace lump "materials" with purchase-unit resources. Each row
  carries *formula = working = result*, and every parameter can be edited:
  gypsum ceiling (board ÷ sheet area, main and furring channels by spacing, perimeter angle, hanger
  rod, anchors, connectors, screws, tape, compound), drywall partition, tiles (grout from joint
  geometry, adhesive from the TDS, or a mortar bed), paint coat by coat, pipe with counted
  fittings and clamps, PVC conduit, cable tray with supports, LT cable with glands and lugs,
  screed and formwork. Builder rows carry their own wastage, so item wastage B is 0.
- **Confidence** is derived, never typed: *Verified*, *Reference-Based*, *Assumed* or *Review
  Required* (unpriced, composite / installed rate used as a material, source older than the
  staleness limit (default 12 months, set in Settings), or a high-severity audit finding). An
  item takes the worst level among its components, and the reasons are listed on the item.
- **Tax (I)** is added after overheads and profit: `I = tax % × (direct + G + H)`. The default
  is in Settings and it can be overridden per item. The bases of G, H and I are printed.
- **Revisions**: *Save revision* snapshots an item (15 kept). Compare any two revisions, or a
  revision against the current build-up. Every Rate Database edit is logged with its old and new
  values and the analyses it re-priced (300 entries kept). Items record who updated them and when.
- **QS Register & Reports**: filter by category, sub-category, confidence, location and update
  date. Exports: register to Excel and CSV; a detailed workbook with one sheet per analysis and
  live Excel formulas (`Amount = Qty × Rate`, sub-totals, G / H / I); printable PDF sheets; a
  material and labour breakdown.
- **Audit & Quotations**: the corrections applied (with rate before and after), the rate lines
  that need a supplier quotation, and every audit finding. Items are flagged, never deleted.

Seed corrections are applied only to items and lines still exactly as seeded. An item already
edited by hand is left alone and listed, with a button to apply the builder, which saves a
revision first. Applied on the first load after this change:

| Item | Error found | Correction |
|---|---|---|
| SC-420 screed 1" 1:4 | cement 0.0217 was the cement *volume* in cft, not bags (÷ 1.25 omitted); sand 0.1083 was the whole dry volume, not the 4/5 share — both +25 % | screed builder: 0.01733 bag, 0.08667 cft (+5 % wastage) |
| FN-500 / FN-505 tiles | grout 0.08 kg/Sft ≈ 10 × the joint volume for 24" tiles, 1/16" joints | tile builder |
| FN-550 gypsum ceiling | `GYPBD` 200/Sft was an installed rate entered as a material | gypsum builder (11 resources) |
| FN-530 / 535 / 540 paint | `PUTTY`, `PRIMER`, `EMUL`, `WSHIELD` were per-Sft systems | paint builder, priced per Ltr / Kg |
| PL-700 / PL-710 pipes, EL-600 conduit, EL-650 tray | pipe / tray + a percentage for fittings | counted fittings, clamps and supports from Quadrangle GRNs |
| EL-670 LT cable | glands and lugs not priced | allocated per run |
| FW-300 … 350 formwork | amortised per-Sft ply / timber lines | sheet price, uses and batten volume explicit |
| NAILS | 400/kg assumption | Phoenix GRN RCP-273, 21-May-2026 — 715/kg |

Flagged, not changed: FN-510 marble bed thickness is not stated (the quantities imply 7/8");
FN-560 door has no frame; EW-950 paving has no paver; EW-960 manhole has no materials; EX-130
compaction factor; EL-615 has one switch per light point; MEP items add house OH / profit on top of
MAK rates that already include MAK's margin.

**Rates.** The new purchase-unit lines come from the GRN Price Register (same `GRN-…` codes as
its *+ Rate DB* button, so lines the MEP analyses already use are shared), from dated published
pages (Reference-Based), or are left at **0** as `ASSUMPTION — no dated source`. From the build
environment, supplier and price-list sites (United Gypsum, Nippon, Brighto, OLX, icons.com.pk …)
were blocked by the network egress policy, and search results gave only installed ceiling rates.
The gypsum board, channels, angle, connectors, tape, compound, studs and tracks are therefore
**unpriced**, and the gypsum items show *incomplete* until a quotation is entered. The prompt's
PKR 500 / sheet board is used only as the test figure (500 ÷ 32 × 1.05 = 16.406 / Sft).

Data: the `<script type="application/json" id="raQsEngine">` block, written by
`tools/qs_engine_data.py` (reads the GRN block of the same page). Tests:

```sh
tools/qs_engine_data.py --as-of YYYY-MM-DD          # rebuild the data block
python3 -m unittest tools/test_qs_engine_data.py     # data rules (source format, GRN match, guards)
python3 -m http.server 8765 &                        # then, with playwright installed:
node tools/test_qs_engine.js                         # 48 browser checks (QE_LIBS=… for offline Excel)
```

## Civil gap rate analyses (Rate Analysis)

Added 26-Sep-2026 from Sajjad's list of missing civil analyses
(`QS_Rate_Analysis_Lahore_2026_All_Missing.txt`), reviewed line by line. The review, including every
rate side by side with the list, is in [`docs/civil-gap-rate-review.md`](docs/civil-gap-rate-review.md).

- **133 new Item Library items**: `CV-001` … `CV-130` (site preparation, earthwork, concrete, formwork,
  reinforcement, masonry, waterproofing, plaster, screed, flooring, doors / windows / joinery, painting,
  ceilings, metal work, external works) and `CV-R01` … `CV-R03` (repair). Each carries its QS category.
- **Built as full A–H analyses** wherever inputs exist (53 items). Materials use the library's own lines
  or the GRN register. Labour uses the Punjab MRS 1st Bi-Annual 2026 labour-only rate for the same
  operation, with the same `MRS-C…` codes as the MRS register's *+ Rate DB* button.
  - 30 items use an **MRS 2026 composite rate**.
  - 9 use a **dated web installed rate**.
  - 41 keep the list's figure as a `BM-CV-<n>` line marked **`ASSUMPTION — no dated source`**, so they
    show as Assumed until a quotation replaces them.
- **Seed items repaired:** FN-560 gains its galvanised steel door frame (Quadrangle GRN). EW-950 gains
  the paver block. EW-960 gains the materials of a 3 × 3 ft × 5 ft brick manhole. The gypsum items
  (FN-550, QS-GYP-P01) stay incomplete, because no dated board or GI-section price was found.
- **Shared lines moved:**
  - `L-HELPER` 1,300 → 1,538 per day (Punjab minimum wage 40,000 per month from 01-Jul-2025 ÷ 26 days).
    This raises almost every civil item.
  - From the Part 1 research (Claude chat, 26-Sep-2026): `BRK-1` 18 → 17.5, `BRK-2` 15 → 13,
    `GRAVEL-SB` 120 → 100, and seven trade wages that were assumptions (plaster mason, carpenter, steel
    fixer, tile fixer, electrician, plumber, foreman).
  - The Punjab "September" MRS on Drive is the Layyah district edition, so the Rawalpindi edition stays as
    the MRS basis until the Lahore 2nd Bi-Annual 2026 file is loaded.

Saved libraries pick the block up on their next load, the same way as the MEP block (`raSyncBlk`,
revision key `civRev`):

- missing lines and items are added;
- a line or seed item still at its published version (`prevRates` / `prevItems`) is moved to the new one;
- anything edited by hand is left alone.

Data: the `<script type="application/json" id="raCivilData">` block, written by `tools/civil_gap_data.py`
(it reads the GRN and MRS blocks of the same page).

```sh
tools/civil_gap_data.py --as-of 2026-09-26          # rebuild the data block
python3 -m unittest tools/test_civil_gap_data.py    # data rules: sources, units, MRS match, worked examples
python3 -m http.server 8765 &                       # then, with playwright installed:
node tools/test_civil_gap.js                        # 18 browser checks: fresh and saved-library merge
```

## Master Rate Analysis Rev07 (Rate Analysis)

Added 27-Sep-2026 from `RA_Master_Pakistan_FINAL_Rev06_2026-09-27.xlsx` (125 analyses). The updated workbook is
[`docs/RA_Master_Pakistan_FINAL_Rev07_2026-09-27.xlsx`](docs/RA_Master_Pakistan_FINAL_Rev07_2026-09-27.xlsx) and the
full revision / validation report is [`docs/master-rate-analysis-rev07.md`](docs/master-rate-analysis-rev07.md).

- **160 Item Library items under the workbook codes** (`CIV-CON-001` … `MISC-SGN-001`): the 125 workbook analyses
  plus 35 new ones (floor-level extras from Punjab MRS, HDPE pipe, landing valve, signage, and vendor items for
  gaps in both libraries — mobilization, site office, testing, FR / metal ceilings, carpet, wallpaper, GRC, EIFS,
  canopy, skylight, urinal, CPVC, access control, fire stopping, escalator, irrigation, VRF, MDB). Each carries the
  same description, unit, resource rows and 8% OH / 10% profit as the workbook; row quantities are the workbook's
  adjusted quantities (consumption × (1 + wastage)). Sheet 18 of the workbook reconciles all 160 against the page.
- **One rate per shared resource**: 36 workbook resources use the dashboard's own Rate Database line (CEM, SAND-*,
  CRSH-*, STL60, BLK-*, BRK-1, RMC-*, L-* …). Workbook inputs moved to the dated dashboard rate for 11 of them;
  the dashboard moved `QE-TIMB-CFT` to the workbook's Phoenix GRN (3,680/cft).
- **Crew productivity** (workbook sheet 13) checked against Punjab MRS 2026 labour shares, MAK installation rates
  (÷ 1.18) and ConcretesMath Lahore piece rates; kept within ±35%, otherwise reset. 27 outputs corrected; 8 with no
  dated benchmark stay marked as assumptions.
- **Dashboard corrections**: ST-200/205/210 rebar labour (36.80 → 11.08 per kg); brick generator labour now scales
  with wall thickness; plaster generator labour by thickness (MRS); saved libraries are migrated on their next
  load unless the item was edited by hand.

- **Rev07a assumptions (27-Sep-2026, on request)**: every rate that was still blank — 53 workbook inputs (gypsum
  board and channels, MDF, ACP, props / mixer hire, release oil, lift, escalator, VRF, MDB, vendor items …) and 110
  dashboard lines (97 MEP components of the MAK build, gypsum / drywall components, topsoil) — now carries an
  assumed value whose remarks start with `ASSUMPTION — no dated source` and state the basis. Nothing in either file is
  left unpriced; replace each with a quotation (workbook 16 RFQ col H, or the Rate Database). The full list is in the
  report.

- **Rev07b remark dates (01-Oct-2026)**: every dated Rate Database line now reads `<source>, DD-Mon-YYYY — <details>`
  with its Effective date as the only date before the dash. 62 price-list lines are dated by the list's effective
  date instead of the day it was read (27-Sep-2026); GRN lines cite the receipt (`Quadrangle GRN RCP-n, date — …`);
  MRS edition periods and other dated brackets moved behind the dash; four seed lines reworded. No rate changed.
  Details in the report's Rev07b section.

Data: the `<script type="application/json" id="raMasterData">` block, merged by `raSyncBlk` (key `masRev`) and
`raSyncMaster`. To rebuild after entering quotations in the workbook's 16 RFQ sheet:

```sh
python3 -m http.server 8765 &                                   # repo root; needs LibreOffice Calc + playwright
tools/ra_master_build.sh RA_Master_Pakistan_FINAL_Rev06_2026-09-27.xlsx docs/
python3 -m unittest tools/test_ra_master_data.py
```

## RFQ Tracker (Rate Analysis)

Added 01-Oct-2026. QS Cost Control → **RFQ Tracker** turns the lines that need a dated quotation into
enquiries, and the quotes received into Rate Database rates with their source and date.

- **Needs a quotation**: every Rate Database line used in an analysis that has no rate, is an assumption,
  or is dated more than the staleness limit ago (Settings, default 12 months). Most-used first, with the QS
  category it is mainly used in and any open RFQ it is already on. Tick lines → **Create RFQ**.
- **RFQ**: items (Rate Database unit, optional qty and spec), reply-by date, delivery and terms; vendors
  invited, with the date each enquiry went out. Vendors who supplied similar items before are suggested
  from the GRN Price Register. **Print enquiry** makes one letter per vendor; **Copy enquiry text** gives the
  same as plain text to paste into WhatsApp or an email; **Enquiry Excel** for vendors who fill a sheet.
  Nothing is sent from the page.
- **Quotes**: vendor, quotation reference, date (not in the future), validity, terms and the rate per item.
- **Comparative statement**: lowest per item in green; the lowest is awarded unless another is picked, which
  needs a reason. **Apply** writes each awarded rate to its Rate Database line after a confirmation listing
  old → new: rate, the quotation date as Effective date, status Verified, and the source
  `<Vendor> quotation <ref>, DD-Mon-YYYY — RFQ-2026-001 <title>: lowest of 3 quotes (range); <terms>; valid to …
  Applied <date> by <name>` (CLAUDE.md form). Every change goes to the rate change log with the analyses it
  re-priced; **Revert** puts a line back while nobody has edited it since.
- Status per RFQ: Draft → Sent → Quotes in → Awarded (or Closed / Cancelled); **Overdue** when the reply date
  passes with no quote. Open and overdue RFQs also show on the Executive Dashboard.

Records are kept in the rate library (`RA.rfq`, browser storage `SAJ_QSCOST_v1`) and travel with Backup JSON,
like the Lab Rate Analysis records. The code is the `<!--zd:rfq-->` block of `zameen-developments/index.html`.

```sh
python3 -m http.server 8765 &
node tools/test_rfq_tracker.js        # 38 browser checks (QE_LIBS=… for the offline Excel check)
```

## Price Trends (Rate Analysis)

Added 01-Oct-2026. QS Cost Control → **Price Trends**, read-only, three tabs:

- **Price trend**: every GRN receipt of a material over time, Quadrangle and Phoenix in their own colours,
  the monthly median, and the Rate Database line it should agree with. Groups: OPC cement (per bag), Grade 60
  steel (per Kg; receipts per Ton ÷ 1,000), Sargodha crush, Chenab / Lawrencepur / local sand, ready-mix
  4000 / 4500 / 6000 psi, solid and hollow blocks — or any single GRN item. Receipts are in the house unit the
  GRN Price Register uses; items in another unit are left out and listed, and every unit reading is stated
  (e.g. GRN "Each" read as one bag). Tiles: latest receipt, change over 12 months (monthly medians a year
  apart), the Rate Database rate against the latest receipt, receipts and vendors. Site and period filters,
  table view and CSV.
- **Rate DB vs latest GRN**: every line that is a GRN line, or whose remark names a GRN receipt as its own
  source (before the dash) or as a `Last / Replaces … GRN RCP-n` cross-check, against the latest receipt of
  the same item. A receipt has to match the line by rate or by name; assumptions and composites that only
  mention a receipt are not linked; receipts in another unit are listed as not comparable. Flags: off by more
  than the tolerance (default ±10%) and newer GRN available. Ticked lines go straight to a new RFQ.
- **Staleness map**: Rate Database lines by kind of source (assumption, RFQ quotation, GRN, price list, MRS,
  MAK bill, other quotation, web) × age of the source date (≤ 3, 3–6, 6–12, 12–24, > 24 months, none);
  click a cell for its lines, tick them into an RFQ.

The code is the `<!--zd:pt-->` block of `zameen-developments/index.html`; charts use Chart.js from the CDN
(the receipts table is shown when it cannot load).

```sh
node tools/test_price_trends.js       # 29 browser checks, worked against the page's own GRN block
```

## PDF Takeoff (`takeoff/`)

Added 01-Oct-2026 (Phase 1). Measure quantities straight off PDF drawings, in the browser — linked from the
dashboard sidebar (QS Cost Control → PDF Takeoff) and the landing page.

- **Private by design**: a PDF opens in the viewer's browser and is stored with the takeoff in that browser's
  IndexedDB — nothing is uploaded and nothing is committed here. Projects move between computers as
  **Export → Project (.json)**; the PDF is re-attached by adding it again (matched by file name and size).
- **Scale**: read from the drawing's scale note — `1/8" = 1'-0"`, `3/16"=1'-0"`, `1" = 20'`, `1:100` — including
  `@ A1`-style paper sizes when the PDF page is printed smaller or larger than the drawing (the A3 copy of an
  A1 sheet is corrected by 1190.55 / 2383.94). A scale from a note shows as **not verified** until a known
  dimension is measured against it (scale chip → Verify, ±1%); **Calibrate** (`K`) sets it from two points and a
  length typed in feet or ft-in. Pages with no note must be calibrated; measurements on such pages stay out of
  the totals until they are.
- **Snapping** to the drawing's own vector lines — endpoints, intersections, midpoints, nearest point on a line
  (curves flattened) — plus points already measured. Vector PDFs exported from CAD snap; scanned PDFs can be
  measured but have no lines to snap to. `Shift` keeps a run at 0° / 90°.
- **Conditions** (what is measured) with presets per the house standards: floor area (Sft), RCC slab (cft, T),
  ceiling plaster, formwork soffit (5.00 Sft threshold), 9" and 13.5" brick walls (cft, H, T), 4.5" partition
  (Sft, thickness stated), internal plaster both faces / external plaster (Sft, H), skirting (ft), doors and
  windows (Nos). Heights and thicknesses are never assumed: a wall in Sft or cft cannot be created without H,
  a cft quantity without T.
- **Tools**: draw (`A` — polygon / run / count per the condition), rectangle (`R`), deduction (`D` — void in an
  area, length in a run), opening (`O` — door / window width measured on the plan, height typed), measure
  (`M`, not saved), select and drag points (`V`), undo / redo, Nos multiplier per measurement.
- **Measurement sheet** in the house format: every row `Nos × L × W × H` in decimal feet (3 dp), Sft / cft
  / ft (3 dp), Nos (whole); a quantity is the product of the dimensions as printed, so the sheet re-measures from its
  own figures. Rectangles are one row `L × W`; any other outline is one row with its plan area by coordinates;
  a run lists its legs (`12.000 + 14.000 + …`). Deductions are their
  own negative rows; openings / voids at or under the condition's threshold (masonry and plaster 1.00 Sft,
  formwork 5.00 Sft, concrete 0.50 cft) are listed but not deducted, saying why. Internal plaster carries both
  faces in Nos.
- **Exports**: Excel in the house colours (blue measured inputs, unlocked; green formulas `=PRODUCT(D:G)`,
  `=-PRODUCT(…)` for deductions, a run's length as `=12.000+14.000+…`; grey `SUM` totals; sheet protected) with
  Summary, Scale & audit (how each page's scale was set and checked) and Assumptions (unverified scales,
  heights / thicknesses and opening heights to confirm); CSV; the marked-up page as PNG; the project as JSON.

**QS controls** (added 01-Oct-2026):

- **Lossless project file, version 2.** Import keeps every property of the file (viewports, markups, auto-area
  settings, layers, sheet info, opening schedule, and any key it does not know) and upgrades version-1 files in
  place. After an import a **Project Import Validation** table compares the file and the imported project (PDFs,
  conditions, measurements, scales, viewports, markups …, measurements pointing to a missing condition or PDF,
  PDFs still to re-attach) with PASS / WARNING / FAIL.
- **Scale status** per page — ✓ Verified / ✓ Calibrated / ⚠ From note / ⚠ Inherited / ✕ Unknown — on the scale chip
  and the page list. **Copy scale to…** replaces "use on every page": tick pages (quick picks: this PDF, same
  paper size, same scale note); copies are *inherited, not verified*, and a page that already has a scale asks first.
- **Typical floors**: copies are previewed first. *Same place* checks each target sheet by its own text (share of
  words at the same position) and warns before copying onto a different layout; *Align by two reference points*
  takes two points on the source and the same two on each target (move, turn, rescale), shows the copies dashed
  and copies on **Copy here**. Every copy is marked *Copied — not checked*.
- **Skirting less doors**: assembly variables `PD` (perimeter less the door openings on the outline) and `D`
  (door widths). Doors are openings whose schedule type is door, labelled `D…`, or 6 ft or taller, within 1.25 ft
  of the room outline (either wall face); a typed value on the measurement overrides.
- **Location**: Sheet info (ⓘ Sheet: sheet no., title, revision, discipline, building, floor) per page;
  measurements take the sheet's building and floor unless given their own, plus zone / apartment and room. The
  bill groups by building / floor; Excel has a *By location* sheet.
- **QA** per measurement: Measured / Checked (by whom, when) / Recheck required, with AI-generated and copied
  flags; a QA bar over the sheet (checked, pending, recheck, AI / copied to check, missing rate, unverified scale)
  filters the sheet, and **✓ Check this page** signs off a page. Moving a checked outline resets it.
- **Check before export**: missing or unverified scale, missing H / T, opening height, negative or zero quantity,
  BOQ code, rate (or rate without a dated source), formula errors, unchecked AI / copied / recheck measurements,
  no floor — shown as PASS / WARNING / ERROR in Export and on the Excel *Validation* sheet.
- **BOQ / WBS code and Rate Analysis code** on each condition and assembly line. An RA code takes the item's
  built-up rate from the Rate Analysis library kept in the same browser (SAJ QSCOST, `SAJ_QSCOST_v1`), worked out
  exactly as Rate Analysis does (materials + wastage + labour + plant + access + transport, + OH, + profit); the
  source reads `ZD Rate Analysis <code>, DD-Mon-YYYY — built-up rate …` and counts assumed rows. A code not in the
  library, priced in another unit, or with unrated rows gives **RATE NOT AVAILABLE** — never a guess. Open the
  dashboard and the takeoff on the same host (Netlify or GitHub Pages) — browser storage is per host.
- **Opening schedule**: marks (D1, W2 …) with type, width and height, entered once; the Opening tool picks a
  mark (its size wins over the clicked width) or adds a new one, and can keep placing the same mark. Changing a
  size updates every opening with that mark.
- **Revision quantity compare** (Bill → Revision compare): old sheets against new sheets (picked from Sheet info),
  per condition and assembly line — old, new, variance, %, cost impact where the line has a rate — and a
  **Change Management CSV** with the log's columns (Log ID left blank to assign) plus item, BOQ code, old / new
  qty, variance and rate.
- **Backups**: the last 10 copies of each project in this browser — on opening, every 10 minutes while working,
  on demand, and before a restore. Restore (Projects → Backups, or Export → Backups…) always asks first.

**Bluebeam / PlanSwift editing** (added 02-Oct-2026 — compared against Bluebeam Revu 21 / Bluebeam Max and PlanSwift 11
v11.0.0.191 with Takeoff Boost; the full table is `docs/takeoff-bluebeam-planswift-parity.md`):

- **Selecting**: click; a box dragged **left → right selects what is wholly inside** (blue), **right → left what it
  touches** (green); **Lasso** (`Shift+O`); Shift / Ctrl+click add or take out; **Tab** steps through objects lying on
  top of each other; hover highlights the object and shows its quantity; a multiple selection shows its totals.
- **Moving and copying**: drag a selected object to move it (the grabbed point snaps to the drawing; `Shift` straight;
  `Alt`+drag moves without selecting first); **Ctrl+drag copies**; arrow keys nudge. `Ctrl+C` / `Ctrl+X` / `Ctrl+V`
  work on a whole selection (measurements and markups), on any page, pasted at the **same real size** if the page's
  scale differs; **`Ctrl+Shift+V` pastes in place** (typical floors); `Ctrl+D` duplicates; **`Ctrl` + arrow copies at a
  distance or as an array** (ft across / down, PlanSwift style); *Place copies by clicking*; *Copy to other pages*;
  rotate 90° / flip; bring to front / send to back; **lock** (`Ctrl+Shift+L`: not moved, edited or deleted).
- **Undo while drawing**: `Ctrl+Z` / `Backspace` take back the last click (an arc as one step) and **`Ctrl+Y` puts it
  back**; `Ctrl+Z` or `Esc` during a drag cancels it; the undo / redo buttons name the change ("Undo: Move 3 objects"),
  200 steps.
- **Drawing**: `A` while drawing makes the next segment an **arc** (a point on it, then its end — one leg on the sheet);
  **type a length and Enter** to place the next point at that distance (`12'-6"`, `12.5`; a rectangle takes `12 x 14`);
  `Ctrl`+click places a point with no snap.
- **Editing points**: **double-click a side to add a point, double-click a point to remove it** (or `Shift`+click, as in
  Bluebeam); drag the **+** at the middle of a side to pull out a new point; a selected point goes with `Delete`.
- **Lines**: **Break** (`B`) cuts a run in two where clicked, `Shift`+click with Break deletes one segment; *Cut a gap*
  removes the part between two clicks (a door across a skirting); **Join** makes selected runs one; *Continue drawing*
  carries a run on from its nearer end; *Explode* gives one run per segment; *Close* the run; **Offset** a run sideways
  or an outline in / out (defaults to half the condition's thickness); an area's outline becomes a **perimeter run**
  in a length condition, a run of 3+ points an area.
- **Right-click menu** on a measurement, a selection, a markup or the empty drawing, with all of the above plus
  properties, rename (`F2`), cut-out / opening, move to condition, select all of the condition, condition (edit,
  colour, hide, show only), QA (checked / recheck), zoom to and delete. A right-drag still pans; on a tablet, press and
  hold. `?` lists every shortcut; `Z` is a zoom window.
- **Doors / windows agent** (🚪 in the Claude panel, or *count doors on all pages* in its chat): every door, window and
  ventilator tag however it is written — `D1`, `D-1`, `D.01`, `DR-02`, `DOOR 3`, `SD` / `FD` / `FRD` / `MD` / `GD` / `AD` /
  `DD` / `RS`, `W1`, `WN-2`, `WIN 3`, `WINDOW 4`, `KW` / `TW` / `BW` / `CW` / `SW` / `FW` / `AW` / `SKY`, `V1`, `VT`, `VENT 1`,
  `LV`, `DW`, primed `W1'`, suffixed `W1A` (`D-01` and `D1` are one mark) — including tags written in two pieces (a letter
  over a number in a circle). Marks inside the door / window schedule table are not counted; the table's sizes (ft-in,
  inches, decimal ft, or mm converted to ft) and quantities are read, a schedule quantity that differs from the count
  is flagged, and the sizes can go straight into the opening schedule. On this page, every page of the PDF or the whole
  project; you tick what to count (one condition per mark, or per type); markers are flagged AI until checked.
  *count door swings* counts doors from their swing symbols (arcs of 1.2–6 ft; double doors once) on drawings with no
  tags.

**QA pass** (02-Oct-2026 — full audit, bug hunt and regression test; the report with the bug register,
calculation table and live-retest checklist is `docs/takeoff-qa-report-2026-10-02.md`):

- **Pages tab** beside Sheet / Conditions: a thumbnail of every page of every PDF (drawn as it scrolls into view) with
  its scale status and number of measurements; **remove a PDF** from the project (a backup is taken first, its
  measurements go with it).
- **View menu** (header): fit page (`F`), **fit width** (`Shift+F`), dim the drawing, line weights on / off, PDF layers, hide
  markups, labels; `Home` / `End` go to the first / last page. The header wraps on narrow screens instead of
  pushing buttons off the edge.
- **Chosen scale** for a sheet with no note: architectural (1/32" … 3" = 1'-0"), engineering (1" = 10' … 100') or
  metric ratio (1:20 … 1:1000), with the paper size it was drawn for (ISO A0–A4, ARCH C–E, ANSI C–E) so a reduced
  print is corrected; shown as *Chosen by hand — not verified* until a known dimension is checked.
- **Scale check by room sizes**: on opening a sheet, the room sizes written on it (`12'-0" x 14'-0"`) are measured
  across the room and a scale note that disagrees is flagged with the scale they suggest.
- **Password-protected PDFs** ask for the open password (kept with the PDF in this browser); the marked-up PDF export
  flattens locked and rotated pages.
- **Auto area** now closes corridors and passages as narrow as the door gap (trying smaller gaps when the click is
  off-centre), rooms drawn at an angle, round rooms, rooms with hatched / tiled walls, L-shaped rooms and scanned
  sheets; door swings, furniture and hatching no longer close or leak a room. A self-crossing outline is flagged on
  the sheet and by *Check before export*.
- **Walls agent** runs across corridors and splits walls at + junctions (no double count where walls cross).
- **Saving**: `Ctrl+S` saves now; closing or hiding the tab saves at once; a second tab with the same project shows
  a warning with *Reload this one*. A damaged project file is repaired on import (bad points, colours, conditions)
  and the repairs are listed as *Repaired* rows in the import validation.
- **Quantities to 3 dp** everywhere (sheet, CSV, Excel `#,##0.000`), Nos whole; undo keeps 200 steps (fewer on very
  large projects, never under 20).

**Free agents** (03-Oct-2026 — in the Claude panel; no API key, no cost, nothing leaves the browser; they read the
PDF's own lines and text, so vector drawings — a scanned sheet has neither):

- **⚡ Full takeoff**: rooms, walls, doors / windows and finishes in one run, on this page, every page of the PDF or
  the whole project, with one report (page by page, the run's totals, counts against the schedule's quantities, the
  pages skipped and why). *Rooms* — auto area at every room name not yet measured, checked against its written size.
  *Walls* — every **standard** thickness drawn (4", 4.5", 5", 6", 8", 9", 10", 12", 13.5", 18") on the centre line, into
  your existing wall condition of that thickness when there is one; other spacings of parallel lines (window glass, a
  counter) are listed, never measured. *Doors / windows* — every tag counted, a schedule table's sizes into the opening
  schedule. A page with no scale, or a scale its written room sizes disagree with, is skipped — nothing is measured at
  a doubtful scale. Running it again leaves measured rooms as they are and replaces its own walls, counts and finishes,
  so nothing is doubled; **one Ctrl+Z takes the whole run back**.
- **🎨 Finishes**: for each room measured on the page, its **wall finish** (plaster / paint) as one run round the room,
  Nos × L × H at the room height given, with **every door and window its own deduction row** (house threshold:
  1.00 Sft or less not deducted); its **skirting** less its doors; its **ceiling** as an assembly line (= A) of the room
  condition, for the Bill. Doors are found from their swings (hinge to jamb; a double door once), sized from the opening
  schedule when a door tag is beside them, else drawn width × the door height given; a door tag with no swing drawn (an
  entrance) is placed by its tag. Windows are found from their tags and sized from the opening schedule only — a
  window's height is never on a plan, so one with no size is listed as *not deducted*, never assumed. A room finishes
  table (floor, ceiling, perimeter, doors, windows, skirting, gross, deductions, net) copies to Excel.
- **✅ Check**: audits the takeoff the way a checking QS would — rooms written on the drawing but not measured (with
  *Measure them*), the same room measured twice (two outlines of one condition overlapping), a count marker on top of
  another, door / window tags not counted or counted differently (with *Count them*), measured against written room
  sizes (over 5 %), counts against the schedule's quantities, the drawing's schedule sizes against the opening
  schedule (a revised size), walls with length only, and unchecked agent work; each finding has **Show** (goes to the
  page and selects it) or a fix. The export check's notes (BOQ codes, rates, floors) are folded underneath.
- **Chat without a key**: *how many D1*, *how many doors*, *total floor area*, *total bedroom area* are answered from what
  is measured; commands can be chained (*measure all rooms, then count doors and walls 9"*); *measure all rooms on every
  page* runs the rooms over the whole PDF; a typing slip (*bedrom*, *kitchn*) still finds the room. The 🏠 Rooms agent
  no longer measures a room twice — one already measured in the condition is left as it is.

Phase 2 / 3 status: click-inside room areas, walls by thickness, symbol / tag counting, room sizes and door /
window marks read from the drawing, the revision overlay and scanned-PDF measuring are in. Still planned: a command
bar, typical-floor multipliers, sending quantities to the Project BOQ, OCR of scanned sheets, and page reorder /
rotate inside a PDF.

`takeoff/index.html` (layout) and `takeoff/takeoff.js` (the app) load pdf.js 4.10.38 and ExcelJS from the jsDelivr
CDN. Tests use a hand-written 3-page vector PDF with known dimensions (`tools/takeoff_fixture.js`):

```sh
python3 -m http.server 8765 &
TK_LIBS=/path/with/pdfjs-dist+exceljs node tools/test_takeoff.js      # 150 browser checks
TK_LIBS=/path/with/pdfjs-dist+exceljs+pdf-lib node tools/test_takeoff_qa.js   # full QA audit: 460 checks in 24 sections
```

The QA audit (`tools/test_takeoff_qa.js`, fixtures in `tools/takeoff_qa_fixture.js`) builds an 8-page drawing set
(a house at 1/4" = 1'-0" with known room areas, a rotated page, an offset page box, a blank page, a 1:50 metric
sheet, a sheet with a detail at another scale, angled / round / hatched rooms, an A4 page with no note), a 120-page
PDF, a 200 dpi scanned sheet and a 150,000-line CAD sheet, and checks every quantity against the hand-worked
figure. `TK_REPORT=file.json` writes every check, calculation and timing to a file.

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
- **Gauge thickness:** wherever gauge is meaningful — sheet / plate (MS, GI, stainless,
  aluminium), pipe and hollow-section walls, pipe volume / weight, C / Z purlins, cable tray,
  HVAC duct and the any-shape steel calculator — the thickness unit dropdown offers **Gauge**
  next to mm / inch. Pick the gauge (10–30, or manual entry) and a **gauge standard**:
  GI / galvanized (GSG), MS / uncoated steel (Manufacturers' Standard Gauge), stainless
  (U.S. Standard Gauge 1893), aluminium / non-ferrous (Brown & Sharpe = AWG), SWG (BS 3737)
  or BWG (tube wall). Sheets default to the standard for the selected material; tubes
  default to SWG. The equivalent thickness (mm and inch) is shown under the field, in a
  *Conversion* block and as the first working step, and is used in the calculation.
  Switching Gauge ↔ mm ↔ inch converts the value. **Gauge Reference Table** (Calculator →
  Gauge Reference) lists every standard with mm, inch and kg/m², finds the nearest gauge for
  a thickness, and names each source. The tables live in the `gauges` part of the
  `calcData` block (built by `tools/calc_data.py`): MSG and GSG from the published charts,
  stainless from the weight schedule of 15 U.S.C. §206 (oz ÷ 640 in), SWG, BWG and B&S from
  the `fluids` package.
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
takeoff/index.html, takeoff.js      PDF Takeoff (pdf.js viewer, scale, snapping, measurement sheet)
tools/grn_register.py               merge GRN receiving exports into the GRN Price Register
tools/po_register.py                link GRN receipts to Sage POs (POPODET1 PDF); add GRNs dated by PO date
tools/test_po_register.py           tests for the PO list loader
tools/mrs_register.py               load a Punjab MRS PDF into the Punjab MRS Rates register
tools/test_mrs_register.py          tests for the MRS loader
tools/mep_rates.py                  build the MEP rate analyses from the MAK final bill + GRN register
tools/test_mep_rates.py             tests for the MEP rate analyses
tools/lab_mix_data.py               lab concrete mix designs for the Lab Rate Analysis tab
tools/test_lab_mix_data.py          tests for the lab mix-design transcription
tools/kpk_mrs.py                    load the KPK MRS PDF into the KPK MRS Rates tab
tools/rate_watch.py                 daily check for new KPK / Punjab (Lahore) rate schedules
tools/qs_engine_data.py             build the QS Rate Analysis Engine data block (categories, rate lines, corrections)
tools/test_qs_engine_data.py        tests for the engine data block
tools/test_qs_engine.js             browser tests for the engine (playwright)
docs/qs-rate-engine-brief.md        revised brief for the QS Rate Analysis Engine
tools/civil_gap_data.py             build the civil gap-analysis data block (CV items, rate lines, seed repairs)
tools/test_civil_gap_data.py        tests for the civil gap data block
tools/test_civil_gap.js             browser tests for the civil gap merge (playwright)
docs/civil-gap-rate-review.md       review of the missing-items rate list, with every rate side by side
tools/ra_master_config.py           decisions for the Master Rate Analysis Rev07 (shared lines, rates, productivity, new items)
tools/ra_master_excel.py            update the Master Rate Analysis workbook (Rev06 -> Rev07) and add sheets 17-19
tools/ra_master_data.py             build the dashboard block #raMasterData from the Rev07 workbook
tools/ra_master_build.sh            run the whole Rev07 build (workbook, recalculation, block, reconciliation, tests)
tools/test_ra_master_data.py        tests for the block and the workbook
tools/test_ra_master.js             browser tests for the Master Rate Analysis merge (playwright)
docs/master-rate-analysis-rev07.md  revision and validation report of the Master Rate Analysis Rev07
docs/RA_Master_Pakistan_FINAL_Rev07_2026-09-27.xlsx  the Rev07 workbook
tools/test_rfq_tracker.js           browser tests for the RFQ Tracker (playwright)
tools/test_price_trends.js          browser tests for Price Trends & Staleness (playwright)
docs/takeoff-bluebeam-planswift-parity.md  PDF Takeoff vs Bluebeam Revu 21 / Max and PlanSwift 11 (Takeoff Boost), feature by feature
tools/takeoff_fixture.js            hand-written 3-page vector test PDF for the takeoff tests
tools/takeoff_qa_fixture.js         QA drawing set: 8-page house / odd-page PDF, 120-page PDF, scanned sheet, 150,000-line sheet
tools/test_takeoff_qa.js            full QA audit of the PDF Takeoff (sections 1-23, playwright)
docs/takeoff-qa-report-2026-10-02.md  QA audit report: bug register, calculation checks, performance, retest checklist
tools/test_takeoff.js               browser tests for the PDF Takeoff (playwright)
tools/calc_data.py                  build the Calculator tab's section / pipe / material data block
.github/workflows/rate-watch.yml    runs the rate watch daily and offers updates as a pull request
.github/workflows/deploy-pages.yml  deploy to Pages + mirror main onto gh-pages
.nojekyll                           serve files as-is (no Jekyll processing)
```
