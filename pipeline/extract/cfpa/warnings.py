"""Connecticut Forest & Park Association: warnings, read with closures (decision 53 phase B,
2026-10-03). closures.py's notice sources feed this type too: one upstream is one resource and one
raw table (decision 34), and dbt's decision 7 classifier splits each notice into closures or
warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Connecticut Forest & Park Association: warnings, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

The "CLEARED" items are reopenings and must not render as hazards.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Non-closure items in the same feed: "Nipmuck Trail Parallel to
Chaffeville Rd – Caution" (2025-05-06), "North Stonington – Difficult/Unblazed Trail Section"
(2025-01-06), "Ragged Mountain Preserve, Storm Damage CLEARED" (2026-07-17).

Its `where`: https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services
https://ctwoodlands.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
