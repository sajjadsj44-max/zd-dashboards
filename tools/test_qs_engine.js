#!/usr/bin/env node
/* Browser tests for the QS Rate Analysis Engine (Rate Analysis module of the dashboard).

     python3 -m http.server 8765 &            # from the repo root
     node tools/test_qs_engine.js             # needs playwright (npm i -g playwright)

   QE_URL   page to test (default http://127.0.0.1:8765/zameen-developments/index.html)
   QE_LIBS  folder holding exceljs/dist/exceljs.min.js and papaparse/papaparse.min.js — CDN requests are
            answered from there when the CDN is not reachable (offline / sandboxed runs)
   QE_SHOTS folder for screenshots (optional)

   Checks: category filtering for all 19 categories and category switching, the gypsum 8 × 4 ft example,
   price-change propagation and its log, OH / profit / tax bases, persistence across a reload, revision
   compare, register / CSV / Excel exports, phone-width layout, and that no page errors occur. */
const path = require("path"), fs = require("fs");
let pw;
try { pw = require("playwright"); } catch (e) { pw = require("/opt/node22/lib/node_modules/playwright"); }
const URL = process.env.QE_URL || "http://127.0.0.1:8765/zameen-developments/index.html";
const LIBS = process.env.QE_LIBS || "";
const SHOTS = process.env.QE_SHOTS || "";
let fails = 0, passes = 0;
function ok(cond, msg){ if (cond) { passes++; console.log("  ✓ " + msg); } else { fails++; console.log("  ✗ " + msg); } }
function near(a, b, tol){ return Math.abs(a - b) <= (tol == null ? 0.005 : tol); }

