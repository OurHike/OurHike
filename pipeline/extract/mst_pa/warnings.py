"""Mid State Trail Association (PA): warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mid State Trail Association (PA): warnings, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

The original's "recorded under closures" contradicts decision 7 (`obstructs_trail`; everything else,
and anything unreviewed, goes to warnings). One page feeds both marts, as it does for waldo and
uvta. The region pages are old. The section pages are current.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same section "Alerts" carry hazards that close nothing,
e.g. `/134-section-1` (updated 2026-07-01): "Blazes have been obscured on some parts of the old
route through Hewitt. (6/10)". The region update pages (`/index.php/tioga-region-updates`,
`/everett-region-updates`) carry "Watch for unbridged streams", "can be steep and treacherous near
unbridged stream" and construction-detour notices, dated 2009–2014.

Its `where`: https://mapservices.pasda.psu.edu/server/rest/services
https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services https://hike-mst.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
