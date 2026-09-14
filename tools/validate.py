#!/usr/bin/env python3
"""Pre-publish checks for the dashboards site.

A single-file dashboard has no build step and no tests, so nothing stands
between a bad export and the URL people have already been given. These are the
cheap checks worth running before a deploy: that the files exist, that the
markup parses, that internal links resolve, that the published page has not
quietly doubled in size, and that the two protections which are easy to lose in
a rebuild - the CDN integrity digests and the site-wide headers - are still in
place.

Usage:  tools/validate.py [--root .]
Exits non-zero on the first category of failure, listing every problem found.
"""

import argparse
import pathlib
import re
import sys
import tomllib
from html.parser import HTMLParser

# A published dashboard is ~700 KB today, most of it embedded logos. The cap is
# a tripwire for an export that balloons, not a target - raise it deliberately.
MAX_DASHBOARD_BYTES = 1_000_000

REQUIRED = ["index.html", ".nojekyll", "netlify.toml"]

# Headers that must reach every URL, including the bare "/" the rewrite serves.
REQUIRED_HEADERS = [
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Cache-Control",
]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class Checker(HTMLParser):
    """Parses the markup and collects the bits the checks below care about."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.unbalanced = []
        self.unclosed = []
        self.links = []
        self.remote_scripts = []
        self.has_title = False
        self.has_charset = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.has_title = True
        if tag == "meta" and "charset" in a:
            self.has_charset = True
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script" and a.get("src", "").startswith("http"):
            self.remote_scripts.append((a["src"], a.get("integrity"), a.get("crossorigin")))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag not in self.stack:
            self.unbalanced.append(tag)
            return
        # Unwind to the matching open tag. Anything skipped on the way was
        # opened and never closed - report it rather than silently discarding
        # it, which would let an unclosed <main> slip through unnoticed.
        while self.stack:
            popped = self.stack.pop()
            if popped == tag:
                break
            self.unclosed.append(popped)


def check_html(path, root, problems):
    rel = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="replace")

    c = Checker()
    c.feed(text)

    if c.unbalanced:
        problems.append(f"{rel}: stray closing tag(s): {', '.join(sorted(set(c.unbalanced))[:5])}")
    dangling = c.unclosed + c.stack
    if dangling:
        problems.append(f"{rel}: unclosed tag(s): {', '.join(dict.fromkeys(dangling))[:120]}")
    if not c.has_title:
        problems.append(f"{rel}: no <title>")
    if not c.has_charset:
        problems.append(f"{rel}: no <meta charset>")

    # Every remote script must be pinned to a digest. A version in the URL only
    # pins which package was asked for, not which bytes come back.
    for src, integrity, crossorigin in c.remote_scripts:
        if not integrity:
            problems.append(f"{rel}: <script src=\"{src}\"> has no integrity attribute")
        elif not crossorigin:
            problems.append(f"{rel}: <script src=\"{src}\"> has integrity but no crossorigin "
                            f"(the browser will refuse it)")

    # Scripts built in JS bypass the markup check above, so look for the bare
    # jsDelivr URLs the dashboard assigns to a script element at runtime.
    for m in re.finditer(r'["\'](https://cdn\.jsdelivr\.net/[^"\']+\.js)["\']', text):
        if m.group(1) not in [s for s, _, _ in c.remote_scripts]:
            window = text[max(0, m.start() - 400):m.start() + 400]
            if ".integrity" not in window:
                problems.append(f"{rel}: {m.group(1)} is loaded from JS without setting .integrity")

    for href in c.links:
        if re.match(r"^(https?:|mailto:|tel:|#|data:)", href):
            continue
        target = (path.parent / href.split("?")[0].split("#")[0]).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            problems.append(f"{rel}: link \"{href}\" does not resolve to a file")


def check_netlify(root, problems):
    path = root / "netlify.toml"
    try:
        conf = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        problems.append(f"netlify.toml: does not parse ({exc})")
        return

    catch_all = [h for h in conf.get("headers", []) if h.get("for") == "/*"]
    if not catch_all:
        problems.append("netlify.toml: no headers rule for \"/*\" - the rewritten site root "
                        "would be served with no headers")
        return

    values = {}
    for h in catch_all:
        values.update(h.get("values", {}))
    for name in REQUIRED_HEADERS:
        if name not in values:
            problems.append(f"netlify.toml: \"/*\" does not set {name}")

    # The rewrite is what makes the root serve a dashboard; if it loses its
    # target the short link 404s while every other URL keeps working.
    for r in conf.get("redirects", []):
        if r.get("from") == "/":
            target = (root / r.get("to", "").lstrip("/")).resolve()
            if not target.exists():
                problems.append(f"netlify.toml: root rewrite points at {r.get('to')}, "
                                f"which does not exist")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve()

    problems = []

    for name in REQUIRED:
        if not (root / name).exists():
            problems.append(f"missing required file: {name}")

    pages = sorted(p for p in root.glob("*/index.html")
                   if not p.relative_to(root).parts[0].startswith((".", "node_modules")))
    if not pages:
        problems.append("no <dashboard>/index.html found - the site would publish with no dashboards")

    for page in pages:
        size = page.stat().st_size
        if size > MAX_DASHBOARD_BYTES:
            problems.append(f"{page.relative_to(root)}: {size:,} bytes exceeds the "
                            f"{MAX_DASHBOARD_BYTES:,} byte budget")

    for page in [root / "index.html", *pages]:
        if page.exists():
            check_html(page, root, problems)

    if (root / "netlify.toml").exists():
        check_netlify(root, problems)

    if problems:
        print(f"validate: {len(problems)} problem(s) found\n", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    checked = ", ".join(str(p.relative_to(root)) for p in pages)
    print(f"validate: OK - index.html, netlify.toml, {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
