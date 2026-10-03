"""NY State Parks / NYS GIS Clearinghouse: elevation, published as NYS ITS's 1 m DEM, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source.

Licence, Latest DEM item: "The State of New York, acting through the New York State Office of
Information Technology Services, makes no representations or warranties, express or implied, with
respect to the use of or reliance on the Data provided. The User accepts the Data provided "as
is"…". Class: none_stated (a disclaimer). A project item (`1acc8f51…`, Columbia County's copy) adds:
"NYS ITS GIS Program Office: Use Constraints - None… Acknowledgement of New York Office of
Information Technology Services would be appreciated". `copyrightText`: "NYS ITS Geospatial
Services, United State Geological Survey (USGS), and FEMA". Basis: decision 22 covers OPRHP's own
items. This one is NYSGIS_GPO's, so it rests on 21(a). Folder: `_shared/` (NYS GIS Program Office
elevation), not `oprhp`. 3DEP is already the loaded elevation source. Load this only if a measured
profile shows the 1 m mosaic beats 3DEP.

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `Latest_DEM/ImageServer` is still an F32, 1-band, 1 m ImageServer; "
        "copyrightText 'NYS ITS Geospatial Services, United State Geological Survey (USGS), and FEMA'",
        '`https://elevation.its.ny.gov/arcgis/rest/services/Latest_DEM/ImageServer`: "Mosaic dataset of high '
        "resolution (1 meter) Bare Earth Digital Elevation Model's (DEM's). Newest and hightest resolution data"
        ' is stored on top. This mosaic is a combination of County, State, and Federal Collections". F32, 1 m '
        "pixels, statewide extent (EPSG:26918), image export enabled. The root lists 64 services: about 55 "
        "project ImageServers plus `DEM_Extents`, `Dem_Indexes`, `LAS_Indexes`, "
        "`In_Progress_LiDAR_Collections_in_NYS` and `NYS_Statewide_Hillshade`. Clearinghouse: "
        "`data.gis.ny.gov/api/search/v1/collections/all/items?q=DEM` returns 7 items, 4 of them owned by "
        "`NYSGIS_GPO`: Latest DEM (`75759cd0…`), DEM Projects (`988e7f37…`), NYS DEM Indexes and NYS Statewide "
        'Hillshade. data.ny.gov (Socrata) also lists "High Resolution Digital Elevation Models (DEMs)". OPRHP: '
        "AGOL `owner:NYS.Parks.Admin` × elevation, contour, DEM, lidar, hillshade, terrain or topographic "
        "returns 0. Other OPRHP roots: `parks.ny.gov/arcgis/rest/services` and `/server/rest/services` answer "
        "403 (the website, not an ArcGIS server, Reasoned); `gis.`, `maps.` and `gisservices.parks.ny.gov` do "
        "not resolve. Tried: 1, 2, 3, 5 (data.gov returns coastal NOAA and USGS records only).",
    ),
    where=(
        "https://elevation.its.ny.gov/arcgis/rest/services/Latest_DEM/ImageServer",
        "https://data.gis.ny.gov/api/search/v1/collections/all/items?q=DEM",
        "https://data.ny.gov",
        "https://parks.ny.gov/arcgis/rest/services",
        "https://gisservices.parks.ny.gov",
        "https://data.gov",
        "https://data.gis.ny.gov/",
        "https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
