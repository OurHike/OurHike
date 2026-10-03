"""Mountain Club of Maryland: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mountain Club of Maryland: warnings, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

Seasonal and evergreen rather than live.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Same API: hunting-season posts 2022-10-28 ("It's the Season
for Orange") and 2023-09-23; bear-container policy post 2022-07-15

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://mcomd.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
