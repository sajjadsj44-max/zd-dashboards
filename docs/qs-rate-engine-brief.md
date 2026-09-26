# QS Rate Analysis Engine — revised brief

Revised version of the "Upgrade the Rate Analysis Dashboard into a professional QS Rate
Analysis Engine" prompt (26-Sep-2026). The first part says what was changed in the original
prompt and why. The second part is the revised prompt, and it is what this upgrade was built
against.

---

## Part A — What was wrong with the original prompt

| # | Issue in the original | Why it matters | Revision |
|---|---|---|---|
| 1 | The prompt stops mid-sentence ("The objective is to"). | The goal statement was lost. | Restored: every rate must be traceable from purchase unit → consumption → PKR per BOQ unit. |
| 2 | It asks for "deep web research" and "Assumed market rates" without a date/source format. | `CLAUDE.md` requires `<source>, DD-Mon-YYYY — <details>` and the same date in *Effective date*, and says **never invent a rate**. The two rules conflicted. | One rule: a rate needs a dated source. With no dated source the rate stays **0** or is marked `ASSUMPTION — no dated source`, with the evidence and basis written in the remarks. |
| 3 | Mixed units: "per RFT or metre", "M3", "SFT/RFT/CFT/M3". | House standard is decimal feet, **Sft / Rft / Cft / Nos / Kg / Ton**, PKR. Metric only appears as a converted source figure. | All BOQ units are imperial house units. Metric figures (GRN per m³, per metre) are converted and the conversion is written in the remarks. |
| 4 | It assumed a database, users and logins ("updated by", "save to database"). | The dashboard is a single static HTML file on GitHub Pages / Netlify. Data lives in the browser (`localStorage`, key `SAJ_QSCOST_v1`) with a JSON backup. There is no server and no login. | "Database" = the in-browser rate library plus the seed JSON blocks in the page. "Updated by" = the *Prepared by* name in Settings. Revision history is kept in the library and goes into the backup. |
| 5 | Three confidence words were used loosely (verified / assumed / 95 % accuracy). | The existing library already tags every rate line V / I / A. | Four levels, derived rather than typed: **Verified** (V, dated PO / GRN / signed quote, ≤ 12 months), **Reference-Based** (I, dated published or market evidence), **Assumed** (A, or unconfirmed consumption parameters), **Review Required** (unpriced component, source older than the staleness limit, lump "composite" line used as a material, or an audit finding). An item takes the **worst** level of its components. |
| 6 | "Do not rebuild … preserve data" beside "correct every item". | Users have edited items in their browsers. Silent overwrites would destroy their work. | Corrections are applied only to items and rate lines that are still exactly as seeded (guarded by the seed value). Anything edited by hand is left alone and flagged in the audit. |
| 7 | Tax is required but the calculation base was not defined. | Double counting OH / profit / tax is the most common error. | Order fixed: A Material (wastage inside each row where the builder calculates it) → B percentage wastage (0 for builder items) → C Labour → D Plant → E Access → F Transport = Direct cost → G Overheads on direct → H Profit on direct (or direct + OH, a setting) → I Tax on (direct + G + H) → Rate. Each base is printed. |
| 8 | Gypsum example priced the board at PKR 500 / sheet. | The prompt itself says this is not a market price. It must not end up in the library. | Used only as the automated calculation test (500 ÷ 32 × 1.05 = 16.406 / Sft). Library board rate stays unpriced until a quotation is entered. |
| 9 | "Research every missing rate from the wider internet." | From this build environment, supplier and price-list sites are blocked by the network egress policy. Only search-engine snippets were available. | Rates come from, in order: the embedded **GRN Price Register** (actual receipts, Phoenix / Quadrangle) → dated published lists / market pages → otherwise unpriced. Snippet-only figures are never marked Verified. |
| 10 | "Currency" and "location" switching. | No FX or location-factor source is held for finishes. | Location and rate-reference date are recorded per item. Currency stays PKR. The KPK MRS tab already carries official district factors for schedule rates. |
| 11 | No acceptance criteria. | "Test everything" cannot be checked. | Section 10 below lists the concrete checks that were run. |
| 12 | Scope: "every item in Pakistan construction" in one pass. | The library has ~ 750 items (52 seed, ~ 250 generated, 423 MEP). | Parametric **builders** calculate the item families that were lump sums (gypsum, tiles, paint, pipes, conduit, tray, cable, screed, formwork). The rest are audited and flagged, not deleted. |

---

## Part B — Revised prompt

**Role.** Senior Quantity Surveyor and dashboard developer, Pakistan high-rise work (grey structure,
finishes, MEP).

**Goal.** Every rate in the Rate Analysis module must be explainable as
*purchase price ÷ purchase unit → consumption per BOQ unit (from geometry, spacing, coverage or a
lab mix design) → + wastage → + labour (productivity × day rate) → + plant → + access / transport →
+ overheads → + profit → + tax = PKR per Sft / Rft / Cft / Kg / Nos.*
A lump-sum "material" that is really an installed rate is not an analysis.

### 1. Category-wise filtering

- 19 QS categories (Civil Works … Miscellaneous and Specialized Works), each with sub-categories.
  Every item carries one category and one sub-category. The classifier assigns them, and the user can
  override them per item. Items are not duplicated across categories.
