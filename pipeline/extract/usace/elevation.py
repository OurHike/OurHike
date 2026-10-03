"""US Army Corps of Engineers: elevation, published as lake contours and a coastal DEM, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Contours are vectors, so decision 35 does not cover them, but no mart reads them
and they are background-map material: decision 54's wave 1 registers none, and loading them is the
maintainer's call (decided 2026-10-03). The Louisville District's contours are 1,725 lines at 17
lake projects, none of them on a trail.

Licence: "While the United States Army Corps of Engineers (hereinafter referred to USACE) has made a
reasonable effort to insure the accuracy of the maps and associated data, it should be explicitly
noted that USACE makes no warranty…". Class: open_licence, public domain as a federal work, except …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `LRL_PublicInfo_Contour_G/FeatureServer/9` 'Contour_L' 1,725 polylines, hasZ "
        "true, dataLastEditDate 2026-09-23",
        "Louisville District: "
        "`services2.arcgis.com/Gxjpth7iW1Xoiixo/arcgis/rest/services/LRL_PublicInfo_Contour_G/FeatureServer` "
        "(item `2ac63e5c…`, owner `AGOL_BSM`). Layer 9 `Contour_L`: 1,725 lines, edited 2026-09-23, at 17 lake "
        'projects in KY, IN and OH. Buckhorn has 1,283 of them, at 5 ft from "KY Topo 5ft Contours"; the others'
        " have 4–51 each, from project lidar flown 2014–2024. Layers 8 and 10 are summer-pool lines (53) and "
        'areas (18). The item snippet: "summer pool and elevations to allow the public to visualize water '
        'levels at boat ramps". Coastal: …',
    ),
    where=(
        "https://services2.arcgis.com/Gxjpth7iW1Xoiixo/arcgis/rest/services/LRL_PublicInfo_Contour_G/FeatureServer",
        "https://arcgis.usacegis.com/arcgis/rest/services/JALBTCX/JALBTCX_Products_BareEarth_1mGrid/ImageServer",
    ),
    reason=(
        "raster and vector contours, not landed: decision 35 lands no raster, and decision 54's wave 1 "
        "registers no contours, which are the maintainer's call; checked gives the measured counts"
    ),
)
