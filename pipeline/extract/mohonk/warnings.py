"""Mohonk Preserve: warnings, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `mohonk_deer_zones`: Mohonk Preserve deer management zones,
  `MP_Deer_Management_with_Restrictions/FeatureServer/0`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

The preserve's alerts and peregrine-watch pages are read in closures.py (`mohonk_alerts`,
`mohonk_peregrine_updates`, decision 53 phase B, 2026-10-03); their notices are split into closures
and warnings in dbt.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mohonk_deer_zones",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
