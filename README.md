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
(0, **ASSUMPTION — no dated source**). Until a dated fly-ash rate is entered the
Al Rafiq items show one unrated row each and their rates are understated.

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
  Wire bought by the coil is converted at a 90 metre coil; insulation sheet and GI sheet
  are converted to per Sft. Each conversion is written in the line's remarks.
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
already in the library is changed). To rebuild from a newer bill or GRN register:

```sh
pip install openpyxl
tools/mep_rates.py "MAK Final Bill Checking.xlsx"
MAK_BILL="MAK Final Bill Checking.xlsx" python3 -m unittest tools/test_mep_rates.py
```

The build stops if any rows grouped into one item carry different rates. The bill
workbook is not committed.

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
.github/workflows/deploy-pages.yml  deploy to Pages + mirror main onto gh-pages
.nojekyll                           serve files as-is (no Jekyll processing)
```
