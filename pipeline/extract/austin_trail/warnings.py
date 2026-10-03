"""The Trail Foundation (Austin): warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

The Trail Foundation (Austin): warnings, nothing published (coverage audit 2026-10-01, batch
p08_persist).

Licence: TTC is none_stated. The ATXFloods response carries no terms, and I did not read the site's
terms page. Note: low-water crossings are roads, so they would belong to closures, not to this row.
The City's Lady Bird Lake algae notices are web pages on `austintexas.gov`, not GIS; I did not open
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): TTC's hazard-shaped layers all date from a 2020 planning
study, each with one generic description: `Conflict_Points` 28 points (every row "Pinch Point"),
`Lighting_Issues_points` 6 ("Sources of Glare") and `Lighting_Issues_lines` 52,
`Trail_Conditions_Issues` 11 lines ("Landscape Issues"), and `Narrow_Width` 134. All were last
edited 2020-10-14. `Condition_Assessment_V6` ("TTC_Condition_Assessment", the "2024 Butler Trail
Fall Hazard Assessment", edited 2026-09-28) refuses queries: "This operation is not supported".
City: `api.atxfloods.com/api/closures` is the API behind `atxfloods.com` …

Its `where`: https://api.atxfloods.com/api/closures https://atxfloods.com https://austintexas.gov
https://thetrailfoundation.org/
"""

SHARES = "closures"
