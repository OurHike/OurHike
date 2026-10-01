"""DEC publishes no elevation product. Profiles are USGS 3DEP (_shared/usgs/) along the lines trail_lines.py loads."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "all 10 folders and 15 root services on DEC's on-prem ArcGIS Server: the only rasters are the "
        "NYNHP/ADK_Hemlock and NYNHP/BIO_RASTER habitat-model ImageServers",
        "all 716 service names in DEC's ArcGIS Online org: none matches elev, dem, lidar, contour, terrain, hillshade or slope",
        "DEC's listings on data.ny.gov and data.gis.ny.gov",
        "DEC's day-hike pages: stated climbs in prose, such as 'climbs 944 feet to the summit', a cross-check "
        "on a computed climb rather than an elevation product",
    ),
    where=(
        "https://gisservices.dec.ny.gov/arcgis/rest/services",
        "https://data.gis.ny.gov/",
        "https://dec.ny.gov/things-to-do/hiking/adirondack-day-hikes",
    ),
)
