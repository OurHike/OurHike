"""New York State Dept of Environmental Conservation: warnings, 2 ArcGIS layers extracted here
(decision 53 phase B, 2026-10-03).

- `nysdec_hab_reports`: DEC harmful algal bloom reports, `Current_HAB_Reports_DIL/FeatureServer/0`.
- `nysdec_big_game_seasons`: DEC big-game seasons by wildlife management unit,
  `big_game_CopyFeatures/FeatureServer/0`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

The decision 53 inventory's other DEC sources (2026-10-03): the Adirondack backcountry page lands in
nysdec/closures.py as `nysdec_adk_backcountry`, which the warnings staging model reads too; DEC's
GovDelivery bulletin is one bulletin per URL, not a channel; and the NYS Mesonet fire-danger API
(https://api.nysmesonet.org/data/firewx/GetFDRA/) is disallowed by its robots.txt, so never fetched.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nysdec_hab_reports", "nysdec_big_game_seasons")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
