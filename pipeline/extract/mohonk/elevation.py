"""Mohonk Preserve: elevation, nothing published (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

USGS 3DEP (`_shared/`).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The 24 services hold trails, boundary, deer zones, peregrine table, Hub events and Survey123 forms. "
        "None is elevation. A 76-item AGOL org search found none either.",
    ),
    where=("https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services",),
)
