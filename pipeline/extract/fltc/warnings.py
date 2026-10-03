"""Finger Lakes Trail Conference: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `fltc_hunting_bypasses`: FLTC hunting-season bypass routes, `Hunting_Bypasses_/FeatureServer/2`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://fingerlakestrail.org/FLTC/new_notice/noticesJSON.php?data=notices (json_api - robots.txt
disallows it, so not to be fetched).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Finger Lakes Trail Conference: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 41 active notices flagged `tn_Hunting=1`.
`…/Hunting_Bypasses_/FeatureServer/2` holds 69 bypass lines (lastEdit 2026-07-19).
`/hunting-season-schedules/` lists NYS Southern Zone dates. Waypoints include `Advisory` (7) and
`HuntingClosures` (76).

Its `where`: https://fingerlakestrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fltc_hunting_bypasses",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
