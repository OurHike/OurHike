"""Ice Age Trail Alliance: closures, 2 ArcGIS layers extracted here (decision 53 phase B, 2026-10-03).

- `iata_trail_conditions`: Ice Age Trail conditions (posted),
  `IAT_Trail_Conditions_Posted/FeatureServer/0`.
- `iata_hunting_closures`: Ice Age Trail hunting-season closures,
  `IAT_Hunting_Closures/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

NPS'S ALERTS FOR THIS TRAIL LAND IN nps/warnings.py, and this file used to be a `via` note for them
alone (decision 34); a file takes one form, so that relation is prose here now. NPS's alerts for
park code `iatr` land once, in nps/warnings.py's `nps_alerts`, whose sources.json entry lists it
against this folder in `park_codes`. The decision 53 inventory (batch 3, 2026-10-03) read 16
(Information 11, all titled 'Reroute in Effect — ...'; Caution 5 'Use Caution — ...'): the same
events republished by NPS, deduplicated against the IATA layers in dbt. NPS's `Park Closure`
category is the closures half, split from the rest in dbt; no alert carries geometry, so the NPS
category never sets `obstructs_trail` alone.

Refused by robots.txt and never fetched (the decision 53 inventory, batch 3, 2026-10-03):
iceagetrail.org's website, the hunting-season page
(https://iceagetrail.org/explore/plan-hike/hunting-season-iata/) among it: `User-agent: *` /
`Disallow: /`, with `crawl-delay: 300`. The layers above live on services.arcgis.com, another host,
and decision 39 counts a club's public layer as published.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Ice Age Trail Alliance: closures, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Filter `posted='yes'`. The 57 `no` rows include alerts from as far back as 2019 ("Stewart Tunnel
closed", posted 2019-09). Loading all 80 would show expired closures as live. Gun-deer closures are
lines that close segments, so they `obstruct_trail` (decision 7). The NPS copy must be deduplicated
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `.../IAT_Trail_Conditions_Posted/FeatureServer/0`: 80 rows,
last edit 2026-09-30. `posted`: yes 21, no 57, pending 2. Headings include Trail Closed 5, Trail
closure 4, Logging Closure 3, Prescribed Burn Closure 2, Boardwalk Closed, Bridge Closed, and
"Hunting Closure beginning 9/1 / 10/15 / 11/2 / 11/22". Fields: `date_posted`, `date_updated`,
`hyperlink`, `segment_name`. `.../IAT_Hunting_Closures/FeatureServer/0`: 52 polylines (`GunDeer` =
Closed on 51, `OtherSeason` = Closed on 6), last edit 2026-09-21. The NPS Data API
`alerts?parkCode=iatr` returns 16 (11 "Reroute in Effect", 5 "Use …

Its `where`: https://dnrmaps.wi.gov/arcgis/rest/services https://iceagetrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("iata_trail_conditions", "iata_hunting_closures")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
