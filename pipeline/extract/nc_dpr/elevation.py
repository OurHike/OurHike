"""NC Division of Parks & Recreation — NC Trails: elevation, published as NC OneMap's DEM, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source.

open_licence (unnamed), state work, not federal. NC OneMap's Terms page (Hub page item
`e60514c3b78542ef9902e3d7f7a671c1`, updated 2026-07-22) reads: "…committed to offering access to
current State geospatial information at no charge. By sharing their content, all partner
organizations understand …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `Elevation/DEM03/ImageServer` is still an esriImageServiceDataTypeElevation "
        "ImageServer, F32, 1 band, 3.125 ft pixels, capabilities "
        "'Catalog,Mensuration,Download,Image,Metadata'",
        "`https://services.nconemap.gov/secure/rest/services/Elevation/DEM03/ImageServer` (item "
        '`d0416b6d7b994575b2b60ce7491e02c6`, "NC Digital Elevation Model", owner `nconemap`, modified '
        "2026-04-29): a 3.125 ft cell, F32, `serviceDataType` esriImageServiceDataTypeElevation. Capabilities "
        'are "Catalog,Mensuration,Download,Image,Metadata"; values run from -308.7 to 6,683.0 ft. The '
        "description says it is built from \"county mosaic DEM's created by the NC Floodplain Mapping Program "
        'and processed by NC Department of Public Safety - Division of Emergency Management", and that "Data '
        "should not be downloaded …",
    ),
    where=(
        "https://services.nconemap.gov/secure/rest/services/Elevation/DEM03/ImageServer",
        "https://trails.nc.gov",
        "https://trails.nc.gov/",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
