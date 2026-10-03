"""Washington RCO — State Trails Database: closures, 1 ArcGIS layer extracted here (decision 53 phase
B, 2026-10-03).

- `wa_rco_trailhead_status`: WA RCO trailheads: status,
  `WA_RCO_Trails_Database_Public_View/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Also drawn from (decision 53 phase B, 2026-10-03, decision 34): _shared/wa_state_parks/
`wsprc_winter_rec_closures`.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/1,
WA DNR's Burn Bans layer, not re-read; layer 0, wired in _shared/wa_dnr/, carries BURN_BAN_LEVEL_NM
itself.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Washington RCO — State Trails Database: closures, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

This is not a feed. Load the attribute; do not build a closure source on it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Attribute only: Trailheads `trailhead_status` reads `closed`
1, `construction` 6, `seasonal` 6, with no dates. `trail_condition` on the trails holds condition
grades (A–D, Class 1–5), not closures.

Its `where`: https://gis.dnr.wa.gov/site1/rest/services https://gis.dnr.wa.gov/site3/rest/services
https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services
https://trails-wa-rco.hub.arcgis.com/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wa_rco_trailhead_status",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
