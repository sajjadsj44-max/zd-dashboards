#!/usr/bin/env python3
"""Daily check of the government rate schedules the dashboard carries.

    tools/rate_watch.py            check, update the dashboard, open issues
    tools/rate_watch.py --dry-run  check and report only; change nothing

Run every day by .github/workflows/rate-watch.yml, which offers whatever this
changes as a pull request on the rate-watch/update branch - the live dashboard
only changes when that pull request is merged.

KPK  - reads the Market Rate System page of the KPK Finance Department. When an
       edition newer than the one in the KPK MRS tab is listed, its PDF is
       downloaded, parsed by tools/kpk_mrs.py and written into the dashboard.
       The notification date is read from the notification itself; when it
       cannot be found the PDF's own issue date is used and the tab says so.
       A new edition that does not parse cleanly is never published - an issue
       is opened with the link instead, and the load is retried every day.
Punjab - reads the Punjab Finance Department market-rate and input-rate pages
       and records every Lahore PDF listed there. A Lahore PDF that was not
       listed before opens an issue, since the dashboard has no Punjab parser
       yet, and is shown on the KPK MRS tab under "Auto-watch".

State lives in data/rate-watch.json. It changes only when something new is
found, so a quiet day opens no pull request. Exit status 1 means the KPK site
could not be reached or read - GitHub then flags the run as failed, which is the
alert. The Punjab site often does not answer GitHub's runners; that is logged as
a warning on the run and retried the next day.
"""
import argparse
import datetime as dt
import html as htmllib
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kpk_mrs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "rate-watch.json"
KPK_LIST = "https://www.finance.gkp.pk/articles/info-desk/market-rate-system"
PUNJAB_PAGES = ["https://finance.punjab.gov.pk/market-rates-system",
                "https://finance.punjab.gov.pk/details/market-rates-bi-annual-period",
                "https://finance.punjab.gov.pk/input-rates"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
LINK = re.compile(r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.S | re.I)


def log(*a):
    print(*a, flush=True)


def fetch(url, binary=False, tries=2):
    """Pages get 30 s per attempt, PDFs 120 s; a site that does not answer costs
    about a minute, not the quarter hour of longer timeouts."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120 if binary else 30) as r:
                b = r.read()
            return b if binary else b.decode("utf-8", "replace")
        except Exception as e:  # network errors, HTTP errors
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def links(page_html, base):
    out = []
    for href, text in LINK.findall(page_html):
        t = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
        out.append((urljoin(base, htmllib.unescape(href.strip())), t))
    return out


def edition_key(s):
    """(year, half) from 'Market Rate System (MRS) 2025 (Ist Bi-Annual)', a slug, or
    'MRS-2025 (1st Bi-Annual)'; None if the text names no edition."""
    s = s.lower().replace("-", " ")
    y = re.search(r"\b(20\d\d)\b", s)
    pat = r"\b(ist|1st|first|i)\b|\b(2nd|iind|second|ii)\b"
    h = (re.search(pat, s[y.end():]) or re.search(pat, s)) if y else None
    if not y or not h or "bi" not in s:
        return None
    return int(y.group(1)), 1 if h.group(1) else 2


def edition_name(key):
    return f"MRS-{key[0]} ({'1st' if key[1] == 1 else '2nd'} Bi-Annual)"


def find_date(text):
    """First 'Dated Peshawar, the dd/mm/yyyy' style date in a notification, as ISO."""
    t = re.sub(r"\s+", " ", text)
    for pat in (r"Dated\s+Peshawar[^0-9]{0,20}(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})",
                r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(20\d\d)"):
        m = re.search(pat, t, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y += 2000 if y < 100 else 0
            try:
                return dt.date(y, mo, d).isoformat()
            except ValueError:
                pass
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(%s)[a-z]*,?\s+(20\d\d)" % "|".join(MON), t, re.I)
    if m:
        return dt.date(int(m.group(3)), MON.index(m.group(2).lower()[:3]) + 1, int(m.group(1))).isoformat()
    return ""


def pdf_info(path):
    import pymupdf
    doc = pymupdf.open(path)
    first = " ".join(doc[i].get_text() for i in range(min(6, len(doc))))
    cd = (doc.metadata or {}).get("creationDate", "")
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", cd)
    return {"pages": len(doc), "text": first,
            "created": f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""}


class Watch:
    def __init__(self, dry):
        self.dry = dry
        self.state = json.loads(STATE.read_text()) if STATE.exists() else {}
        self.changes, self.issues, self.errors = [], [], []

    # ---- KPK ----
    def kpk(self):
        cur = kpk_mrs.current()
        have = edition_key(cur.get("edition", "")) or (0, 0)
        page = fetch(KPK_LIST)
        found = {}
        for url, text in links(page, KPK_LIST):
            if "market-rate-system" not in url.lower() and "market rate system" not in text.lower():
                continue
            k = edition_key(text) or edition_key(url.rsplit("/", 1)[-1])
            if k and (k not in found or "/article/" in url):
                found[k] = (url, text)
        if not found:
            raise RuntimeError(f"{KPK_LIST}: no MRS edition links found - page layout may have changed")
        newest = max(found)
        url, title = found[newest]
        log(f"KPK: dashboard has {cur.get('edition')}, newest listed {edition_name(newest)} - {url}")
        st = self.state.setdefault("kpk", {})
        st.update({"list": KPK_LIST, "newest": edition_name(newest), "newestUrl": url})
        if newest <= have:
            return
        self.load_kpk(newest, url, title)

    def load_kpk(self, key, url, title):
        name = edition_name(key)
        article = fetch(url) if "/article" in url else ""
        cands = [u for u, t in links(article, url) if re.search(r"/attachments/|\.pdf(\?|$)", u, re.I)] if article else [url]
        if not cands:
            cands = [url]
        book, note_text, created = None, "", ""
        tmp = Path(tempfile.mkdtemp())
        for i, u in enumerate(dict.fromkeys(cands)):
            try:
                b = fetch(u, binary=True)
            except RuntimeError as e:
                log("  skip", e)
                continue
            if not b.startswith(b"%PDF"):
                continue
            p = tmp / f"kpk{i}.pdf"
            p.write_bytes(b)
            info = pdf_info(p)
            log(f"  {u}: {info['pages']} pages")
            if info["pages"] >= 100 and (book is None or info["pages"] > book[1]["pages"]):
                book = (p, info, u)
            if "NOTIFICATION" in info["text"].upper():
                note_text += " " + info["text"]
        if not book:
            return self.kpk_failed(name, url, "no MRS PDF of 100+ pages found on the edition page")
        p, info, pdf_url = book
        note_text += " " + info["text"]
        notified = find_date(note_text) or find_date(re.sub(r"<[^>]+>", " ", article))
        date_note = ""
        if not notified:
            notified = info["created"] or dt.date.today().isoformat()
            date_note = "Notification date not found - this is the PDF issue date; confirm against the notification."
        num = re.search(r"No\.?\s*(MRS/[A-Z0-9/\-]+)", note_text)
        notification = "No." + num.group(1) if num else "number not read from the PDF"
        if self.dry:
            log(f"  dry run: would load {name} from {pdf_url}, notified {notified}")
            return
        try:
            msg = kpk_mrs.build(p, kpk_mrs.DEFAULT_HTML, name, notified, notification, pdf_url, date_note)
        except Exception as e:  # parse or validation failure
            return self.kpk_failed(name, pdf_url, str(e))
        self.state["kpk"].pop("failed", None)
        self.state["kpk"].update({"loaded": name, "loadedUrl": pdf_url, "loadedOn": dt.date.today().isoformat()})
        self.changes.append(f"KPK {name} loaded automatically: {msg}")

    def kpk_failed(self, name, url, why):
        log(f"KPK: {name} could not be loaded - {why}")
        if self.state["kpk"].get("failed") == name:
            return  # reported on an earlier day; keep retrying quietly
        self.state["kpk"]["failed"] = name
        self.issues.append((f"KPK {name} published but not loaded automatically",
                            f"The KPK Finance Department has published **{name}** ({url}).\n\n"
                            f"The daily rate watch could not load it: {why}\n\n"
                            "The KPK MRS tab still shows the previous edition. Load it by hand with "
                            "`tools/kpk_mrs.py <pdf> --edition ... --notified YYYY-MM-DD --notification ...`, "
                            "or adjust the parser if the PDF layout changed."))
        self.changes.append(f"KPK {name} found but not loaded ({why})")

    # ---- Punjab ----
    def punjab(self):
        st = self.state.setdefault("punjab", {"lahore": []})
        seen = {x["url"] for x in st["lahore"]}
        first_run = not seen
        reached = 0
        for page_url in PUNJAB_PAGES:
            try:
                page = fetch(page_url)
            except RuntimeError as e:
                log("Punjab:", e)
                if not reached and "timed out" in str(e):
                    break  # the whole host is not answering; do not wait on its other pages
                continue
            reached += 1
            for url, text in links(page, page_url):
                if not re.search(r"\.pdf(\?|$)", url, re.I):
                    continue
                if "lahore" not in (url + " " + text).lower():
                    continue
                if url in seen:
                    continue
                seen.add(url)
                kind = "Input rates" if "input" in page_url else "MRS"
                entry = {"url": url, "title": text or url.rsplit("/", 1)[-1], "kind": kind,
                         "page": page_url, "firstSeen": dt.date.today().isoformat()}
                st["lahore"].append(entry)
                log(f"Punjab: new Lahore PDF - {entry['title']} - {url}")
                if not first_run:
                    self.issues.append((f"Punjab {kind} (Lahore) published: {entry['title']}"[:120],
                                        f"A Lahore PDF not listed before is on {page_url}:\n\n{url}\n\n"
                                        "The dashboard has no Punjab parser yet, so its rates are not loaded. "
                                        "It is listed under Auto-watch on the KPK MRS tab."))
                self.changes.append(f"Punjab {kind} Lahore PDF recorded: {entry['title']}")
        if not reached:
            raise RuntimeError("Punjab Finance Department pages could not be reached")

    # ---- output ----
    def open_issues(self):
        tok, repo = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
        if not tok or not repo:
            for t, _ in self.issues:
                log("issue (not opened, no token):", t)
            return
        api = f"https://api.github.com/repos/{repo}/issues"
        hdr = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json", "User-Agent": "rate-watch"}
        req = urllib.request.Request(api + "?state=open&per_page=100", headers=hdr)
        with urllib.request.urlopen(req, timeout=60) as r:
            open_titles = {i["title"] for i in json.load(r)}
        for title, body in self.issues:
            if title in open_titles:
                continue
            data = json.dumps({"title": title, "body": body + "\n\n---\n_Opened by the daily rate watch (tools/rate_watch.py)._"}).encode()
            with urllib.request.urlopen(urllib.request.Request(api, data=data, headers=hdr, method="POST"), timeout=60) as r:
                log("opened issue:", json.load(r)["html_url"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    w = Watch(a.dry_run)
    warnings = []
    for name, fn in (("KPK", w.kpk), ("Punjab", w.punjab)):
        try:
            fn()
        except Exception as e:
            # KPK is what the dashboard loads, so only it fails the run; the Punjab
            # site does not answer GitHub's runners on some days, which is a warning
            (w.errors if name == "KPK" else warnings).append(f"{name}: {e}")
            log(f"{name}: ERROR {e}")
    if w.changes and not a.dry_run:
        w.state["lastChange"] = dt.date.today().isoformat()
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(w.state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (ROOT / ".rate-watch-msg").write_text("Rate watch: " + "; ".join(w.changes)[:3000] + "\n")
        w.open_issues()
    log("changes:", w.changes or "none")
    for m in warnings:
        log(f"::warning::{m}")
    if w.errors:
        sys.exit("unreachable: " + " | ".join(w.errors))


if __name__ == "__main__":
    main()
