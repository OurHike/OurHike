"""Colorado Parks & Wildlife — COTREX: warnings, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `cpw_bear_conflict_areas`: CPW black bear human conflict areas, `CPWSpeciesData/FeatureServer/20`.
  Read monthly, not on the type's lane: a standing conflict-area map (lastEditDate 2026-05-07),
  whose hundreds of polygons are too large a first read for the hourly lane's 150 s budget.
- `cpw_lion_conflict_areas`: CPW mountain lion human conflict areas,
  `CPWSpeciesData/FeatureServer/93`. Read monthly, not on the type's lane: a standing conflict-area
  map (lastEditDate 2026-05-07), whose hundreds of polygons are too large a first read for the
  hourly lane's 150 s budget.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://cpw.state.co.us/hunting/big-game (html_page);
https://cpw.state.co.us/living-bears (html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Colorado Parks & Wildlife — COTREX: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

These are standing conflict-area maps, not activity reports. A card must word them as "an area CPW
maps as a bear–human conflict area", never as "bear activity reported". Season dates live in
brochures (pdf), not opened.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Hunting: `CPWAdminData/6` GMU Boundary (Big Game), 186
polygons, plus `cpw.state.co.us/hunting/big-game` (page). Bears: `cpw.state.co.us/living-bears`
(page). `/12` Walk In Access: 470 polygons with `CLOSEDATE`. | Skeptic adds (Measured):
`services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/20` "Black
Bear Human Conflict Area": 613 polygons, and `/93` "Mountain Lion Human Conflict Area": 266
polygons, both last edited 2026-05-07. The item licence reads "This wildlife distribution map is a
product and property of Colorado Parks and Wildlife…".

Its `where`: https://cpw.state.co.us/hunting/big-game https://cpw.state.co.us/living-bears
https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/20
https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cpw_bear_conflict_areas", "cpw_lion_conflict_areas")
RESOURCES = [
    arcgis_layer(
        "cpw_bear_conflict_areas",
        cadence_override="monthly",
        cadence_reason="a standing conflict-area map (lastEditDate 2026-05-07), whose hundreds of polygons are too large a first read for the hourly lane's 150 s budget",
    ),
    arcgis_layer(
        "cpw_lion_conflict_areas",
        cadence_override="monthly",
        cadence_reason="a standing conflict-area map (lastEditDate 2026-05-07), whose hundreds of polygons are too large a first read for the hourly lane's 150 s budget",
    ),
]
