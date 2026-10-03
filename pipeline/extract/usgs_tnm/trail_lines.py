"""USGS — The National Map: trail lines, published, and held out of decision 54's wave 1.

`USGSTrails/MapServer/0` is the National Digital Trails aggregate, built from other publishers' lines:
grouped by `sourceoriginator` on 2026-10-03, the U.S. Forest Service supplies 149,256 of its 607,202
rows, Colorado Parks and Wildlife 50,883, the National Park Service 50,199, BLM 31,226, MassGIS 19,777,
NJDEP 16,850, CT DEEP 16,664 and NH GRANIT 16,254, among 62 originators. 230,681 of them (38%) come from
the three federal agencies whose own trail layers usfs/, nps/ and blm/ already extract; whether those
rows are copies of the agencies' layers is not measured, and under the one-extraction rule (decision 34)
it decides how much of the layer is a copy. At 304 pages of 2,000 it would be the largest single read
the monthly lane gains.

So it waits on two things, the lead's call on 2026-10-03: a measured monthly time budget (the first
monthly run with wave 1, pipeline/ELT.md, "Volume, and what it does to each clock"), and a
copy-versus-independent check against `usfs_trails`, whether its Forest Service rows are the Forest
Service's rows or USGS's own edit of them. Its rows from originators no folder extracts would be a
gap-filler then, deduplicated in dbt.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1), robots.txt first (partnerships.nationalmap.gov answered "
        "403, which RFC 9309 reads as no rules): `USGSTrails/MapServer/0` (TrailsSegment) holds 607,202 "
        "polylines (returnCountOnly), maxRecordCount 2,000, no editingInfo, max(objectid) 2,842,987; "
        "max(loaddate) 2026-09-14, max(sourceeditdate) 2026-06-23, publisheddate null on every row. Extent in "
        "EPSG:4326: lat -14.37 to 68.46, lon -177.40 to 145.73 (dbt/macros/lands_outside_its_region.sql's "
        "us_and_territories box). One group-by on sourceoriginator: 62 originators, U.S. Forest Service "
        "149,256, Colorado Parks and Wildlife 50,883, National Park Service 50,199, Virginia DCR 41,179, BLM "
        "31,226, MassGIS 19,777, Florida DEP 18,950, Vermont ANR 16,991, NJDEP 16,850, CT DEEP 16,664, NH "
        "GRANIT 16,254.",
        "`https://partnerships.nationalmap.gov/arcgis/rest/services/USGSTrails/MapServer/0` (TrailsSegment): "
        '607,202 polylines, maxRecordCount 2,000, copyright "USGS The National Map: National Transportation '
        'Dataset; U.S. Census Bureau – TIGER/Line; U.S. Forest Service. v20260611.3". Fields include '
        "`nationaltraildesignation`, `primarytrailmaintainer`, `hikerpedestrian`, `sourceoriginator`, "
        "`sourcefeatureid`, `seasonopen`. Also "
        "`carto.nationalmap.gov/arcgis/rest/services/transportation/MapServer/37` (Trails), 591,392.",
    ),
    where=(
        "https://partnerships.nationalmap.gov/arcgis/rest/services/USGSTrails/MapServer/0",
        "https://carto.nationalmap.gov/arcgis/rest/services/transportation/MapServer/37",
    ),
    reason=(
        "held out of wave 1 (the lead, 2026-10-03): built largely from agencies other folders extract (38% "
        "of its rows from USFS, NPS and BLM), and the largest monthly read; waits on a measured monthly time "
        "budget and a copy-versus-independent check against usfs_trails"
    ),
)
