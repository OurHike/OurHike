"""Utah Division of Forestry, Fire and State Lands: warnings, extracted here once for every club that
draws on it (decision 53 phase B, 2026-10-03). Its steward has no club folder (decision 18), so it
lives in _shared/, and each club's own file carries a `via` note naming it (decision 34).

- `utah_ffsl_fire_restrictions`: Utah fire restrictions (FFSL, multi-agency),
  `Fire_Restrictions/FeatureServer/0`. Filtered on the agency's own status field: `Status NOT IN
  ('Rescinded', 'Superseded') OR Status IS NULL`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = ("utah_ffsl_fire_restrictions",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
