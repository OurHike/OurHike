"""Pacific Crest Trail Association: closures, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `pcta_fires_and_closures`: PCTA fires and trail closures,
  `PCT_Fires_and_Trail_Closures_public_view/FeatureServer/0`.
- `pcta_closure_lines`: PCTA closure lines (closures map), `Closure_Data_view/FeatureServer/1`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

NOT READ, BECAUSE WALLED (decision 53's inventory, batch 2, 2026-10-03): https://closures.pcta.org/
answered our agent with Vercel's Security Checkpoint (HTTP 429, `x-vercel-mitigated: challenge`, its
robots.txt too), and https://www.pcta.org/discover-the-trail/trail-conditions/ with Cloudflare's
challenge (HTTP 403, `cf-mitigated: challenge`). Neither is solved or worked round (decision 39);
not_available.toml [pcta.warnings]'s note quotes both, and holds until PCTA answers. So which of the two layers above
the closures page renders cannot be checked from here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("pcta_fires_and_closures", "pcta_closure_lines")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