(async () => {
  const exe = fs.existsSync("/opt/pw-browsers/chromium") ? undefined : undefined;
  const browser = await pw.chromium.launch(exe ? {executablePath: exe} : {});
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, acceptDownloads: true});
  const errors = [];
  await ctx.route(/cdn\.jsdelivr\.net|docs\.google\.com|fonts\.g/, async route => {
    const u = route.request().url();
    if (LIBS && /exceljs/.test(u)) return route.fulfill({path: path.join(LIBS, "exceljs/dist/exceljs.min.js"), contentType: "application/javascript"});
    if (LIBS && /papaparse/.test(u)) return route.fulfill({path: path.join(LIBS, "papaparse/papaparse.min.js"), contentType: "application/javascript"});
    if (/chart\.js/.test(u)) return route.fulfill({body: "window.Chart=function(){return{destroy(){},update(){}}};", contentType: "application/javascript"});
    return route.abort();
  });
  const page = await ctx.newPage();
  page.on("pageerror", e => errors.push(String(e)));
  page.on("dialog", d => d.accept("test revision"));
  await page.goto(URL, {waitUntil: "domcontentloaded"});
  await page.evaluate(() => localStorage.clear());
  await page.reload({waitUntil: "domcontentloaded"});
  await page.click("#tabRA");
  await page.waitForFunction(() => typeof RA !== "undefined" && RA && window.qeEngine && RA.qe && RA.qe.rev === qeEngine.rev, null, {timeout: 20000});

  console.log("Sync of the engine data");
  const s = await page.evaluate(() => ({
    rev: RA.qe.rev, applied: RA.qe.applied.length, skipped: Object.keys(RA.qe.skipped).length,
    items: RA.items.length, fn550: RA.items.find(i => i.id === "FN-550").gen.k,
    sc420: RA.items.find(i => i.id === "SC-420").M.map(r => [r.ref, r.qty]),
    nails: RA.rates.find(r => r.code === "NAILS").rate, added: RA.qe.added.length}));
  ok(s.applied === 18 && s.skipped === 0, "18 seed items rebuilt as material-based analyses, none skipped (" + s.applied + ")");
  ok(s.fn550 === "qe-gypc", "FN-550 gypsum ceiling uses the gypsum builder");
  ok(near(s.sc420[0][1], 0.1083 / 5 / 1.25 * 1.05, 1e-5) && near(s.sc420[1][1], 0.1083 * 0.8 * 1.05, 1e-4), "SC-420 screed corrected: cement " + s.sc420[0][1] + " bag, sand " + s.sc420[1][1] + " cft (incl. 5% wastage)");
  ok(s.nails === 715, "NAILS corrected to the Phoenix GRN (715/kg)");
  ok(s.added === 7, "7 new builder items added");

  console.log("Category filtering (19 categories)");
  const cats = await page.evaluate(() => qeEngine.data.cats.map(c => c.id));
  ok(cats.length === 19, "19 QS categories");
  await page.evaluate(() => raGo("an"));
  let emptyCats = [];
  for (const c of cats) {
    await page.selectOption("#qeCat", c);
    const r = await page.evaluate(cid => {
      const opts = [...document.querySelectorAll("#raPick option")].map(o => o.value).filter(Boolean);
      const bad = opts.filter(id => qeEngine.classify(raItemById(id)).c !== cid);
      return {n: opts.length, bad: bad.length, cur: RA_CUR, curCat: RA_CUR ? qeEngine.classify(raItemById(RA_CUR)).c : null};
    }, c);
    if (!r.n) emptyCats.push(c);
    ok(r.bad === 0 && (!r.n || r.curCat === c), c + ": " + r.n + " items in dropdown, all in category, selection moved into it");
  }
  console.log("  categories with no items yet: " + (emptyCats.join(", ") || "none"));
  await page.selectOption("#qeCat", "C14");
  await page.fill("#raAnQ", "cable");
  await page.waitForTimeout(200);
  const srch = await page.evaluate(() => [...document.querySelectorAll("#raAnQRes [data-rasq]")].map(e => qeEngine.classify(raItemById(e.dataset.rasq)).c));
  ok(srch.length > 0 && srch.every(c => c === "C14"), "search 'cable' inside Electrical returns only Electrical items (" + srch.length + ")");
  await page.fill("#raAnQ", "");
  await page.selectOption("#qeCat", "");
  const all = await page.evaluate(() => [document.querySelectorAll("#raPick option").length, RA.items.length]);
  ok(all[0] === all[1], "All categories shows every item (" + all[0] + ")");

  console.log("Gypsum ceiling, 8 × 4 ft board at PKR 500 / sheet, 5% wastage");
  const g = await page.evaluate(() => {
    const it = raItemById("FN-550"); const bd = it.M[0];
    const line = RA.rates.find(r => r.code === bd.ref); const old = line.rate; line.rate = 500;
    const amt = raRowAmt(bd); line.rate = old;
    return {qty: bd.qty, perSft: 500 / 32, amt: amt, rows: it.M.length, notes: it.M.every(r => /=/.test(r.note))};
  });
  ok(near(g.perSft, 15.625, 1e-9), "board 500 ÷ 32 = 15.625 / Sft");
  ok(near(g.amt, 16.406, 0.001), "with 5% wastage = " + g.amt.toFixed(3) + " / Sft (expected 16.406)");
  ok(g.rows === 11 && g.notes, "11 resource rows (board, channels, angle, hangers, rod, anchors, connectors, screws, tape, compound), each with formula = working");

  console.log("Material price change → dependent analyses re-priced and logged");
  await page.evaluate(() => raGo("mat"));
  await page.fill("#raMQ", "Cement — OPC");
  await page.waitForTimeout(150);
  const before = await page.evaluate(() => ["SC-420", "PLS-I05-14", "PCC-148-V", "QS-SCR-2"].map(id => { const i = raItemById(id); return i ? [id, raCalc(i).A, i.M.find(r => r.ref === "CEM") ? i.M.find(r => r.ref === "CEM").qty : 0] : null; }).filter(Boolean));
  const inp = page.locator('#raMatTbl input[data-ra-rt$=".rate"]').first();
  const oldCem = Number(await inp.inputValue());
  await inp.click(); await inp.fill(String(oldCem + 100)); await inp.press("Tab");
  await page.waitForTimeout(200);
  const after = await page.evaluate(ids => ids.map(b => { const i = raItemById(b[0]); return [b[0], raCalc(i).A]; }), before);
  before.forEach((b, i) => ok(near(after[i][1] - b[1], 100 * b[2], 0.01), b[0] + ": material +" + (after[i][1] - b[1]).toFixed(3) + " = 100 × " + b[2].toFixed(5) + " bag"));
  const log = await page.evaluate(() => RA.qe.log[0]);
  ok(log && log.code === "CEM" && log.field === "rate" && log.n > 10, "change logged: CEM " + (log && log.from) + " → " + (log && log.to) + ", " + (log && log.n) + " analyses re-priced");
  await inp.click(); await inp.fill(String(oldCem)); await inp.press("Tab");

  console.log("Overheads, profit and tax on their bases");
  const t = await page.evaluate(() => {
    const it = raItemById("QS-SCR-2"); it.oh = 8; it.prof = 10; it.tax = 5; RA.set.profOnOh = false;
    const c = raCalc(it); const r1 = {G: c.G, H: c.H, I: c.I, rate: c.rate, sub: c.sub};
    RA.set.profOnOh = true; const c2 = raCalc(it); RA.set.profOnOh = false; it.tax = null;
    return {r1: r1, H2: c2.H, sub: c.sub};
  });
  ok(near(t.r1.G, t.sub * 0.08) && near(t.r1.H, t.sub * 0.10) && near(t.r1.I, (t.sub + t.r1.G + t.r1.H) * 0.05) && near(t.r1.rate, t.sub + t.r1.G + t.r1.H + t.r1.I), "G = 8% × direct, H = 10% × direct, I = 5% × (direct + G + H)");
  ok(near(t.H2, (t.sub + t.r1.G) * 0.10), "profit on (direct + overheads) when that setting is chosen");

  console.log("Editor: builder parameter, revision, compare, persistence");
  await page.evaluate(() => { RA_CUR = "FN-550"; raGo("an"); });
  await page.click('[data-qe-act="rev"]');
  const r0 = await page.evaluate(() => raCalc(raItemById("FN-550")).A);
  await page.fill('[data-qe-p="fcSp"]', "1.5"); await page.press('[data-qe-p="fcSp"]', "Tab");
  await page.waitForTimeout(150);
  const fc = await page.evaluate(() => { const it = raItemById("FN-550"); return it.M.find(r => r.ref === "QE-GYP-FC").qty; });
  ok(near(fc, 1 / 1.5 * 1.05, 1e-5), "furring spacing 1.5 ft → " + fc + " Rft/Sft");
  await page.click('[data-qe-act="compare"]');
  const cmp = await page.evaluate(() => document.querySelectorAll("#qeCmp tr.qe-chg").length);
  ok(cmp > 0, "revision compare shows " + cmp + " changed rows");
  await page.waitForTimeout(500);
  await page.reload({waitUntil: "domcontentloaded"});
  await page.click("#tabRA");
  await page.waitForFunction(() => typeof RA !== "undefined" && RA && RA.qe, null, {timeout: 20000});
  const kept = await page.evaluate(() => { const it = raItemById("FN-550"); return {sp: it.gen.p.fcSp, revs: (it.revs || []).length, upd: !!it.upd, log: RA.qe.log.length}; });
  ok(kept.sp === 1.5 && kept.revs >= 2 && kept.upd && kept.log >= 2, "after reload: parameter, " + kept.revs + " revisions, update stamp and " + kept.log + " log entries kept");

  console.log("Register and exports");
  await page.evaluate(() => raGo("qsr"));
  await page.click('#raSub [data-rv="qsr"]');
  await page.selectOption("#qeRC", "C08");
  const reg = await page.evaluate(() => document.querySelectorAll("#qeRTbl tbody tr").length);
  ok(reg >= 3, "register filtered to Gypsum / ceiling / partition: " + reg + " rows");
  const [dl1] = await Promise.all([page.waitForEvent("download"), page.click('[data-qe-act="regCsv"]')]);
  const csvTxt = fs.readFileSync(await dl1.path(), "utf8");
  ok(/Final rate PKR/.test(csvTxt) && csvTxt.trim().split("\n").length === reg + 1, "register CSV: " + (csvTxt.trim().split("\n").length - 1) + " rows");
  if (LIBS) {
    const [dl2] = await Promise.all([page.waitForEvent("download", {timeout: 30000}), page.click('[data-qe-act="detXls"]')]);
    const st = fs.statSync(await dl2.path());
    ok(/\.xlsx$/.test(dl2.suggestedFilename()) && st.size > 5000, "detailed analyses workbook " + dl2.suggestedFilename() + " (" + st.size + " bytes)");
    const [dl3] = await Promise.all([page.waitForEvent("download", {timeout: 30000}), page.click('[data-qe-act="regXls"]')]);
    ok(/\.xlsx$/.test(dl3.suggestedFilename()), "register workbook " + dl3.suggestedFilename());
  } else console.log("  (Excel skipped: set QE_LIBS to test it offline)");
  const [pop] = await Promise.all([page.waitForEvent("popup"), page.click('[data-qe-act="pdfSel"]')]);
  await pop.waitForLoadState("domcontentloaded");
  const pages = await pop.evaluate(() => document.querySelectorAll(".pg").length);
  ok(pages === reg, "printable PDF sheets: " + pages + " pages");
  await pop.close();

  console.log("Audit view");
  await page.click('#raSub [data-rv="qsa"]');
  await page.waitForTimeout(300);
  const aud = await page.evaluate(() => ({rows: document.querySelectorAll("#qeABody tr").length, txt: document.getElementById("qeABody").textContent}));
  ok(/Rates requiring supplier quotations/.test(aud.txt) && /QE-GYP-BD12/.test(aud.txt) && /SC-420/.test(aud.txt), "audit lists corrections, quotation needs (gypsum board) and findings");

  console.log("Layout");
  if (SHOTS) { await page.evaluate(() => { RA_CUR = "FN-550"; raGo("an"); }); await page.screenshot({path: path.join(SHOTS, "desktop-analysis.png"), fullPage: false}); }
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => { RA_CUR = "FN-550"; raGo("an"); });
  await page.waitForTimeout(200);
  const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(ov <= 2, "no horizontal page overflow at 390 px (" + ov + " px)");
  if (SHOTS) await page.screenshot({path: path.join(SHOTS, "phone-analysis.png"), fullPage: false});

  ok(errors.length === 0, "no page errors" + (errors.length ? ": " + errors.slice(0, 3).join(" | ") : ""));
  await browser.close();
  console.log("\n" + passes + " passed, " + fails + " failed");
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
