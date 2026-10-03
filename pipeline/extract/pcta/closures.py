"""Pacific Crest Trail Association: closures, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `pcta_fires_and_closures`: PCTA fires and trail closures,
  `PCT_Fires_and_Trail_Closures_public_view/FeatureServer/0`.
- `pcta_closure_lines`: PCTA closure lines (closures map), `Closure_Data_view/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://closures.pcta.org/ (html_page);
https://www.pcta.org/discover-the-trail/trail-conditions/ (html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Pacific Crest Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Neither layer has an active flag or an end date. "Current" can only be inferred from `Year` plus the
CMS page, which is @unvalidated. What would settle it is asking PCTA which layer its closures page
renders.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `PCT_Fires_and_Trail_Closures_public_view/FeatureServer/0`:
144 points, last edit 2026-09-28. Fields: `Year`, `Closure_Name`, `Type`, `Agency_Unit`,
`Miles_of_PCT_in_Closure_Area`. Year 2026: 13 `Wildfire` + 10 `Other Closure`.
`Closure_Data_view/FeatureServer/0,1,2`: Closure Point 111, Line 138, Polygon 127, last edit
2026-09-24. Those are cartographic: `Type` holds symbol names (`Crossed out line` 54, `Purple` 47…),
`Label_Text` reads "PCT Closed", and `CMS_ID` links to `closures.pcta.org`. The page itself returns
HTTP 429 (Vercel checkpoint).

Its `where`:
https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCT_Fires_and_Trail_Closures_public_view/FeatureServer/0
https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/Closure_Data_view/FeatureServer/0
https://closures.pcta.org

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("pcta_fires_and_closures", "pcta_closure_lines")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
