"""Arizona Trail Association: elevation, carried on two of its own layers that other types register.

The Arizona Trail's elevation is the Z on its trail line, layer 3 of ATA's
`Arizona_National_Scenic_Trail_Feature_Layers_view`, and the `Elevation`
field on its waypoints, layer 1. Both are in FEET (measured 2026-10-03
against 3DEP, below), so a model that read either as metres would put the
trail 3.28 times too high. Layer 3 is a trail line and layer 1 a set of
points, so trail_lines.py and points_of_interest.py register them, layer 3
with `return_z` on its row; one upstream is one resource (decision 34), and
this file becomes `SHARES` once a sibling resource reads one of them
(decided 2026-10-03 for decision 54's wave 1).

The layers' copyrightText names ATA's GIS director and an aztrail.org e-mail
address, which this file does not copy (a person, CLAUDE.md and ELT.md rule 8).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "layer 3, 'Arizona National Scenic Trail Polyline' (read 2026-10-03): 44 polylines, hasZ and hasM true, "
        "dataLastEditDate 2026-09-04; passage 01's 12,855 vertices carry Z from 5,505.1 to 9,095.2. 4 of them read "
        "against 3DEP through EPQS sit a median of 1.38 m away read as feet and 5,011 m away read as metres, so the "
        "Z is in feet. Its description says the line was digitized 'using Statewide aerial imagery, GPS data, LiDar "
        "and 10M USGS DEM'",
        "layer 1, 'Arizona National Scenic Trail Points' (read 2026-10-03): 3,041 points, an integer `Elevation` "
        "field in feet (3 points, a median of 0.10 m from 3DEP read as feet). It is 0 on 1 row and null on 2, which "
        "mean unknown, never sea level",
        "the service's `_for_OSM` view (item 96a2b446702f4e2a91c92d6882614215) serves layers 1, 3 and 4 again: a "
        "copy, for whichever file registers them to record as SAME_AS",
        "the coverage audit (2026-10-01, batch c10_nst_rest) also found a Web Experience, 'Arizona National Scenic "
        "Trail Elevation Profile' (dd1becd86ed24b43b957532f8546b15d); not re-read",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/3",
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/1",
        "https://aztrail.org/",
    ),
    reason="carried on a layer another type's file registers: becomes SHARES once that sibling resource exists",
)
