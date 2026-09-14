# zd-dashboards

Static, self-contained HTML dashboards published live on Netlify and GitHub Pages.

## Live links

| Page | Netlify (short link to share) | GitHub Pages |
|---|---|---|
| Zameen Developments | https://zd-dashboard.netlify.app/ | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |
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

- **`validate`** runs `tools/validate.py` and fails the run before anything is
  published if it finds a problem.
- **`deploy`** packages the repo and deploys it to Pages. Runs only if
  `validate` passed.
- **`mirror`** force-pushes `main` onto a `gh-pages` branch, so switching
  `Source` to *Deploy from a branch* (`main` or `gh-pages`, `/ (root)`) would
  also serve the current site without editing the workflow. Runs only if
  `deploy` succeeded, so the fallback branch never gets a commit the live site
  rejected.

Each job requests only the permissions it needs: `deploy` gets Pages access and
no repo write, and `mirror` is the only job that can push a branch.

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

## Checks before publishing

`tools/validate.py` runs in CI before every deploy, and can be run locally at
any time:

```sh
python3 tools/validate.py
```

It fails the deploy if a page does not parse, a link on the landing page does
not resolve, a published dashboard blows past its size budget, a CDN script has
lost its integrity digest, or `netlify.toml` stops setting the site-wide
headers. Those last two are the easy ones to lose in a rebuild, which is why
they are checked rather than just documented.

## Headers and CDN pinning

`netlify.toml` sets its headers for `/*`, not `/*.html`. This matters: the link
that actually gets shared is the bare site root, and the rewrite serves the
dashboard there, so `/` never matches a `*.html` rule. Keep the rule at `/*` or
the most-visited URL on the site goes out with no headers at all.

Alongside the cache headers it sends a CSP, `X-Frame-Options: SAMEORIGIN` (the
dashboard states its authorship in the page; none of that survives being framed
inside someone else's site), `X-Content-Type-Options`, `Referrer-Policy` and a
`Permissions-Policy`.

The three jsDelivr libraries carry SRI digests, so the browser refuses anything
that is not the exact bytes they were computed from — a pinned version in a URL
only pins which package was requested, not what comes back. `tools/harden.py`
injects them, so a rebuild keeps them; the digest table lives at the top of that
file with the command for recomputing after a version bump.

Note that Chart.js is loaded from `dist/chart.umd.js`, not `dist/chart.umd.min.js`.
The `.min.js` file does not exist in the published package — asking jsDelivr for
it makes jsDelivr minify on the fly and serve a file that exists nowhere
upstream, which no digest can be computed against. `chart.umd.js` is the
minified UMD build the package actually ships.

These headers come from Netlify. GitHub Pages serves the same files but does not
read `netlify.toml` and cannot set response headers, so the Pages mirror has the
SRI pinning but not the CSP or the framing protection. Share the Netlify link.

## Adding a new dashboard

Create `<dashboard-name>/index.html`, then add a card for it in the root
`index.html`. Keep the filename `index.html` so the short folder URL works.

Each dashboard is one self-contained HTML file. External libraries (Chart.js,
PapaParse) load from the jsDelivr CDN at runtime, so viewers need an internet
connection.

## Repo layout

```
index.html                          landing page listing all dashboards
netlify.toml                        Netlify publish settings, cache + security headers
zameen-developments/index.html      Zameen Developments dashboard
tools/harden.py                     build a publishable dashboard from the authoring copy
tools/validate.py                   pre-publish checks, run in CI before every deploy
.github/workflows/deploy-pages.yml  validate, deploy to Pages, mirror main onto gh-pages
.nojekyll                           serve files as-is (no Jekyll processing)
```
