"""NC Division of Parks & Recreation — NC Trails: elevation, published, and not landed (coverage audit
2026-10-01, batch p10_persist).

open_licence (unnamed), state work, not federal. NC OneMap's Terms page (Hub page item
`e60514c3b78542ef9902e3d7f7a671c1`, updated 2026-07-22) reads: "…committed to offering access to
current State geospatial information at no charge. By sharing their content, all partner
organizations understand …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
