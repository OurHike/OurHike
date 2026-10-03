"""New York State Dept of Environmental Conservation: warnings, 2 ArcGIS layers extracted here
(decision 53 phase B, 2026-10-03).

- `nysdec_hab_reports`: DEC harmful algal bloom reports, `Current_HAB_Reports_DIL/FeatureServer/0`.
- `nysdec_big_game_seasons`: DEC big-game seasons by wildlife management unit,
  `big_game_CopyFeatures/FeatureServer/0`. Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://dec.ny.gov/things-to-do/hiking/adirondack-backcountry/backcountry-information-for-adirondack-park
(html_page); https://content.govdelivery.com/accounts/NYSDEC/bulletins/37eccff (html_page);
https://api.nysmesonet.org/data/firewx/GetFDRA/ (json_api - robots.txt disallows it, so not to be
fetched).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

DEC's warnings: fire danger is Mesonet's under a no-redistribution policy, and the hunting and
algal-bloom layers are not landed.

Its `checked` (confirmed 2026-10-01): fire danger: NYS Mesonet's GetFDRA JSON, 12 Fire Danger Rating
Areas with risk and validity dates, embedded in DEC's fire-danger map; no FDRA polygons were found |
hunting seasons by Wildlife Management Unit: big_game_CopyFeatures/FeatureServer/0, 92 polygons,
last edited 2026-09-11 | harmful algal bloom reports: Current_HAB_Reports_DIL/FeatureServer/0

Its `where`: https://api.nysmesonet.org/data/firewx/GetFDRA/
https://dec.ny.gov/environmental-protection/wildfires/fire-danger-map
https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services/Current_HAB_Reports_DIL/FeatureServer/0

Its `terms`, verbatim: NYS Mesonet Data Access Policy: no redistribution "without the express prior
written consent of RFSUNY" (the fire-danger feed; the two DEC layers carry no such text)

Its `reason`: the two DEC layers are not landed: neither has a sources.json row, and whether hunting
seasons and algal blooms are warnings at all is an open question for the maintainer
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nysdec_hab_reports", "nysdec_big_game_seasons")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
