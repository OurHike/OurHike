"""USDA Forest Service: elevation, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Regional and partial: by its own description, R9's DEM covers Huron-Manistee and not the White
Mountain or Green Mountain NFs. It is lidar that 3DEP mostly also holds. Not worth loading first,
since 3DEP covers NFS land. The 403 folders and the empty `Terrain_Region` listings are UNKNOWN, not
empty.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
