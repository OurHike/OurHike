// The site's two pages about OurHike's data, linked from the app (Q24 of
// #1805 — dlt → dbt re-platform as one go/no-go change: the maintainer chose
// "All three as drawn", 2026-10-15). Before this the app had no way to them,
// and on the site the only one was the footer, at 94% of the way down a
// phone's home page (q24_frames.html, measured 2026-10-15).
//
// ON OURHIKE.ORG, NOT DOCS.OURHIKE.ORG, ON PURPOSE. Whether the docs host
// serves the data pages yet is decided at each deploy (pages.yml, "Ask
// whether docs.ourhike.org serves the data docs"), and an app built today
// outlives that answer. ourhike.org/data/ is right either way: it serves the
// pages itself until the move, and after it serves a page at each old
// address that sends the visitor on (.github/scripts/docs_host.py).
//
// Opened in a new tab like every other link out of the app, so the map is
// still there when the hiker comes back. Neither page is the app, so neither
// can hand the app a session (lib/safeLink.ts's concern).

/** "How the data is built": site/src/pages/data/how/index.astro, the plain
 *  page in front of dbt's own docs. */
export const DATA_BUILT_URL = 'https://ourhike.org/data/how/'

/** "Data quality": site/src/pages/data/quality/index.astro. */
export const DATA_QUALITY_URL = 'https://ourhike.org/data/quality/'
