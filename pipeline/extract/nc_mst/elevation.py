"""NC Mountains-to-Sea Trail (state-published layer): elevation, published as NC OneMap's DEM, not
landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. The same DEM as nc_dpr/elevation.py's note.

Licence: open_licence. NC OneMap terms page (item `e60514c3…`): "all partner organizations
understand this free and unrestricted use policy… Written release agreements to authorize use of the
geospatial data, web services, and applications found on the NC OneMap website are not required and
will not be issued". It asks for a citation. It is a state work, not federal. The item's own
`licenseInfo` points to `https://www.nconemap.gov/pages/terms`. Folder: `_shared/` elevation input,
not `nc-mst/`. @unvalidated: whether it adds anything over 3DEP for NC. The state's lidar is
delivered through the same federal programmes; comparing tile dates and resolution for one mountain
county would settle it. Its item says "Data should not be downloaded using the map on the dataset's
item page" and points to Direct Data Downloads.

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `Elevation/DEM03/ImageServer` is still an esriImageServiceDataTypeElevation "
        "ImageServer, F32, 1 band, 3.125 ft pixels",
        "NC OneMap `https://services.nconemap.gov/secure/rest/services/Elevation/DEM03/ImageServer` (item "
        '`d0416b6d…`, owner `nconemap`, "NC Digital Elevation Model"): F32, 1 band, 3.125 ft pixels, extent '
        'covers the state, item modified 2026-04-29. Description: "A digital elevation model (DEM) for North '
        "Carolina using county mosaic DEM's created by the NC Floodplain Mapping Program and processed by NC "
        'Department of Public Safety - Division of Emergency Management." Its `Elevation` folder holds 13 '
        "ImageServers: DEM03, hillshade, slope, aspect, shaded relief, raster contours at 1, 2, 4, 20 and 100 "
        "ft, and DEM20ft_Hillshade.",
        "Tried:",
        "NC OneMap root `services.nconemap.gov/secure/rest/services`: 8 folders, `Elevation` walked. "
        "`/arcgis/rest/services` and `/rest/services` answer 404.",
        "AGOL `North Carolina elevation DEM nconemap` 20, `NC OneMap elevation` 33, `North Carolina lidar DEM` "
        "49. Hub `www.nconemap.gov` search `elevation` 33.",
        "NC OneMap is the clearinghouse.",
        "Not applicable.",
        "data.gov: USGS coastal DEMs only. Socrata: none.",
        "DPR site, audit.",
    ),
    where=(
        "https://services.nconemap.gov/secure/rest/services/Elevation/DEM03/ImageServer",
        "https://www.nconemap.gov/pages/terms",
        "https://data.gov",
        "https://trails.nc.gov/",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
