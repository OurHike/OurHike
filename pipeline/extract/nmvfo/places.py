"""New Mexico Volunteers for the Outdoors: places, drawn from usfs/'s resources, and the rest not landed
(decision 54, wave 1, read 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs `usfs_forest_boundaries` (Cibola 0303, Santa Fe 0310, Lincoln 0308) and `usfs_wilderness_areas` (Sandia"
        " Mountain, Pecos), registered 2026-10-03.",
        "Not landed: the City of Albuquerque's Open_Space/FeatureServer/0 (65 polygons), whose steward has no folder "
        "(wave 6), and the RGIS 'New Mexico State Parks / State Park boundaries' download (wave 2).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0",
        "https://coageo.cabq.gov/cabqgeo/rest/services/agis/Open_Space/FeatureServer/0",
    ),
    reason="partly drawn from usfs/'s resources (decision 34); the City of Albuquerque's and RGIS's layers are not landed yet",
)
