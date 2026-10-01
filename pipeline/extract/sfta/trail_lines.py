"""Santa Fe Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

1:100k designated line (finding 2)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/SAFE_NHT/FeatureServer/0`: 96 lines (`SAFE_SantaFeNHT100k_ln`), edited 2025-01-22, "
        '`NHTPUBLICUSESEGMENT` null on all 96. `nps_trails`: 0. Own: "Trail Maps" '
        '`https://santafetrail.org/trail-maps/` and an "Interactive Trail Map" (search index; format unknown)',
    ),
    where=(
        "https://santafetrail.org/trail-maps/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/SAFE_NHT/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
