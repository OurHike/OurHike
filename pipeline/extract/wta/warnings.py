"""Washington Trails Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("The same Hiker Headlines posts (fire, bridge work).",),
    where=(
        "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",
        "https://wta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
