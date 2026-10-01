"""Mohonk Preserve: warnings, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

Zones without dates. The dates are in a PDF nobody has parsed (@unvalidated whether they are
machine-readable). Skeptic additions (Measured 2026-10-01): the layer's fields are only
`Zone_Number`, `Zone_Name`, `Area_Acres` and `Perimeter_MIles`, so no restriction or date field
exists despite the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`MP_Deer_Management_with_Restrictions/FeatureServer/0`: 16 polygons, `dataLastEditDate` 2026-08-18, "
        "fields `Zone_Number`/`Zone_Name`/`Area_Acres` (attachments enabled). The season's dates sit in "
        "`wp-content/uploads/2026/09/HuntingRegulations2026.pdf` and the hunt maps "
        "`2025_DeerManagement_Main/D1/D2/D3.pdf`, linked from `/…/deer-management-program/` (`modified` "
        '2026-09-01). The alerts page\'s "Alerts" section carries a storm-hazard notice ("downed trees, ruts, '
        'and areas of standing water").',
    ),
    where=(
        "https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services/MP_Deer_Management_with_Restrictions/FeatureServer/0",
        "https://mohonkpreserve.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
