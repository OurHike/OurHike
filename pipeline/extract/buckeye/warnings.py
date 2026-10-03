"""Buckeye Trail Association: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Buckeye Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restricted. Every row needs decision 7's `obstructs_trail` classifier.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same blocks carry non-closure notices: "Aggressive Dogs"
(Sinking Spring, 2024-10-22), "Potential Flooding" (Caesar Creek, 2025-02-26), "Challenging
Conditions" (Old Man's Cave, 2024-07-30), "Hiking Guidance in East Fork State Park based on Lake
Levels" (2025-05-13).

Its `where`: https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services
https://buckeyetrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
