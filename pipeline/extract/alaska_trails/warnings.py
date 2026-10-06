"""Alaska Trails: warnings, 2 ArcGIS layers extracted here (decision 53 phase B, 2026-10-03).

- `alaska_trails_obstacles`: Alaska Long Trail obstacles (crossings),
  `AKLT_Trail_Obstacles/FeatureServer/20`.
- `alaska_trails_seward_obstacles`: Seward to Eagle River obstacles,
  `Seward_to_Eagle_River_Obstacles/FeatureServer/2`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

NPS'S ALERTS FOR THIS TRAIL LAND IN nps/warnings.py, and this file used to be a `via` note for them
alone (decision 34); a file takes one form, so that relation is prose here now. NPS's alerts for
park codes `dena` and `kefj` land once, in nps/warnings.py's `nps_alerts`, whose sources.json entry
lists them against this folder in `park_codes`. NPS's Danger, Caution and Information categories
are the warnings half, split from the rest in dbt. The decision 53 inventory (batch 3, 2026-10-03)
read 2 (Park Closure 'Teklanika Area Closures' 2026-09-24; Information 'Road Open To: Mile 30');
NPS manages 8 AKLT segments.

The club's other notice sources are the land managers', each read once outside this folder (decision
34): the Chugach NF's alerts page (https://www.fs.usda.gov/r10/chugach/alerts, 8 forest and 3 region
alerts on 2026-10-03) in usfs/closures.py as `usfs_r10_chugach_alerts`, and Alaska State Parks'
condition reports (https://dnr.alaska.gov/parks/asp/curevnts.htm, 'Last Update: September 30, 2026',
linking 28 per-park PDFs), a steward with no club folder, in _shared/alaska_state_parks/ as
`alaska_state_parks_conditions`. The club's own https://www.alaska-trails.org/trail-reports is a
list of links to those managers, not a notice.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Alaska Trails: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

These are planning records (they carry a `Cost` field), but "impassable crossing" is a hazard point
all the same.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `AKLT_Trail_Obstacles/FeatureServer/20`: 13 points, last edit
2026-03-05: `BridgeNeeded(Impassable)` 4, `BridgeNeeded(Passable)` 7, `RiverFord` 2.
`Seward_to_Eagle_River_Obstacles/2`: 7 (2023-05-17).

Its `where`:
https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/AKLT_Trail_Obstacles/FeatureServer/20

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("alaska_trails_obstacles", "alaska_trails_seward_obstacles")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
