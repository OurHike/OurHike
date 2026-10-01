"""AMC Delaware Valley Chapter: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Dormant: one post, 2023. Lehigh Gap is in `kta`'s A.T. section, not AMC-DV's, so a row from here has
to be deduplicated against KTA and ATC in dbt. ATC's own "George W. Outerbridge Shelter Yearly Bear
Warning" covers the same area.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WP REST post "Bear Safety", `https://amcdv.org/activities/bear-safety/` (2023-07-05; categories '
        'activities, conservation, state-forests, state-parks, trail-work): "The current hot spot seems to be '
        "around Lehigh Gap, where there have been several bear sighting on or near the A.T. over the past "
        'several weeks", with PA Game Commission / BearWise flyers. Readable through `/wp-json/wp/v2/posts`. '
        "`/leadership/pennsylvania-state-game-lands-special-use-permit-requirements/` covers group-permit "
        "procedure, not hunting-season notices.",
    ),
    where=(
        "https://amcdv.org/activities/bear-safety/",
        "https://amcdv.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
