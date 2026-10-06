"""Ice Age Trail Alliance: warnings, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `iata_lands_hunting_regs`: Ice Age Trail Alliance lands hunting regulations,
  `IATA_Lands_Hunting_Regulations_view/FeatureServer/9`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

NPS'S ALERTS FOR THIS TRAIL LAND IN nps/warnings.py, and this file used to be a `via` note for them
alone (decision 34); a file takes one form, so that relation is prose here now. NPS's alerts for
park code `iatr` land once, in nps/warnings.py's `nps_alerts`, whose sources.json entry lists it
against this folder in `park_codes`. NPS's Danger, Caution and Information categories are the
warnings half, split from the rest in dbt. The decision 53 inventory (batch 3, 2026-10-03) read 16
(Information 11, all titled 'Reroute in Effect — ...'; Caution 5 'Use Caution — ...'): the same
events republished by NPS, deduplicated against the IATA layers in dbt.

Refused by robots.txt and never fetched (the decision 53 inventory, batch 3, 2026-10-03):
iceagetrail.org's website, the hunting-season page
(https://iceagetrail.org/explore/plan-hike/hunting-season-iata/) among it: `User-agent: *` /
`Disallow: /`, with `crawl-delay: 300`. The layers above live on services.arcgis.com, another host,
and decision 39 counts a club's public layer as published.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Ice Age Trail Alliance: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

"High Water" and "Trail Flooded" are warnings, not drought (decision 2). Skeptic spot-check:
`IATA_Lands_Hunting_Regulations_view/9` = 65, last edit 2026-07-13.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same conditions layer's non-closure headings: "Caution -
Logging Activities" 5, "Caution - logging near trail" 3, High Water 3, Storm Damage 3, Trail Flooded
2, Confusing blazes 2, hornet nests 2, "New Wood River - dangerous ford" 1.
`.../IATA_Lands_Hunting_Regulations_view/FeatureServer/9`: 65 polygons. `.../IAT_Dogs_Prohibited`: 7
lines plus 6 points. Page `iceagetrail.org/explore/plan-hike/hunting-season-iata/` (blocked by
robots.txt).

Its `where`: https://iceagetrail.org/explore/plan-hike/hunting-season-iata/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("iata_lands_hunting_regs",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
