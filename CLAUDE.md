# zd-dashboards

Static, self-contained HTML dashboards for Zameen Developments, published on
Netlify and GitHub Pages. Owner: Sajjad Ahmad (Quantity Surveyor).

Read this before touching the dashboard. It records how the thing is built, the
rules the rate data lives by, and the decisions behind the numbers already in
it — several of which look like omissions until you know why they are there.

## Units and house rules

Decimal feet to 3 dp, Sft, cft, Nos, kg/ton, PKR. Never m, mm, sqm or cum.
Rebar diameter in sutar is the one exception. Quantities carry their dimension
string (Nos × L × W × H); openings are separate negative rows.

**Never invent a rate.** Every rate is either verified against a dated source or
flagged as an assumption. This rule is not advisory — it is enforced in code
(see the V/I/A section) and it is the reason 46 rate lines are still blank.

## Layout

```
index.html                          landing page listing all dashboards
netlify.toml                        publish settings, cache + security headers
zameen-developments/index.html      the dashboard (single file, ~706 KB)
tools/harden.py                     build a publishable dashboard from the authoring copy
tools/validate.py                   pre-publish checks, gates every deploy
.github/workflows/deploy-pages.yml  validate → deploy to Pages → mirror to gh-pages
```

Run the checks any time: `python3 tools/validate.py`

## The three dashboards

One file, three tabs, each with its own data source.

**Change Management** — reads Sheet1 of the Change Management Tracker over
Google Sheets `gviz` JSONP, plus a Sheet 3 of project details that it finds by
trying a list of candidate tab names and GIDs. Polls every 30 s.

**Payment** — a separate sheet, a separate JSONP loader. Tracks vouchers through
nine dated stages (Vendor → QS → Jeffi → PR → PO → Admin → Audit → Finance →
Paid) with cycle time, desk analysis, retention and back charge. The
best-built of the three.

**BOQ & Rate Analysis** — the only tab with no sheet behind it. Everything lives
in `localStorage` under `SAJ_QSCOST_v1`. This asymmetry matters: clear the
browser cache and the rate database, item library and project BOQ are gone. A
JSON backup/restore exists but is manual.

## The rate database

91 rows seeded in `RA_MAT_SEED`, shape:

```
[code, kind(M/L/P), name, unit, rate, location, source, date, status]
```

`raCalc` builds the rate in house order: A material + B wastage (material only)
+ C labour + D plant + E access + F transport = direct subtotal, then G
overheads and H profit, with a setting for whether profit sits on overheads.

### V / I / A — what the flags mean

- **V** — verified, dated source. Requires **both** a date and a source. A row
  marked V with either missing is downgraded automatically.
- **I** — dated market indication, no procurement backing.
- **A** — assumption or unrated.

`raRowVs` enforces this. A rate typed straight into a build-up, with no link to
a rate-database line, is **always A** — it has no date and no source, so it
cannot be anything else. This was a bug once: typed rates rendered as blue
"Verified" and counted zero toward the assumption total, which made a guess
indistinguishable from a sourced rate on a printed analysis. Do not "simplify"
it back.

### Ageing

Every rate is aged against its date: green, amber past `RA.set.warnDays` (90),
red past `RA.set.staleDays` (180), grey when undated. The 90-day threshold is
deliberate — it turns the MRS rows amber before the schedule's own window
expires on 31 December 2026.

### Seed merge

`raMergeSeedRates` runs on load so new seeded rates reach an existing browser.
It fills **gaps only**: a row sitting at zero, or a row still carrying the exact
placeholder wording the seed shipped it with (matched by
`RA_SEED_PLACEHOLDER`). The moment a rate is typed over a placeholder the remark
changes, and the row is then the user's and never overwritten. Keep that
property in any change here.

## What the rates are, and why

**45 rated / 46 blank.** 28 rows carry MRS.

**MRS Punjab, 2nd Bi-Annual 2026 (01.07.2026–31.12.2026), Lahore column** — the
Finance Department input-rate schedule, flagged V, dated `2026-07-01`. Lahore is
the first district column in every sheet. Covers 12 labour trades (skilled 2,000
/day, unskilled 1,538/day), 3 plant items, and materials including binding wire
330/kg, brick 17.00 each, porcelain tile 185/Sft, gypsum board 70/Sft, flush
door 600/Sft, uPVC 100 mm 388/Rft, copper 2.5 mm² 35.97/Rft, wash basin 8,000,
WC 18,000, sprinkler head 1,681.

