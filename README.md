# zd-dashboards

Static, self-contained HTML dashboards published live via GitHub Pages.

## Live links

| Page | URL |
|---|---|
| Dashboard index | https://sajjadsj44-max.github.io/zd-dashboards/ |
| Zameen Developments | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |

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

## How publishing is wired

Pages `Source` is set to **GitHub Actions**, so
`.github/workflows/deploy-pages.yml` does the publishing on every push to `main`:

- **`deploy`** packages the repo and deploys it to Pages.
- **`mirror`** force-pushes `main` onto a `gh-pages` branch, so switching
  `Source` to *Deploy from a branch* (`main` or `gh-pages`, `/ (root)`) would
  also serve the current site without editing the workflow.

Note for future changes: do not add `actions/configure-pages` with
`enablement: true`. The workflow `GITHUB_TOKEN` cannot create a Pages site
(`Resource not accessible by integration`) and it is not needed — the site
already exists.

## Adding a new dashboard

Create `<dashboard-name>/index.html`, then add a card for it in the root
`index.html`. Keep the filename `index.html` so the short folder URL works.

Each dashboard is one self-contained HTML file. External libraries (Chart.js,
PapaParse) load from the jsDelivr CDN at runtime, so viewers need an internet
connection.

## Repo layout

```
index.html                          landing page listing all dashboards
zameen-developments/index.html      Zameen Developments dashboard
.github/workflows/deploy-pages.yml  deploy to Pages + mirror main onto gh-pages
.nojekyll                           serve files as-is (no Jekyll processing)
```
