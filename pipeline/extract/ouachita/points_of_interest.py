"""Friends of the Ouachita Trail: points of interest, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

Skeptic: the loaded `usfs_rec_sites` (`EDW_RecInfraRecreationSites_02/MapServer/0`) holds 0 sites
with "SHELTER" in the name under Ouachita NF (`managing_org LIKE '0809%'`), and 37 trailheads, one
named "OUACHITA TRAIL-TALIMENA STATE PARK". So the shelters really are missing from what we load,
and …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/hiker-info/trail-shelters/` (HTML): 23 shelters by mile marker, 12 with coordinates in degrees and "
        'decimal minutes, e.g. "ROCK GARDEN – MM 9.4 N34 46.387 / W94 51.799". There is also the Shelter Guide '
        "PDF `/wp-content/uploads/2025/05/Ouachita-Trail-Shelters-5-7-25.pdf` (216,300 bytes). Water: "
        '`/wp-content/uploads/2025/05/OT_Water_Sources_rev_2019-03-01.pdf`, "OUACHITA TRAIL NAVIGATION POINTS, '
        'Compiled by a named individual". 7 pages, created 2019-03-02, about 252 mile-marked rows, 98 with UTM '
        'fixes and 17 with lat/lon. It warns "Even a good source may be dry under drought conditions".',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0",
        "https://friendsoftheouachita.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