Each MRS remark also records the neighbouring options in the same series — other
tile sizes, other pipe diameters, basin with and without pedestal — so a change
of specification does not mean going back to the schedule.

**Sajjad's own market rates are kept over MRS**, with MRS recorded in the remark
as a cross-check. On a private job the market rate is the commercial reality and
the schedule is the benchmark. Cement 1,575 (MRS 1,410); Grade 60 steel 260
(MRS 239.50); Chenab sand 80 (MRS 60.00).

### Traps worth knowing

- **MRS aggregate is quoted at quarry site**, excluding carriage. It is *not*
  comparable with the delivered Lahore crush rates of 180–185. Both crush rows
  carry that warning instead of a false discrepancy.
- **MRS publishes Grade 40 and Grade 60 steel only.** There is no Grade 72 line,
  so `STL72` cannot be settled from the schedule. It still carries 286 from a
  superseded band and needs a supplier figure.
- **MRS machinery is per hour**, the rate database is per day, and the three
  plant rows are referenced by existing build-ups whose quantities mean days. The
  unit stays; the hourly figure is converted at 8 h with the arithmetic written
  into the remark.

### Why 46 rows are still blank

Not an oversight. Three reasons:

1. **Unit mismatch.** MRS prices emulsion and primer per gallon, waterproofing
   per kg, anti-termite per litre; the build-ups are per Sft. Converting needs a
   coverage or dosage figure that would be an assumption, not a source.
2. **No MRS line.** Concrete blocks, ready-mix, shuttering ply, props, mould oil,
   excavator, concrete pump, hoist, cradle, bar bender, tile cutter, 5 kVA
   generator. MRS has a 100 KW plant and a lighting set, neither of which is a
   5 kVA generator.
3. **Specification-dependent.** "Approved make and size" means nothing without a
   named spec, and the open web will not supply one.

**The open web is not a usable source for these.** Thirteen searches produced:
porcelain tile at 1,000–2,000/Sft against an MRS 185; PPRC priced by pressure
class with no diameter; gypsum and electrical only as "a 5 marla house costs X";
excavator hire in US dollars. A "Punjab" query returned Indian rupees, and one
result turned a *steel* grade into a cement rate. Use MRS, or a supplier
quotation against a named spec. Do not fill these from search snippets.

## Publishing

`zameen-developments/index.html` is a **hardened, minified build**, not the
authoring copy. The authoring copy is gitignored and kept outside the repo.

```sh
npm install terser clean-css-cli          # once
tools/harden.py NEW_VERSION.html zameen-developments/index.html
```

`harden.py` injects ownership markers, pins the CDN libraries with SRI digests,
then minifies.

**Anything edited directly in the minified build is lost on the next rebuild.**
Several changes currently live only there — the V/I/A fix, rate ageing, the seed
merge, the rate styling, and all the MRS rates. They need porting into the
authoring copy.

### CDN pinning

Three jsDelivr libraries carry SRI digests; the table and the recompute command
are at the top of `harden.py`. Chart.js loads from `dist/chart.umd.js`, not
`dist/chart.umd.min.js` — the `.min.js` does not exist in the package, so
jsDelivr auto-minifies on the fly and serves a file no digest can match.

### Headers

`netlify.toml` sets its headers for `/*`, not `/*.html`. The shared link is the
bare site root and the rewrite serves the dashboard there, so `/` never matches
a `*.html` rule — scoping it that way leaves the most-visited URL with no
headers at all. GitHub Pages cannot set headers, so the Pages mirror has the SRI
pinning but not the CSP or framing protection. Share the Netlify link.

## Open items

- Port everything above into the authoring copy, then rebuild.
- Grade 72 steel — needs a supplier rate.
- Paint, waterproofing, anti-termite — need spread/coverage rates to convert.
- Quotation tracker (vendor, quote ref, validity) for spec-dependent rows.
- Rate-database import — 46 blanks currently have to be typed one at a time.
- Logos out of the HTML — ~400 KB of ~706 KB, re-downloaded on every visit.
- Pause the 30 s polls when the tab is hidden; dedupe the two JSONP loaders.
- Payment: SLA thresholds per desk, to flag stuck vouchers rather than only
  measuring the average.

## Environment notes

Web search works; **fetching pages does not** — outbound HTTPS is restricted by
organisation policy, `finance.punjab.gov.pk` included. MRS PDFs have to be
uploaded by hand. There is no Gmail attachment-download tool, so email
attachments must be uploaded too.
