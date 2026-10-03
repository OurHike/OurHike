"""USDA Forest Service: elevation, published as regional bare-earth DEMs, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source.

Regional and partial: by its own description, R9's DEM covers Huron-Manistee and not the White
Mountain or Green Mountain NFs. It is lidar that 3DEP mostly also holds. Not worth loading first,
since 3DEP covers NFS land. The 403 folders and the empty `Terrain_Region` listings are UNKNOWN, not
empty.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `imagery.geoplatform.gov/iipp/rest/services/Terrain` still lists exactly four "
        "ImageServers, `BareEarthDEM_multiYear_USFS_R3_Southwest_multiRes_Public`, `..._R5_PacificSW_...`, "
        "`..._R9_Eastern_...` and `..._R10_Alaska_...`",
        "First pass: none of EDW's 145 services is a DEM. Still true (Measured).",
        "Skeptic, Measured 2026-10-01: `https://imagery.geoplatform.gov/iipp/rest/services/Terrain` is the "
        "imagery platform the USFS org's image items point to. It holds four ImageServers, all "
        "`esriImageServiceDataTypeElevation` and F32: "
        "`BareEarthDEM_multiYear_USFS_R3_Southwest_multiRes_Public`, `..._R5_PacificSW_...`, "
        "`..._R9_Eastern_...` and `..._R10_Alaska_...`. The R9 one's copyright text reads \"provided by the U.S."
        " Forest Service Eastern Region (R9) and are served by the U.S. Forest Service Geospatial Technology & "
        "…",
    ),
    where=(
        "https://imagery.geoplatform.gov/iipp/rest/services/Terrain",
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://apps.fs.usda.gov/fsgisx04",
    ),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
