"""COTREX (Colorado Parks and Wildlife): suggested hikes, refused by the COTREX application's terms (decision
54 wave 5, section K, 2026-10-04).

trails.colorado.gov/featured-routes lists 20 featured routes, each its name, distance, difficulty and park in its
card. The COTREX application's Terms of Service forbid using, reposting or copying its Content without a separate
written agreement and using its location data to augment another data set (quoted in `terms`), so nothing past
the page and the terms was read; the route forward is CPW's written permission. Its robots.txt also disallows
every URL with a query string, and 12 of the 20 route links carry one. CPW's ArcGIS layers are another matter,
read as public GIS (cotrex/trail_lines.py; the app's terms govern the app, not those REST layers).

The note this replaces read, whole:

Colorado Parks & Wildlife — COTREX: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Under the COTREX terms this is page-only until CPW says otherwise.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: `trails.colorado.gov/featured-routes` (8
`/routes/<id>` links on the page).

Its `where`: https://trails.colorado.gov/featured-routes https://trails.colorado.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://trails.colorado.gov/featured-routes (HTTP 200, 2026-10-04): 20 `a.result-list-item--itinerary` cards, each a label, a distance ('5¼mi', '877ft'), a difficulty icon and a park",
        "https://trails.colorado.gov/terms (HTTP 200, 2026-10-04): 'Restrictions on Use', quoted in `terms`",
        "robots.txt (2026-10-04): `Disallow: /*?` for every agent",
    ),
    where=(
        "https://trails.colorado.gov/featured-routes",
        "https://trails.colorado.gov/terms",
    ),
    terms="'By accessing and using the COTREX application, you may not: Use, repost, copy, distribute or publish any Content unless you have been given permission by Colorado Parks and Wildlife in a separate written agreement; Use geographic location data to create or augment any other data set; Access or search or attempt to access or search the COTREX application using any means other than the currently available interfaces that are provided by Colorado Parks and Wildlife as part of the COTREX application'",
    reason="refused: the COTREX application's terms forbid copying its Content without a written agreement",
)
