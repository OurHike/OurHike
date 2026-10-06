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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wa_rco_trailhead_status",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
