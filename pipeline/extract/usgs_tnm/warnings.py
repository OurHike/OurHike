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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

USGS — The National Map: warnings, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Volcano alerts matter only on volcanic stretches (e.g. Cascades). Neither feed is drought, so both
are in scope for warnings. Debris flow is the more trail-relevant of the two: in a storm, a trail
through a recent burn scar is where a hiker meets one, and the segment layer says which drainages. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Volcano Hazards Notification Service:
`https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes` (JSON). Today it returned
elevated volcanoes, e.g. Great Sitkin ORANGE/WATCH, sent 2026-09-30 19:47 UTC. A CAP variant is at
`…/getCapElevated`. Skeptic spot check: 4 elevated today (Great Sitkin ORANGE/WATCH, Kilauea
ORANGE/WATCH, Shishaldin YELLOW/ADVISORY, Ahyi Seamount YELLOW/ADVISORY). | Skeptic adds: post-fire
debris-flow hazard assessments.
`https://earthquake.usgs.gov/arcgis/rest/services/ls/pwfdf/MapServer`. Layer 0 "Locations" holds 749
assessed fires (`fire`, `start_date` …

Its `where`: https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes
https://earthquake.usgs.gov/arcgis/rest/services/ls/pwfdf/MapServer

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
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
