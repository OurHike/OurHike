"""The Arizona Trail Association's bear boxes for caching water: 22 boxes with their fix, NOBO mile, closest
FarOut waypoint and land manager, from the PDF its water sources page links.

Decision 54, wave 4: read live on 2026-10-04 (robots.txt first on aztrail.org and on the association's media
bucket, lib/user_agent.py's agent) and registered in sources.json, where the row carries the count, the
validators, the measured key, the terms and what holds it back.

- `ata_water_cache_boxes`: 22 boxes, keyed on the FarOut waypoint.

A BOX IS A CACHE, NEVER A WATER SOURCE: "Bear boxes are for caching water only", and what is in one is what
a hiker or a trail angel left (aztrail.org/explore/water-sources/). The association's terms ask written
permission for information published online, so the row's licence is unresolved and nothing ships.

NOT HERE, AND THE LEAD'S: the coverage audit's ATA water and point data on ArcGIS, read 2026-10-01 at
https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services: layer 0, AZT Water Source Locations (312
points, a free-text `Type`), layer 1, Points (3,041), and layer 2, Trailheads (106). They are ArcGIS layers,
wave 1's reader, and have no sources.json row yet.
"""

from datetime import date

from extract._contract import SameAs
from extract._pdf_points import pdf_points

CLAIMS = ("ata_water_cache_boxes",)
RESOURCES = [pdf_points(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="ata_water_cache_boxes",
        copy=(
            "https://aztrailmedia.s3.us-west-1.amazonaws.com/wp-content/uploads/2024/08/water-cache-box-locations-08152024.xlsx",
        ),
        confirmed=date(2026, 10, 4),
        checked=(
            "aztrail.org's media library lists both on 2024-08-15 (wp-json/wp/v2/media, read 2026-10-04): the "
            "XLSX, 'Water Cache Box Locations_08152024', and the PDF printed from it, whose own /Title is "
            "'water-cache-box-locations-08152024.xlsx'. The water sources page links the PDF only. The XLSX was "
            "not downloaded; the PDF's title is what shows they are one table.",
        ),
    ),
)
