"""Washington RCO — State Trails Database: elevation, published, and not landed (coverage audit
2026-10-01, batch p10_persist).

Lidar_Hillshade item licenseInfo is empty, accessInformation "Washington Geological Survey, WA DNR,
USGS": none_stated. Low value either way: OurHike already reads 3DEP (`_shared`), and
`pipeline/ELEVATION_SOURCES.md` §8 declined state lidar portals on purpose ("fragmentation for no
accuracy gain"). Automated use of the Lidar Portal itself is refused by its robots.txt, so it would
need DNR's permission. Folder: `wa_dnr/` (name Reasoned).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/Lidar_Hillshade/MapServer` has layers `0` "
        '"Top Surface Hillshade (Default Sun Angle)" and `1` "Bare Earth Hillshade (Default Sun Angle)". '
        'copyrightText "Washington Geological Survey"; items `ab865c2741db4cf6a49c1577e1020632` and '
        "`9ec4890f40be4176b9aeaf34ad2e698b`. It is a rendering, not elevation values. "
        "`https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_Data/MapServer/6` "
        '"Elevation (feet)" is a raster layer whose description reads: "The DEM_30M layer is a raster dataset '
        "depicting surface elevation covering Washington State (and beyond). The data was derived by resampling"
        ' USGS 10-meter DEMS…", from scanned contour separates, so it is coarser than the 3DEP we load. The '
        "Washington Lidar Portal (`https://lidarportal.dnr.wa.gov/`) holds the lidar DEMs, but its robots.txt "
        "disallows `/arcgis/`, `/download` and `/query` (see Method notes). `site3/Public_Lidar` answers 499 "
        "Token Required. Tried: (1) RCO hosts `gis.rco.wa.gov` and `geo.rco.wa.gov` do not resolve (proxy "
        "CONNECT 502); the audit covered RCO's own AGOL services (162). WA DNR roots `gis.dnr.wa.gov/site1`, "
        "`/site2` and `/site3` were walked through their elevation-, lidar-, wildfire- and geology-shaped "
        'folders; `/arcgis/` answers 404. (2) AGOL "WA DNR lidar DEM" 16, "Washington State lidar bare earth '
        'DEM" 26; `owner:OpenData_wadnr` elevation 3, lidar 4, DEM 2, none a DEM. Hub "Washington lidar" 502 '
        "hits; the relevant ones are the Lidar Portal (a Document Link) and the hillshade above. (3) geo.wa.gov"
        " search API: lidar 10, elevation 50, hillshade 0. No statewide DEM is listed; the hits are bathymetry,"
        ' WRIA channel layers and "The Bare Earth Story Map". (4) The other land managers (USFS, NPS) are '
        'covered by 3DEP. (5) data.gov "Washington lidar DEM" 20, all NOAA coastal topobathy; Socrata '
        '"Washington lidar" 64, county flood depths. (6) `rco.wa.gov` is not a GIS host (audit).',
    ),
    where=(
        "https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/Lidar_Hillshade/MapServer",
        "https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_Data/MapServer/6",
        "https://lidarportal.dnr.wa.gov/",
        "https://gis.rco.wa.gov",
        "https://geo.rco.wa.gov",
        "https://geo.wa.gov",
        "https://data.gov",
        "https://rco.wa.gov",
        "https://trails-wa-rco.hub.arcgis.com/",
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
