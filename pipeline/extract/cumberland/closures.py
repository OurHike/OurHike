"""Cumberland Trail / Tennessee State Parks: closures, 1 ArcGIS layer extracted here (decision 53 phase
B, 2026-10-03).

- `ctsst_public_hazards_closures`: Cumberland Trail public hazards and closures,
  `PUBLIC_CTSST_2020_gdb/FeatureServer/15`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Also drawn from (decision 53 phase B, 2026-10-03, decision 34): _shared/tdec/ `tdec_trail_closures`.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://tnstateparks.com/api/alerts (json_api).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Cumberland Trail / Tennessee State Parks: closures, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

The strongest closures find in this batch. The closures arrive as segment geometry, already marked
closed, and are edited daily. The `TSP_UID` in every source joins the alerts to parks and trails.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `.../TDEC_Trail_Closures_Public/FeatureServer/0`: 22 closed
trail segments with geometry, `TRSTAT` in {Temporarily Closed, Closed Repairs}, `Notes` (e.g. "Trail
Wash Out", "closed temporarily as of 6/28 due to flooding"), last edit 2026-09-30 19:50 UTC. Two are
CT segments: Cumberland Mountain Section (3.89 mi) and North Chickamauga Section (1.66 mi).
`https://tnstateparks.com/api/alerts` (JSON): 79 alerts with `type`, `expiration_date`,
`parks[].TSP_UID`, `trails[]`, `campgrounds[]`. The JSON:API trails node's `field_trails_status`
reads `partial_closure` on CT North Chickamauga. CTSST …

Its `where`: https://tnstateparks.com/api/alerts

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ctsst_public_hazards_closures",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
