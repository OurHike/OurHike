"""NH GRANIT (University of New Hampshire): elevation, published as lidar DEMs, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Not re-read for decision 54.

Very likely the same lidar projects 3DEP serves (Reasoned). No reason to add it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/Topical/CV_LiDAR_DigitalElevation/MapServer` (Digital Elevation); image tile index "
        "`Topical/WF_NHGeodataImageDownloadTileIndex`.",
    ),
    where=("https://granit.unh.edu/",),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
