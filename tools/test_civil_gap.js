#!/usr/bin/env node
/* Browser checks for the civil gap-analysis block (#raCivilData, tools/civil_gap_data.py).

     python3 -m http.server 8765 &            # from the repo root
     node tools/test_civil_gap.js             # needs playwright (npm i -g playwright)

   QE_URL  page to test (default http://127.0.0.1:8765/zameen-developments/index.html)

   Checks: a fresh library carries all CV items priced, with no unpriced gaps except the ones
   the block leaves open on purpose (TOPSOIL); the seed repairs (FN-560 frame, EW-950 paver,
   EW-960 manhole) are applied; a saved library from before this block is upgraded on the next
   load (missing items added, L-HELPER / BRK-2 moved from their published values), while a line
   or item edited by hand is left alone; and no page errors occur. */
let pw;
try { pw = require("playwright"); } catch (e) { pw = require("/opt/node22/lib/node_modules/playwright"); }
const URL = process.env.QE_URL || "http://127.0.0.1:8765/zameen-developments/index.html";
let fails = 0, passes = 0;
function ok(cond, msg){ if (cond) { passes++; console.log("  ✓ " + msg); } else { fails++; console.log("  ✗ " + msg); } }

(async () => {
  const browser = await pw.chromium.launch();
  const ctx = await browser.newContext();
  await ctx.route(/cdn\.jsdelivr\.net|docs\.google\.com|fonts\.g|cdnjs/, r => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(String(e)));
  async function load(){ await page.goto(URL, {waitUntil: "domcontentloaded"}); await page.waitForTimeout(3500); }

  await load();
  await page.evaluate(() => { localStorage.clear(); });
  await load();
  const fresh = await page.evaluate(() => {
    const D = JSON.parse(document.getElementById("raCivilData").textContent);
    const R = {}; RA.rates.forEach(r => R[r.code] = r);
    const cv = RA.items.filter(i => /^CV-/.test(i.id));
    const calc = {}; cv.concat(RA.items.filter(i => ["FN-560", "EW-950", "EW-960"].includes(i.id)))
      .forEach(i => { const c = raCalc(i); calc[i.id] = {rate: c.rate, gaps: c.gaps}; });
    return {rev: D.rev, civRev: RA.civRev, want: D.items.length, have: cv.length, calc,
            helper: R["L-HELPER"].rate, brk2: R["BRK-2"].rate,
            fn560: RA.items.find(i => i.id === "FN-560").M.map(r => r.ref),
            ew950: RA.items.find(i => i.id === "EW-950").M.map(r => r.ref),
            ew960: RA.items.find(i => i.id === "EW-960").M.length,
            missing: D.items.flatMap(i => [].concat(i.M, i.L, i.P).map(r => r.ref)).filter(c => !R[c]),
            unsourced: RA.rates.filter(r => D.rates.some(d => d.code === r.code) && !/\d{2}-[A-Z][a-z]{2}-\d{4}|ASSUMPTION/.test(r.src)).map(r => r.code)};
  });
  console.log("Fresh library");
  ok(fresh.civRev === fresh.rev, "block applied (civRev " + fresh.civRev + ")");
  ok(fresh.have === fresh.want && fresh.want === 133, "all " + fresh.want + " CV items present (" + fresh.have + ")");
  ok(fresh.missing.length === 0, "every row points at an existing rate line" + (fresh.missing.length ? ": " + fresh.missing.join(", ") : ""));
  ok(fresh.unsourced.length === 0, "every new line names a dated source or ASSUMPTION" + (fresh.unsourced.length ? ": " + fresh.unsourced : ""));
  const open = Object.keys(fresh.calc).filter(k => fresh.calc[k].gaps > 0);
  ok(open.length === 1 && open[0] === "CV-128", "only CV-128 (topsoil) is left unpriced — " + open.join(", "));
  ok(Object.keys(fresh.calc).every(k => fresh.calc[k].rate > 0), "every item has a rate above 0");
  ok(fresh.helper === 1538 && fresh.brk2 === 12.5, "L-HELPER 1,538 and BRK-2 12.5 applied");
  ok(fresh.fn560.includes("GRN-QUA-STR-000134"), "FN-560 carries the GI door frame");
  ok(fresh.ew950[0] === "PAVER-60", "EW-950 carries the paver block");
  ok(fresh.ew960 > 10, "EW-960 carries its materials");
  ok(Math.abs(fresh.calc["CV-001"].rate - 69.03 * 1.18) < 0.05, "CV-001 = MRS 69.03 + 8% OH + 10% profit (" + fresh.calc["CV-001"].rate.toFixed(2) + ")");

  // an older saved library: no block rev, published helper / brick values, seed door; one hand edit
  await page.evaluate(() => {
    RA.items = RA.items.filter(i => !/^CV-/.test(i.id) || i.id === "CV-034");
    RA.items.find(i => i.id === "CV-034").note = "edited by hand";
    RA.items.find(i => i.id === "CV-034").M[0].qty = 13;
    RA.rates.find(r => r.code === "L-HELPER").rate = 1300;
    RA.rates.find(r => r.code === "L-HELPER").date = "2026-09-23";
    RA.rates.find(r => r.code === "BRK-2").rate = 16;                 // typed by the user
    RA.rates.find(r => r.code === "BRK-2").date = "2026-09-25";
    const d = RA.items.find(i => i.id === "FN-560"); d.M = [{ref: "DOOR-W", qty: 1}, {ref: "DOOR-HW", qty: 0.055}];
    const w = RA.items.find(i => i.id === "EW-950"); w.M = [{ref: "SAND-CH", qty: 0.14}]; // edited, not seed
    delete RA.civRev; raPersist();
  });
  await page.waitForTimeout(300);
  await load();
  const up = await page.evaluate(() => {
    const R = {}; RA.rates.forEach(r => R[r.code] = r);
    return {civRev: RA.civRev, n: RA.items.filter(i => /^CV-/.test(i.id)).length,
            cv34: RA.items.find(i => i.id === "CV-034"), helper: R["L-HELPER"].rate, brk2: R["BRK-2"].rate,
            fn560: RA.items.find(i => i.id === "FN-560").M.map(r => r.ref),
            ew950: RA.items.find(i => i.id === "EW-950").M.map(r => r.ref + ":" + r.qty)};
  });
  console.log("Saved library from before the block");
  ok(!!up.civRev && up.n === 133, "missing CV items added back (" + up.n + ")");
  ok(up.cv34.note === "edited by hand" && up.cv34.M[0].qty === 13, "a hand-edited CV item is left alone");
  ok(up.helper === 1538, "L-HELPER moved from the published 1,300");
  ok(up.brk2 === 16, "BRK-2 typed by the user (16) is kept");
  ok(up.fn560.includes("GRN-QUA-STR-000134"), "seed FN-560 gets its frame");
  ok(up.ew950.length === 1 && up.ew950[0] === "SAND-CH:0.14", "edited EW-950 is left alone");

  ok(errors.length === 0, "no page errors" + (errors.length ? ": " + errors.join(" | ") : ""));
  await browser.close();
  console.log(`\n${passes} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})();
