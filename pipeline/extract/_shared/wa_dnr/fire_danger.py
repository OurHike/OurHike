"""Washington State Department of Natural Resources: warnings, extracted here once for every club that
draws on it (read 2026-10-03). Its steward is no managing club, so it lives in _shared/, and each club that draws on it says so in not_available.toml.

- `wa_dnr_wildfire_danger`: WA DNR wildfire danger and burn bans,
  `Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/0`.
- `wa_dnr_ifpl`: WA DNR industrial fire precaution levels,
  `Public_Wildfire/WADNR_PUBLIC_WD_IFPL/MapServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = ("wa_dnr_wildfire_danger", "wa_dnr_ifpl")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
