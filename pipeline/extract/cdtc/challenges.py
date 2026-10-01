"""Continental Divide Trail Coalition: challenges, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page. `cdtcoalition.org/cdt-completers/`: honour-system completion reporting with a "
        'certificate, a CDT patch and a "3000 Miler" rocker. Section hikers get equal recognition.',
    ),
    where=("https://cdtcoalition.org/cdt-completers/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
