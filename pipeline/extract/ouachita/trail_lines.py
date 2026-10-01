"""Friends of the Ouachita Trail: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c6_regional_3).

The catalogue says 25 features, from 2026-09-17. Today's query gives 21, and the match is by name
only. About 35 of the 223 miles are not on National Forest. The January 2026 alert PDF says some
cross "privately-owned area managed for timber production" and Central Arkansas Water land (Reasoned
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "On `EDW_TrailNFSPublish_01/MapServer/0`, `trail_name` 'OUACHITA NRT' has 20 segments / 187.455 mi, and"
        " 'OUACHITA NRT SPUR' has 1 / 0.59 mi. Own: none. `/hiker-info/maps-and-trail-guide/` sends hikers to "
        "`omhikers.club` (a separate hiking club), `ouachitamaps.com`, FarOut (paid) and a named individual's "
        "guidebook (sold).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0",
        "https://ouachitamaps.com",
        "https://friendsoftheouachita.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
