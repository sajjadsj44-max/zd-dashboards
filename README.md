# zd-dashboards

Static, self-contained HTML dashboards published live via GitHub Pages.

## One-time activation (2 settings, ~1 minute)

The files are all in place, but GitHub Pages has never been switched on for this
repo, and the repo is currently **private**. Two settings in the GitHub web UI
turn the live links on. Neither can be done from the API, so they have to be
clicked once by the repo owner.

**1. Make the repo public** — so friends can open the links without a GitHub account.
`Settings` → `General` → scroll to `Danger Zone` → `Change repository visibility`
→ `Make public`.

> Skip this only if you have GitHub Pro/Team. On a private repo Pages still works,
> but the site stays private too: viewers must be signed in to GitHub *and* be
> invited as collaborators. For "send a link to a friend", public is the one you want.
> Note the dashboard file becomes publicly readable, so don't commit anything
> confidential to this repo.

**2. Turn on Pages** —
`Settings` → `Pages` → under `Build and deployment`, set
`Source` = **Deploy from a branch**, `Branch` = **main**, folder = **/ (root)** → `Save`.

A minute or two later the links below go live. They never change after that.

## Live links

| Page | URL |
|---|---|
| Dashboard index | https://sajjadsj44-max.github.io/zd-dashboards/ |
| Zameen Developments | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |

Public and read-only — anyone with the URL opens them in any browser, phone or
desktop, no login and nothing to install. Viewers cannot edit anything.

## How the "live" part works

The site is served straight from the `main` branch, so updating a dashboard is:

1. Replace the dashboard file in this repo with the newer version.
2. Commit and push to `main`.
3. ~1–2 minutes later the same URL serves the new version for everybody.

The URL never changes, so links you already shared stay valid across every update.
If someone still sees an old copy, GitHub Pages caches HTML for up to 10 minutes —
a hard refresh (Ctrl + F5, or Cmd + Shift + R) clears it immediately.

`.github/workflows/deploy-pages.yml` additionally force-mirrors `main` onto a
`gh-pages` branch on every push, so if Pages is ever pointed at `gh-pages`
instead of `main`, that branch is already current. Either source works.

## Adding or updating a dashboard

- **Update an existing one:** overwrite its `index.html` (e.g. `zameen-developments/index.html`).
  Keep the filename `index.html` so the short folder URL keeps working.
- **Add a new one:** create `<dashboard-name>/index.html`, then add a card for it in the
  root `index.html`.

Each dashboard is one self-contained HTML file. External libraries (Chart.js,
PapaParse) load from the jsDelivr CDN at runtime, so viewers need an internet
connection.

## Repo layout

```
index.html                          landing page listing all dashboards
zameen-developments/index.html      Zameen Developments dashboard
.github/workflows/deploy-pages.yml  mirrors main onto gh-pages on every push
.nojekyll                           serve files as-is (no Jekyll processing)
```
