# zd-dashboards

Static, self-contained HTML dashboards published live via GitHub Pages.

## Live links

| Page | URL |
|---|---|
| Dashboard index | https://sajjadsj44-max.github.io/zd-dashboards/ |
| Zameen Developments | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |

Links are public and read-only — anyone with the URL can open them in any browser,
on phone or desktop, with no login and nothing to install.

## How the "live" part works

`.github/workflows/deploy-pages.yml` redeploys the whole repo to GitHub Pages on every
push to `main`. So:

1. Replace the dashboard file in this repo with a newer version.
2. Commit and push to `main`.
3. ~1–2 minutes later the same URL serves the new version for everybody.

The URL never changes, so shared links stay valid across every update.
If someone still sees an old copy, GitHub Pages caches HTML for up to 10 minutes —
a hard refresh (Ctrl + F5, or Cmd + Shift + R) clears it immediately.

## Adding or updating a dashboard

- **Update an existing one:** overwrite its `index.html` (e.g. `zameen-developments/index.html`).
  Keep the filename as `index.html` so the short folder URL keeps working.
- **Add a new one:** create `<dashboard-name>/index.html`, then add a card for it in the
  root `index.html`.

Each dashboard is a single self-contained HTML file. External libraries (Chart.js,
PapaParse) load from the jsDelivr CDN at runtime, so an internet connection is needed
to view them.

## Repo layout

```
index.html                          landing page listing all dashboards
zameen-developments/index.html      Zameen Developments dashboard
.github/workflows/deploy-pages.yml  auto-deploy to GitHub Pages on push to main
.nojekyll                           serve files as-is (no Jekyll processing)
```
