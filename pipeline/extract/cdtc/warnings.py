"""Continental Divide Trail Coalition: warnings, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `cdtc_reroutes`: CDT reroutes, `Reroutes_view/FeatureServer/1`.
- `cdtc_national_defense_area`: National Defense Area on the New Mexico border (CDTC),
  `National_Defense_Area_NM/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://cdtcoalition.org/closures-and-alerts/ (html_page).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Continental Divide Trail Coalition: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

A National Defense Area is military ground along the New Mexico border, and entering it is a federal
offence. The CDT's southern terminus is on that border. Whether this polygon touches the trail or
the Crazy Cook approach was not measured. It belongs in `cdtc/warnings.py` (or closures, if it …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same layers, rows with `Type=Alert` and `Active=Yes`.
Example: "Black Fire… Stay alert for potentially dangerous conditions and slow travel due to
standing dead trees, blowdown, and eroded trail." Also the static page
`cdtcoalition.org/bears-and-the-cdt/`. | Skeptic adds: `National_Defense_Area_NM/FeatureServer/0`: 1
polygon named "National Defense Area", last edit 2026-03-24, about 449 km² by `Shape__Area`
(Measured). It is not one of the 149 + 76 alert features: a `LIKE '%efense%'` query on Alert Points
returned 0 (Measured).

Its `where`:
https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/National_Defense_Area_NM/FeatureServer/0
https://cdtcoalition.org/bears-and-the-cdt/ https://services.wygisc.org/HostGIS/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cdtc_reroutes", "cdtc_national_defense_area")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
