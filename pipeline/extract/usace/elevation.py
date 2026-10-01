"""US Army Corps of Engineers: elevation, published, and not landed (coverage audit 2026-10-01, batch
p08_persist).

Licence: "While the United States Army Corps of Engineers (hereinafter referred to USACE) has made a
reasonable effort to insure the accuracy of the maps and associated data, it should be explicitly
noted that USACE makes no warranty…". Class: open_licence, public domain as a federal work, except …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
