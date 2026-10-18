"""Oregon Department of Fish and Wildlife: warnings, extracted here once for every club that draws on
it (read 2026-10-03). Its steward is no managing club, so it lives in _shared/, and each club that draws on it says so in not_available.toml.

- `odfw_orham_alert_areas`: ODFW hunting access map: alert areas, `ORHAM/ORHAM/MapServer/6`. Its row
  says why it is held back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = ("odfw_orham_alert_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
