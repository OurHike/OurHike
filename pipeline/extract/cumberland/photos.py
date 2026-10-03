"""Cumberland Trail / Tennessee State Parks: photos, nothing published (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Site imagery is CrowdRiff user-generated content (`media--crowdriff`) plus agency photos with no open licence stated.",
    ),
    where=("https://tnstateparks.com/",),
)