- A Category and a Sub-category filter sit **above** the item search on the Rate Analysis screen and
  control the item dropdown, the search results, the Item Library, the Register and the reports.
- Changing the category keeps the current item if it still belongs to the category, and otherwise
  opens the first item in it. "All categories" shows everything.
- Search covers code, description, specification, material names and keywords.

### 2. Rates and sources

- Every rate line: code, name with specification, purchase unit, rate, location, effective date,
  confidence, and `Source, DD-Mon-YYYY — details`.
- Order of preference: dated Lahore quotation or GRN within 30 days → latest Phoenix GRN → other GRN
  in the register → dated published list or market page (Reference-Based) → unpriced / `ASSUMPTION —
  no dated source`. International prices are never used directly.
- Never fabricate a supplier, a URL, a date or a price.

### 3. Material-based build-ups (builders)

For each family, the builder takes editable parameters and writes one row per resource, each with a
**Given → Formula → Working → Result** note:

| Builder | Parameters (editable) | Resources calculated |
|---|---|---|
| Gypsum ceiling | board L × W, price per sheet line, main / furring spacing, hanger grid, drop, room size (for perimeter), screw spacing, compound and tape consumption, wastages | board, main channel, furring, wall angle, hanger rod, anchors, connector clips, screws, joint tape, compound, labour, access |
| Gypsum partition | wall height, stud spacing, layers per side, board size, insulation on/off | studs, top and bottom track, boards both sides, screws, tape, compound, insulation, labour |
| Tiles / stone | tile L × W, joint width and depth, adhesive kg per Sft (TDS), grout density, cutting wastage | tile, adhesive, grout (from joint geometry), spacers, labour, cutter |
| Paint system | primer, putty and finish coats, coverage per coat (TDS), purchase pack | primer, putty, paint, sanding, labour, access |
| Pipe | size, purchase length, fittings per 10 Rft by type, clamp spacing, jointing material | pipe, elbows, tees, sockets, clamps, solvent / fusion, test, labour |
| Conduit / tray / cable | size, bends and boxes per run, support spacing, drop height, terminations per run | conduit or tray, bends, couplers, supports, rods, anchors, glands, lugs, labour |
| Screed | thickness, mix, dry-volume factor, bag volume | cement bags, sand, water, labour |
| Formwork | ply sheet price and uses, battens and uses, props, oil coverage, nails | ply, timber, props, oil, nails, labour |

Concrete keeps the approved **lab mix designs** (each design is its own record) and the nominal-mix and
RMC generators already in the module. A nominal ratio is never substituted for an approved lab design.

Wastage is applied once. Builder rows carry their own wastage, and the item-level wastage percentage is
then 0. Inclusions and exclusions are stated so that jointing, painting or insulation are not counted twice.

### 4. Calculation order

`Direct = Σ material (incl. row wastage) + % wastage + labour + plant + access + transport`;
`G = Direct × OH%`; `H = (Direct [+ G]) × Profit%`; `I = (Direct + G + H) × Tax%`;
`Rate = Direct + G + H + I`. OH, profit and tax are editable per item. Defaults are in Settings.

### 5. Editor

Edit consumption, rates, wastage, crew and productivity; add or remove material, labour and plant rows;
change builder parameters and rebuild; duplicate; add new; record location and rate date. Every edit
stamps *updated at / by*. Rate-line edits are logged with their old and new values and the items
they re-priced. The user can save a revision of an item and compare any two revisions, or a revision
against the current build-up.

### 6. Register and reports

The Register lists: code, category, sub-category, description, specification, unit, material, labour,
equipment, other direct, overheads, profit, tax, final rate, confidence, source summary and last updated.
Filters: category, sub-category, confidence, location, updated between. Exports: selected or full
register to Excel / CSV; detailed analysis workbook (one sheet per item with formulas, notes, sources);
printable PDF sheets per item or per selected categories; material and labour breakdown; revision
comparison.

### 7. Audit

A built-in audit lists, per item: unpriced components, composite lump lines used as materials, empty
material sections, sources older than the staleness limit, percentage wastage on top of builder
wastage, arithmetic errors found in seed items, and missing accessories. Items are flagged, never
deleted.

### 8. Units

Decimal feet; Sft, Rft, Cft, Nos, Kg, Ton, Ltr, Bag; PKR. Rebar diameter may be given in sutar.
Metric appears only in source conversions.

### 9. Design

Keep the existing SAJ QSCOST styling. Put the filters at the top, then the item, specification, unit and
final rate, then the editable breakdown, then sources, assumptions, inclusions / exclusions, revisions and
exports. No decorative charts. Must work on phone width.

### 10. Acceptance checks

1. Each of the 19 categories filters the dropdown, search, library and register, and switching
   category resets or keeps the selection correctly.
2. Gypsum test: board 8 × 4 ft at PKR 500 per sheet with 5 % wastage gives 15.625 → **16.406 / Sft** for the board row.
3. Changing the cement rate re-prices every concrete, mortar, plaster and screed item in proportion to
   its cement consumption, and the change is logged.
4. OH / profit / tax percentages give the hand-calculated result on their stated bases.
5. Edits survive a page reload. Backup JSON carries history and revisions.
6. Excel, CSV and print sheets generate.
7. No console errors. Layout works at 390 px and at desktop width.
