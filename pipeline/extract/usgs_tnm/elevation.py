"""USGS — The National Map: elevation, drawn from another folder's resource (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Not a sources.json key: `usgs_3dhp` is the hydrography `watched_only` row. The `sources` mart will
need an entry for 3DEP.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "3DEP 1/3 arc-second tiles indexed by `pipeline/fetch_elevation.py` "
        "(`prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/…`, HEAD only). EPQS "
        "(`epqs.nationalmap.gov/v1/json`) in `fetch_trail_water.py`.",
    ),
    where=(
        "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/",
        "https://epqs.nationalmap.gov/v1/json",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
