"""Bureau of Land Management: elevation, published, and not landed (coverage audit 2026-10-01, batch
p09_persist).

Licence: the service's copyrightText is "Bureau of Land Management, Oregon State Office". The MMPK
licenseInfo reads "This data is provided by Bureau of Land Management (BLM) 'as is' and might
contain errors or omissions". data.gov gives `http://www.usa.gov/publicdomain/label/1.0/`. So
open_licence: public domain, a federal work (17 U.S.C. 105). Value: BLM labels its national contours
"TNM Derived", so 3DEP stays the source (`_shared/usgs`). The OR/WA contours' origin is not stated
(@unvalidated; their layer description, or BLM OR's GIS staff, would settle it). The recommendation
is not to load them (Reasoned).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Walked 13 REST roots on gis.blm.gov: `arcgis` plus `orarcgis`, `coarcgis`, `nvarcgis`, `azarcgis`, "
        "`utarcgis`, `idarcgis`, `mtarcgis`, `wyarcgis`, `caarcgis`, `akarcgis`, `nmarcgis` and `esarcgis`. "
        "That is 774 services in all; `arcgis2`, `arcgis_image`, `image`, `server` and `gis` answer 404. "
        "Elevation-shaped finds: "
        '`https://gis.blm.gov/orarcgis/rest/services/Basemaps/BLM_ORWA_Cached_Basemap/MapServer/35` "100 Foot '
        'Index Contours", 669,399 polylines, and `…/MapServer/36` "40 Foot Index", 3,405,394 polylines. Both '
        "have the field `CONTOUR`, capabilities Map, Query and Data, maxRecordCount 25,000, and an OR+WA "
        'extent; "The cache was last updated July 15, 2026". No DEM or hillshade service exists on any root (CA'
        " and UT `Imagery` hold Master Title Plat and historic-photo image services). (2) AGOL: the 21 state "
        'mobile map packages (owner `blm_arcgis_hub_natl`; e.g. "BLM Natl Colorado MMPK" '
        '`c9c86fae28df4a1bb49c486e0df5766d`, 786,286,664 B, "Last updated 20260914") list "BLM National '
        'Contours (TNM Derived)" among their contents. They are binary packages, not services. The one-off '
        'rasters "BLM ES GLO ROTW … Web Elevation Layer" (`af59bde9…`, Mount St. Helens) and WY '
        '`TIN_toRaster_Clip_m_ProjectAGO` are project rasters. (5) data.gov "BLM Natl 3DEP Areas" and "BLM Natl'
        ' 3DEP LiDAR Priorities" are coverage polygons. (6) GeoPDF map indexes: '
        "`utarcgis/.../Imagery/BLM_UT_GeoPDF_MapService/MapServer/0` (61 maps) and "
        "`mtarcgis/.../GeoPDF/BLM_MT_GeoPDF_Index_MapService_107/MapServer/0` (16 maps).",
    ),
    where=(
        "https://gis.blm.gov/orarcgis/rest/services/Basemaps/BLM_ORWA_Cached_Basemap/MapServer/35",
        "https://data.gov",
        "https://gis.blm.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
