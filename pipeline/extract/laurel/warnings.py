"""Laurel Highlands Hiking Trail (PA DCNR): warnings, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Hunting season is in scope. This fragment is statewide and already past its end date (spot check
confirms 2025-08-25 → 2025-12-07). Skeptic adds, for a `pa-dcnr/` folder rather than the LHHT (which
is state park, not state forest): `gis.dcnr.pa.gov/dcnrbsc/rest/services/Forestry/` serves …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same AEM endpoint with `alertPath=…/dcnr/content-fragments/sunday-hunting`: "Sunday Hunting in '
        'State Parks", dated 2025-08-25 → 2025-12-07 (the 2025–26 season).',
    ),
    where=(
        "https://gis.dcnr.pa.gov/dcnrbsc/rest/services/Forestry/",
        "https://dcnr.pa.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
