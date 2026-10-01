"""NYC Parks: elevation, published, and not landed (coverage audit 2026-10-01, batch q01_persist).

Not DPR's data. It is OTI's (a sibling city agency) and the State's. Licence: City datasets fall
under Local Law 11 of 2012 (`nyc_licence`); the Socrata `license` field is empty → open_licence (NYC
Open Data Law; not a federal work). NYS ITS `copyrightText` "NYS ITS Geospatial Services" →
attribution_only. Folder: `_shared/` (an `nyc_oti` or `nys_its` entry). Low priority: 3DEP covers
NYC and the 2010 lidar is older than 3DEP's NYC collections (R).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'City (OTI) on `data.cityofnewyork.us`: `dpc8-z3jc` "1 foot Digital Elevation Model (DEM)" (href; "A '
        "bare-earth, hydro-flattened, digital-elevation surface model derived from 2010 Light Detection and "
        "Ranging (LiDAR) data\"; updated 2024-10-30; zip on the portal's own asset store); `7kuu-zah7` the "
        'integer raster (2024-10-30); `9uxf-ng6q` "NYC Planimetric Database: Elevation Points" (dataset, '
        "updated 2025-12-10) and its map `szwg-xci6`. NYS ITS "
        "`https://elevation.its.ny.gov/arcgis/rest/services/NYC_TopoBathymetric_2017_1_meter/ImageServer` (F32,"
        ' 1 m; "bare earth digital elevation model… derived from Green and NIR LiDAR"); also '
        "`USGS_NYC2014_1_meter`. DPR itself: AGOL org `services3.arcgis.com/xJHn8F2NTtwCMFtX` (NYCParksGIS), 75"
        " services, 0 with elev/contour/topo/DEM/lidar/terrain in the name; `owner:NYCParksGIS` elevation "
        "search 0. Tried: (1) DPR AGOL and the City portal, i.e. the parent's host. (2) AGOL as above. (3) NYS "
        "ITS elevation server (63 services). (4) Not applicable (DPR is the manager). (5) Socrata "
        "`domains=data.cityofnewyork.us q=elevation`: 33 (DEM, elevation points, DCP's building-elevation "
        'tables); data.gov "New York City DEM" 3 (NOAA coastal DEMs). (6) No DPR files.',
    ),
    where=(
        "https://elevation.its.ny.gov/arcgis/rest/services/NYC_TopoBathymetric_2017_1_meter/ImageServer",
        "https://data.cityofnewyork.us/d/dpc8-z3jc",
        "https://data.cityofnewyork.us/d/7kuu-zah7",
        "https://data.cityofnewyork.us/d/9uxf-ng6q",
        "https://data.cityofnewyork.us/d/szwg-xci6",
        "https://services3.arcgis.com/xJHn8F2NTtwCMFtX/arcgis/rest/services",
        "https://data.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
