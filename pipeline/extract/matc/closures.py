"""Maine Appalachian Trail Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Dormant and irregular. The newest closure-shaped post is 2023-09-14, and closures share the category
with news, so a dlt resource needs a title/keyword rule to pick them out (@unvalidated: no rule has
been tried). The A.T. is otherwise covered only through `atc_trail_updates` (LOADED), and the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WP REST `https://www.matc.org/wp-json/wp/v2/posts?categories=2` (Announcements, 45 posts; 87 posts "
        'site-wide), RSS `https://www.matc.org/feed/`. Closure-shaped posts in it: "Side Trail Closure on '
        'Barren Mountain" (2021-06-22, `/side-trail-closure-on-barren-mountain/`: "the A.T. side trail leading '
        'to the Barren Slide has been closed" for nesting peregrines), "June 16, 2020 Update on A.T. Closures '
        'and Conditions" (2020-06-16, also category ATC), and "Work on Stratton Brook Pond Road" (2023-09-14, '
        'category Hazard: "some closure of the road and parking areas may occur … park at the Rt. 27 parking …',
    ),
    where=(
        "https://www.matc.org/wp-json/wp/v2/posts?categories=2",
        "https://www.matc.org/feed/",
        "https://matc.org/",
        "https://www.matc.org/trailreport/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
