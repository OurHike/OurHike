"""Santa Fe Trail Association: trail lines, drawn from nps/'s resources (decision 34), registered on
2026-10-03.

1:100k designated line (finding 2)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_santa_fe_nht` (96 lines) registered in "
        "sources.json and extracted in nps/trail_lines.py.",
        "`NPSAGOL/SAFE_NHT/FeatureServer/0`: 96 lines (`SAFE_SantaFeNHT100k_ln`), edited 2025-01-22, "
        '`NHTPUBLICUSESEGMENT` null on all 96. `nps_trails`: 0. Own: "Trail Maps" '
        '`https://santafetrail.org/trail-maps/` and an "Interactive Trail Map" (search index; format '
        "unknown)",
    ),
    where=(
        "https://santafetrail.org/trail-maps/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/SAFE_NHT/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
