"""AMC Connecticut Chapter: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c1_at_clubs_north).

The map is from 2014.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Club polygon "Appalachian Mountain Club - Connecticut Chapter". Own: a map PDF only, '
        '`https://ct-amc.org/wp-content/uploads/2019/10/2014Appalachian-trail-map2.pdf`. ArcGIS search for "AMC'
        ' Connecticut" returned 0.',
    ),
    where=("https://ct-amc.org/wp-content/uploads/2019/10/2014Appalachian-trail-map2.pdf",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
