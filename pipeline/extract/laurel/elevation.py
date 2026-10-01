"""Laurel Highlands Hiking Trail (PA DCNR): elevation, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

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
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
