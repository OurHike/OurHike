"""New York–New Jersey Trail Conference: elevation, nothing published (coverage audit 2026-10-01, batch
b2_nynjtc).

USGS 3DEP (`_shared/`) covers this. The Hike Finder GPX `<ele>` values are a raster sampled along a
drawn line (`nynjtc_hike_finder` notes, #1451 — The Hike Finder GPX files are drawn routes, not
recorded walks — and a climb threshold built on that mistake is understating gain by 15%). They are
not …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`hasZ:false` and `hasM:false` on `Long_Path_2023/0`, `NYNJTC_HighlandsTrail2021sections/0` and "
        "`Long_Path_Shawangunk_Ridge_Trail/0`. The 76 AGOL items include no Image Service, elevation or DEM "
        "type: they are Feature Service 27, Web Map 18, Form 17, Web Mapping Application 7, Feature Collection "
        "3, StoryMap Theme 2, StoryMap 1, and Map Package 1 (LoHudAIS invasives). The 312 WP pages contain no "
        "elevation product.",
    ),
    where=(
        "https://services7.arcgis.com/G1WTEJ6UVRUTvh9C/arcgis/rest/services",
        "https://nynjtc.org/",
    ),
)
