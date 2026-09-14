#!/usr/bin/env python3
"""Prepare a dashboard for publication.

The published dashboard is a single self-contained HTML file, so anyone who can
view it can save it. That cannot be prevented. What this script does instead is
make an unattributed copy awkward to produce and easy to disprove:

  * authorship is stated in the markup, the metadata and the visible UI
  * ownership markers are repeated in places a quick edit will miss
  * the stylesheet and scripts are minified, so the saved file is unpleasant
    to read or modify

Usage:  tools/harden.py SOURCE.html OUTPUT.html [--no-minify]

The source file is deliberately not kept in this repository: publishing a clean,
readable copy alongside the hardened one would defeat the exercise.
"""

import argparse
import datetime
import hashlib
import pathlib
import re
import subprocess
import sys
import tempfile

OWNER = "Sajjad"
BRAND = "SAJ QSCOST"
CONTACT = "sajjadsj44@gmail.com"

# Tools are resolved from the environment so the script stays usable wherever
# node happens to be installed; missing tools downgrade to "no minification"
# rather than failing the build.
BIN_CANDIDATES = [
    pathlib.Path(__file__).resolve().parent.parent / "node_modules" / ".bin",
    pathlib.Path.home() / "node_modules" / ".bin",
]


def find_bin(name, extra_dirs=()):
    for d in list(extra_dirs) + BIN_CANDIDATES:
        p = pathlib.Path(d) / name
        if p.exists():
            return str(p)
    return None


def run_tool(cmd, text):
    """Run a minifier over `text` using temp files (large inputs, safe quoting)."""
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "in"
        out = pathlib.Path(td) / "out"
        src.write_text(text, encoding="utf-8")
        proc = subprocess.run(
            [c.format(inp=str(src), outp=str(out)) for c in cmd],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(proc.stderr.strip()[:800] or "minifier failed")
        return out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Block extraction
#
# Comments are stripped from the HTML only, never from inside <script> or
# <style>: a "<!--" inside a JS string is ordinary text, and removing it would
# corrupt the program. Both block types are therefore lifted out behind
# placeholders first and restored at the end.
# --------------------------------------------------------------------------

STYLE_RE = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S | re.I)
# Only inline scripts. A tag carrying src= has no body to minify.
SCRIPT_RE = re.compile(r"(<script(?![^>]*\bsrc=)[^>]*>)(.*?)(</script>)", re.S | re.I)


def extract(pattern, html, store, tag):
    def sub(m):
        store.append((m.group(1), m.group(2), m.group(3)))
        return f"\x00{tag}{len(store) - 1}\x00"
    return pattern.sub(sub, html)


def restore(html, store, tag, transform):
    for i, (open_tag, body, close_tag) in enumerate(store):
        html = html.replace(f"\x00{tag}{i}\x00", open_tag + transform(body) + close_tag)
    return html


def inject_metadata(html, year, build_id):
    """State authorship where a browser, a crawler and a reader each look."""
    meta = (
        f'<meta name="author" content="{OWNER}">\n'
        f'<meta name="copyright" content="© {year} {OWNER} — {BRAND}">\n'
        f'<meta name="application-name" content="{BRAND}">\n'
        f'<meta name="generator" content="{BRAND} build {build_id}">\n'
    )
    return html.replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">\n" + meta, 1)


def inject_credit(html, year, build_id):
    """A visible credit in the sidebar, plus markers a careless edit will miss."""
    css = (
        "\n.saj-credit{margin:14px 16px 18px;padding-top:12px;"
        "border-top:1px solid rgba(255,255,255,.10);line-height:1.45}"
        ".saj-credit b{display:block;font-size:10.5px;letter-spacing:1.1px;"
        "color:#8fb0d2;font-weight:700}"
        ".saj-credit span{display:block;font-size:9.5px;color:#7f9cbb;margin-top:2px}"
        ":root{--saj-owner:\"" + OWNER + "\";--saj-build:\"" + build_id + "\"}\n"
    )
    html = html.replace("</style>", css + "</style>", 1)

    credit = (
        f'<div class="saj-credit" data-owner="{OWNER}" data-brand="{BRAND}" '
        f'data-build="{build_id}">'
        f'<b>{BRAND}</b>'
        f'<span>Built by {OWNER}</span>'
        f'<span>© {year} — all rights reserved</span>'
        f'</div>\n'
    )
    return html.replace("</aside>", credit + "</aside>", 1)


