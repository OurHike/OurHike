"""Finger Lakes Trail Conference: closures, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `fltc_temporary_notices`: FLTC temporary notices, `Temporary_Notices/FeatureServer/14`.
- `fltc_seasonal_closures`: FLTC hunting and high-water closures, `Closures_/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://fingerlakestrail.org/FLTC/new_notice/noticesJSON.php?data=notices (json_api - robots.txt
disallows it, so not to be fetched).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Finger Lakes Trail Conference: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A structured feed. The closure label is free text (40 "CLOSED", plus "Logging", "Beaver dam has
flooded the trail.", …), so poll 7's `obstructs_trail` mapping is needed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01):
`https://fingerlakestrail.org/FLTC/new_notice/noticesJSON.php?data=notices` is JSON. It needs only
the PHPSESSID cookie the public page sets; there is no login. 713 notices run from 2004-11-01 to
2026-09-26; 121 active, 9 active with `tn_Closure` (e.g. 2026-09-07 "Trail Closed: Storm Damage,
River Rd to Portageville"). Fields: `tn_Hunting`, `tn_tempNotice`, `tn_Expire`, `tn_tmid` (map id;
`?data=maps` returns 62 maps). Also ArcGIS `Closures_/FeatureServer/0` ("Hunting and high water
closures": 82 lines) and `Temporary_Notices/FeatureServer/14` (28 points, lastEdit 2026-09-26).

Its `where`: https://fingerlakestrail.org/FLTC/new_notice/noticesJSON.php?data=notices
https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/Closures_/FeatureServer/0
https://services7.arcgis.com/GwV4OWqOyYWWUpBK/arcgis/rest/services/Temporary_Notices/FeatureServer/14

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fltc_temporary_notices", "fltc_seasonal_closures")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
