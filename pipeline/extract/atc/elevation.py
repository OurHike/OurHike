"""ATC's Z-enabled A.T. centerline, `ATX_Ratings/FeatureServer/9` ("Centerline Current"), read with its Z.

What ships as elevation is still USGS 3DEP (_shared/usgs/), sampled along
the shipping centerline, `ANST_Centerline/FeatureServer/0`, which has no Z
(hasZ false). This layer is the club's own elevation along the same trail:
679 lines with a Z, in metres (every vertex of the 2 features read whole
carried one, and 6 sampled vertices sit a median of 1.93 m from 3DEP,
measured 2026-10-03; sources.json's `elevation_unit_comment`), so it can
check or calibrate the 3DEP profile.
Nothing reads it yet; how it calibrates is phase C's to design, and its
`reaches_hikers` is false until then.

Read as Esri JSON (`return_z` on its row), because `f=geojson` drops the Z.
Two things a model reading it must know, both measured 2026-10-03: 18 of its
697 rows (OBJECTID 681 to 698) have no geometry and repeat segment 25-01-03,
and the layer is editable anonymously (its row's `notes`), so a Z here can
move without ATC moving it.

The other three centerline layers in the same service and the older `Map`
service's centerline are copies, noted below, not landed (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("atc_atx_centerline",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="atc_atx_centerline",
        copy=(
            "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/ATX_Ratings/FeatureServer/1",
            "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/ATX_Ratings/FeatureServer/5",
            "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/ATX_Ratings/FeatureServer/10",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "layers 1 'Current - Centerline', 5 'Desired - Centerline' and 10 'Centerline Desired' sit in the same "
            "ATX Ratings service as layer 9 and are symbolized differently: one outStatistics query on each of the "
            "four answered count 697, max OBJECTID 698, sum of Shape__Length 4,586,382.04 m and sum of tot_miles "
            "2,256.98, the same on all four",
            "the first feature (Katahdin, Baxter Peak to Katahdin Stream Campground) has the same 620 vertices, "
            "Z from 330.50 to 1,601.58, on all four",
            "the same 25 fields and the same dataLastEditDate, 2025-10-01",
        ),
    ),
    SameAs(
        original="atc_atx_centerline",
        copy=("https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/Map/FeatureServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "'Centerline', hasZ true, the same 25 fields, dataLastEditDate 2025-07-24: an earlier state of layer 9, "
            "and the newest copy is the one extracted, as with CPW's COTREX copies",
            "count 679 and max OBJECTID 680 against layer 9's 697 and 698, with the same sum of Shape__Length, "
            "4,586,382.04 m: layer 9 is this layer plus its 18 rows with no geometry",
            "the first feature's 620 vertices and their Z, 330.50 to 1,601.58, are the same as layer 9's",
        ),
    ),
)
