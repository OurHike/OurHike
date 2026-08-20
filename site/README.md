# site/ — ourhike.org

The marketing and organisational site at the apex. [WEBSITE.md](../WEBSITE.md)
is the plan; #116 tracks the build. The app at `/app/` is `client/` and is not
built from here.

```
npm ci
npm run dev        # local preview at localhost:4321
npm run build      # emits dist/, which pages.yml assembles to the site root
```

What lives where:

- `src/pages/` — one `.astro` file per page. Home, Get the app, About,
  Support the trail today; Explore (Phase 4) and For clubs / Get involved
  (Phase 6) join per WEBSITE.md §9, and the nav only ever links pages that
  exist.
- `src/styles/site.css` — the site's stylesheet. Design tokens are NOT copied
  here: `src/layouts/Base.astro` imports
  `client/src/design-system/tokens/colors.css`, so the client's copy stays
  the one copy (WEBSITE.md §7's "decide before there are three", decided).
- `public/` — passed through the build untouched: the live status page
  (`pages.yml` substitutes its bucket URL at assembly), the privacy policy,
  and the self-hosted fonts (`public/fonts/LICENSES.md` for provenance).
- `CNAME` — outside the Astro tree on purpose; the repo-settings tests read
  it at this path and the workflow copies the file verbatim (#733).

Deploys with the app: a `v*` tag runs `.github/workflows/pages.yml`, which
builds `client/`, builds this, assembles both into `_site/` and publishes to
the `gh-pages` branch. Nothing here deploys on its own.