def inject_runtime_marker(html, year, build_id):
    """Runtime markers. Kept as used string literals so a minifier cannot drop them."""
    js = (
        "\n/* ownership marker */\n"
        "var SAJ_BUILD=Object.freeze({owner:%r,brand:%r,contact:%r,year:%r,build:%r});\n"
        "try{document.documentElement.setAttribute('data-saj-build',SAJ_BUILD.build);"
        "document.documentElement.setAttribute('data-saj-owner',SAJ_BUILD.owner);"
        "console.info('%%c'+SAJ_BUILD.brand+' \\u2014 built by '+SAJ_BUILD.owner+"
        "' \\u00a9 '+SAJ_BUILD.year,'color:#2b7de9;font-weight:700');}catch(e){}\n"
    ) % (OWNER, BRAND, CONTACT, str(year), build_id)

    m = SCRIPT_RE.search(html)
    if not m:
        return html
    return html[:m.end(1)] + js + html[m.end(1):]


def banner(year, build_id, minified):
    return (
        "<!--\n"
        f"  {BRAND} — Zameen Developments dashboard\n"
        f"  Copyright (c) {year} {OWNER}. All rights reserved.\n"
        f"  Contact: {CONTACT}\n"
        f"  Build: {build_id}\n\n"
        "  This file and its layout, calculations and presentation are the work of\n"
        f"  {OWNER}. It is published for viewing. Redistributing it, or presenting it\n"
        "  or any derivative of it as another party's work, is not permitted.\n"
        f"  {'Sources are minified; this is not the authoring copy.' if minified else ''}\n"
        "-->\n"
    )


def main():
    ap = argparse.ArgumentParser(description="Harden a dashboard HTML file for publication.")
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--no-minify", action="store_true",
                    help="inject ownership markers but leave sources readable")
    ap.add_argument("--bin-dir", action="append", default=[],
                    help="extra directory to search for terser/cleancss")
    args = ap.parse_args()

    src_path = pathlib.Path(args.source)
    html = src_path.read_text(encoding="utf-8")
    original_len = len(html)

    year = datetime.date.today().year
    build_id = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]

    # Injection happens before minification so the added markup and code are
    # minified along with everything else, rather than standing out as the one
    # readable region in the file.
    html = inject_metadata(html, year, build_id)
    html = inject_credit(html, year, build_id)
    html = inject_runtime_marker(html, year, build_id)

    styles, scripts = [], []
    html = extract(STYLE_RE, html, styles, "S")
    html = extract(SCRIPT_RE, html, scripts, "J")

    html = re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.S)

    minified = False
    css_fn = js_fn = (lambda s: s)
    if not args.no_minify:
        terser = find_bin("terser", args.bin_dir)
        cleancss = find_bin("cleancss", args.bin_dir)
        if terser and cleancss:
            css_fn = lambda s: run_tool([cleancss, "-O2", "{inp}", "-o", "{outp}"], s)
            js_fn = lambda s: run_tool([terser, "{inp}", "-c", "-m", "-o", "{outp}"], s)
            minified = True
        else:
            missing = [n for n, b in (("terser", terser), ("cleancss", cleancss)) if not b]
            print(f"warning: {', '.join(missing)} not found - skipping minification",
                  file=sys.stderr)

    try:
        html = restore(html, styles, "S", css_fn)
        html = restore(html, scripts, "J", js_fn)
    except RuntimeError as exc:
        print(f"error: minification failed: {exc}", file=sys.stderr)
        return 1

    html = banner(year, build_id, minified) + html.lstrip()
    pathlib.Path(args.output).write_text(html, encoding="utf-8")

    pct = (1 - len(html) / original_len) * 100
    print(f"build {build_id}  minified={minified}  "
          f"{original_len:,} -> {len(html):,} bytes ({pct:.1f}% smaller)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
