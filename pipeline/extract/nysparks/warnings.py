"""NY State Parks / NYS GIS Clearinghouse: warnings, 1 ArcGIS layer extracted here (decision 53 phase
B, 2026-10-03).

- `oprhp_hunting_areas`: NY State Parks hunting areas,
  `NY_State_Parks_Hunting_Areas_2_view/FeatureServer/1`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

NY State Parks / NYS GIS Clearinghouse: warnings, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

The layer carries no season dates, so it can say "hunting happens here" but not "this week". Joining
it to DEC's statewide season calendar would be the next step. ~~The meaning of code 1 vs 2 is
@unvalidated beyond the one sample~~ (changed by skeptic: settled by the group-by this note asked
for.) …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `NY_State_Parks_Hunting_Areas_2_view/FeatureServer/1`
"NYSHuntingBoundaries", polygon, 223, `dataLastEditDate` 2026-09-30 (edited the day before this
audit). Field `Hunting` reads 1 on 134 and 2 on 89. The sampled code-2 row is "Restricted
Area/Safety Zone", Allegany SP, 1,919.6 acres. Per-species Y/N plus coded implements (`BG_Deer_Imp`
e.g. "Archery/Crossbow/Shotgun/Muzzleloader"), `WMU`, `Website`, `MasterAreaID`. The item reads "All
hunting boundaries should be seen as approximate. Species, implements, and dates may be restricted".
There are ~60 per-park "Hunting Parks App" web maps …

Its `where`:
https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services/NY_State_Parks_Hunting_Areas_2_view/FeatureServer/1

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_hunting_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
