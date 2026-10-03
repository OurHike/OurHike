"""Catamount Trail Association: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Catamount Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page, and a NOTE paragraph rather than a structured field. One live hazard banner across 33
sections. Low volume, but it is the club's own hazard notice, which is what this mart holds.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASFPR_WM_NOCACHE/MapServer/3,
Vermont ANR's trail layer: 1,625 trails, every Status 'EX', so it carries no closure (a trail_lines
layer for decision 54's first wave).

Its `checked` (confirmed 2026-10-01):
`https://catamounttrail.org/ski-the-trail/ct-section-list/section-31-jay-pass-to-canadian-border/`
opens with "NOTE: There is logging actively taking place on Section 31 south of the Jay Country
Store. If you encounter active logging please keep your distance…" (page modified 2025-09-17).
Section 6's page reads "Be alert for temporary detours due to scheduled logging." Plus the static
"Safety On The Trail" and "Safety In The Backcountry" pages and one ad hoc post, "Warning: Increased
Avalanche Danger In New England Backcountry".

Its `where`:
https://catamounttrail.org/ski-the-trail/ct-section-list/section-31-jay-pass-to-canadian-border/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
