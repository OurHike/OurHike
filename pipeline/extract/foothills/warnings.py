"""Foothills Trail Conservancy: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Foothills Trail Conservancy: warnings, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same `/trail-conditions/` page warns that fire-burned
steps and bridges expose "nails and rebar" and that dead trees ("widow makers") may fall. `/safety/`
is a static page on hunting season, bears, waterfalls and lightning.

Its `where`: https://foothillstrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
