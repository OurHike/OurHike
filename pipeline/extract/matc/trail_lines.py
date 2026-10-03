"""Maine Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

Avenza is a `refuse` platform. The Grafton Loop Trail (MATC's half lies east of Route 26) has no
published MATC geometry; its page has only a Google Maps embed of the trailhead.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`centerline`, `side_trails`; club polygon in `trail_club_sections` ("Maine Appalachian Trail Club"). '
        "MATC's own geometry: Avenza only — 7 maps + 2 bundles at "
        "`https://www.avenzamaps.com/vendor/6011/maine-appalachian-trail-club-inc` (from "
        '`https://www.matc.org/digital-trail-maps/`). ArcGIS search for "Maine Appalachian Trail Club" returned'
        " 0 items.",
    ),
    where=(
        "https://www.avenzamaps.com/vendor/6011/maine-appalachian-trail-club-inc",
        "https://www.matc.org/digital-trail-maps/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
