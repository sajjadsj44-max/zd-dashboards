# zd-dashboards

Static, self-contained HTML dashboards published live via GitHub Pages.

## Live links

| Page | Netlify (short link to share) | GitHub Pages |
|---|---|---|
| Dashboard index | https://zddashboard.netlify.app/ | https://sajjadsj44-max.github.io/zd-dashboards/ |
| Zameen Developments | https://zddashboard.netlify.app/zameen-developments/ | https://sajjadsj44-max.github.io/zd-dashboards/zameen-developments/ |

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
Then `Site configuration` → `Change site name` → `zddashboard`.

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
netlify.toml                        Netlify publish settings and cache headers
zameen-developments/index.html      Zameen Developments dashboard
.github/workflows/deploy-pages.yml  deploy to Pages + mirror main onto gh-pages
.nojekyll                           serve files as-is (no Jekyll processing)
```
