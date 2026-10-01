"""Laurel Highlands Hiking Trail (PA DCNR): places, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/State_Parks/MapServer/9` (State Park Boundaries): "
        "125. State Forest boundaries at `BOF/State_Forests/MapServer/4`.",
    ),
    where=("https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/State_Parks/MapServer/9",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
