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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("fltc_hunting_bypasses",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
