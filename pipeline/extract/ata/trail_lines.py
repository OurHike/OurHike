"""Arizona Trail Association: the Arizona National Scenic Trail's own lines, from ATA's ArcGIS Online
organization.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `ata_arizona_trail`: Arizona National Scenic Trail, the trail's 44 passages (ATA). 44 lines, keyed on `GlobalID`.
- `ata_mountain_bike_passages`: Arizona Trail passages for mountain bikes (ATA). 50 lines, keyed on `GlobalID`.

Layer 3 is the trail itself, which no loaded row carried before: azgeo_arizona_trail is layer 5 of the
same service, the connector trails, so a hiker had the connectors and not the trail they connect to
(coverage audit, 2026-10-01). Layer 3 is Z-enabled, so its row sets `return_z` and its geometry lands
[x, y, z]; not_available.toml [ata.elevation] will SHARES this resource. Not landed: `ATA_Road_Connections` (63 lines of
road connections, by its name, last edited 2024-05-01), and the per-passage GPX on aztrailmedia's S3
bucket, a file wave 2's reader takes. The `_view_for_OSM` service is a second view of the same hosted
layer (SAME_AS below).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "ata_arizona_trail",
    "ata_mountain_bike_passages",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="ata_arizona_trail",
        copy=(
            "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view_for_OSM/FeatureServer/3",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "A second view of the same hosted layer: all 44 GlobalIDs equal layer 3's, the same statistics "
            "(count 44, max(OBJECTID) 1,012, sum(Shape_Leng) 12.4218) and dataLastEditDate 2026-09-04; it "
            "exposes two more columns, ID and Calc_Lengt (compared 2026-10-03)",
        ),
    ),
    SameAs(
        original="ata_mountain_bike_passages",
        copy=(
            "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view_for_OSM/FeatureServer/4",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "A second view of the same hosted layer: all 50 GlobalIDs equal layer 4's, the same 9 fields, "
            "statistics (count 50, max(OBJECTID) 267) and dataLastEditDate 2026-09-04 (compared 2026-10-03)",
        ),
    ),
)
