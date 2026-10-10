"""USGS — The National Map: warnings, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `usgs_pwfdf_assessments`: USGS post-fire debris-flow hazard assessments (locations),
  `ls/pwfdf/MapServer/0`. Read daily, not on the type's lane: an on-prem layer with no maintained
  date answers its change check UNKNOWN, so each check is a full read of 749 points.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

The one notice source the phase A inventory listed for this folder (2026-10-03), USGS's elevated
volcanoes API, lands once in _shared/usgs/volcanoes.py as `usgs_elevated_volcanoes`, on the warnings
lane (decision 53, phase B), so nothing is left to wire here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usgs_pwfdf_assessments",)
RESOURCES = [
    arcgis_layer(
        "usgs_pwfdf_assessments",
        cadence_override="daily",
        cadence_reason="an on-prem layer with no maintained date answers its change check UNKNOWN, so each check is a full read of 749 points; assessments are added per fire, days apart, so a daily read is enough (@unvalidated: settled by _extract_runs' row counts over a fire season)",
    ),
]
