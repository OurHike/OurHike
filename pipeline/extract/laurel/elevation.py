"""Laurel Highlands Hiking Trail (PA DCNR): elevation, published as statewide lidar, not landed.

No raster lands as data (decision 35, pipeline/ELT.md "No raster lands as data"): a DEM, an image
service or a hillshade is read in place or not at all, and USGS 3DEP (_shared/usgs/) is the
elevation source. Not re-read for decision 54.

3DEP already covers PA. Load only if it is shown to differ.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'PA statewide lidar via DCNR\'s Topographic & Geologic Survey "Digital Base Maps" '
        "(`dcnr.pa.gov/agencies/dcnr/conservation/geology/digital-base-maps`, listed in `org_channels.json`) "
        "and PASDA.",
    ),
    where=("https://dcnr.pa.gov/agencies/dcnr/conservation/geology/digital-base-maps",),
    reason="raster, not landed: decision 35 lands no raster as data, and 3DEP (_shared/usgs/) is the elevation source",
)
