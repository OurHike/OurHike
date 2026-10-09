"""NY State Parks' closures: OPRHP's temporary trail closures, and the Empire State Trail's. Hourly, as every closure is.

- `oprhp_trail_closures`: OPRHP's temporary trail closures, `NY_State_Parks_Temporary_Trail_Closure/0`.
  4 polygons, last edited 2026-06-16 (coverage audit 2026-10-01, batch b4_oprhp_mohonk_gatc). The
  layer is a subset of OPRHP's own alerts: ALERTS_NOTICES_SURVEY.md §3b found Lake Awosting closed
  on parks.ny.gov and absent here. So a zero from this layer says the layer is empty, never that
  nothing in a state park is closed, and the count proving it is the server's own
  `returnCountOnly`. The layer's own item carries an empty `licenseInfo`
  (ORG_COVERAGE_SURVEY.md §3b).
- `ptny_est_closures`: the Empire State Trail's closed sections, Parks & Trails New York's
  `Empire_State_Trail_Closures_(Public_View)/FeatureServer/0`, 9 lines on 2026-10-08, none with a
  date, a reason or a link. Parks & Trails New York has no catalogue row, so its layer is claimed
  here, beside OPRHP's (pipeline/ELT.md's folder-placement table).
- `oprhp_est_trail_closures_page`: the Empire State Trail's own closures page,
  https://empiretrail.ny.gov/trail-closures, one PageNotice: its <h1> 'Trail Closures' (which
  expect_title holds) and its own 'Updated <date>' stamp, read live 2026-10-08. Read with
  `items="li"` (decision 128, the maintainer's poll of 2026-10-09): each closure on the page is
  one <li> in <main>, 14 of them on 2026-10-09 (12 distinct: Albany's Dunn Memorial Bridge item
  is listed under all three sections), and the row lands each one's sha256, never its words.
  A section of `ptny_est_closures` draws only while it is matched to one of those items
  (dbt's int_closures__page_matches).
- `oprhp_est_under_construction`: the Empire State Trail's sections under construction,
  `EST_Public/FeatureServer/5` (UnderConstruction), 2 polygons on 2026-10-08, neither dated.

Decision 54's wave 6 (2026-10-08) added the last three, folding the coverage audit's
`empire-state-trail` candidate into this folder; the two layers' rows say why each is held.

Each source's row in sources.json holds its counts, dates, terms and key. Change checks are
_kinds.py's ArcgisLayer (a conditional GET of the layer document on ArcGIS Online, and an allowed
zero only beside the server's own returnCountOnly read in the same run) and extract/_notices.py's
PageNotice (the page read every run, one request, and FRESH only when what would land hashes as
the last load did).
"""

from extract._kinds import arcgis_layer, page_notice

CLAIMS = ("oprhp_trail_closures", "ptny_est_closures", "oprhp_est_trail_closures_page", "oprhp_est_under_construction")
RESOURCES = [
    arcgis_layer("oprhp_trail_closures"),
    arcgis_layer("ptny_est_closures"),
    page_notice("oprhp_est_trail_closures_page", expect_title="Trail Closures", items="li"),
    arcgis_layer("oprhp_est_under_construction"),
]
