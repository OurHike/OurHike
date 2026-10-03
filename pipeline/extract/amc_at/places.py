"""Appalachian Mountain Club (A.T. sections): places, drawn from amc/'s resources (decision 54, wave 1,
read 2026-10-03).

The WordPress destinations and the shuttle page are not ArcGIS and wait for waves 3 and 5.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via amc `amc_properties_and_landscapes` (9 polygons) and `amc_chapter_boundaries` (11 polygons, with Web_URL), "
        "registered 2026-10-03.",
        "Not landed yet: WP REST `destinations` (30, with a `location` taxonomy; wave 3) and the White Mountain Hiker "
        "Shuttle page `https://www.outdoors.org/shuttle/`, which lists trailhead stops (wave 5).",
    ),
    where=(
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services",
        "https://www.outdoors.org/shuttle/",
    ),
    reason="drawn from amc/'s resources, extracted once there (decision 34); the WordPress and page sources are not landed yet",
)
