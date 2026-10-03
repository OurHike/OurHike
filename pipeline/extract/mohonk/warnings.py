"""Mohonk Preserve: warnings, 1 ArcGIS layer extracted here (decision 53 phase B, 2026-10-03).

- `mohonk_deer_zones`: Mohonk Preserve deer management zones,
  `MP_Deer_Management_with_Restrictions/FeatureServer/0`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://mohonkpreserve.org/wp-json/wp/v2/pages/13789
(wordpress); https://mohonkpreserve.org/wp-json/wp/v2/pages?slug=peregrine-watch-updates
(wordpress); https://mohonkpreserve.org/wp-json/wp/v2/wphash_ntf_bar (wordpress).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mohonk Preserve: warnings, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

Zones without dates. The dates are in a PDF nobody has parsed (@unvalidated whether they are
machine-readable). Skeptic additions (Measured 2026-10-01): the layer's fields are only
`Zone_Number`, `Zone_Name`, `Area_Acres` and `Perimeter_MIles`, so no restriction or date field
exists despite the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `MP_Deer_Management_with_Restrictions/FeatureServer/0`: 16
polygons, `dataLastEditDate` 2026-08-18, fields `Zone_Number`/`Zone_Name`/`Area_Acres` (attachments
enabled). The season's dates sit in `wp-content/uploads/2026/09/HuntingRegulations2026.pdf` and the
hunt maps `2025_DeerManagement_Main/D1/D2/D3.pdf`, linked from `/…/deer-management-program/`
(`modified` 2026-09-01). The alerts page's "Alerts" section carries a storm-hazard notice ("downed
trees, ruts, and areas of standing water").

Its `where`:
https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services/MP_Deer_Management_with_Restrictions/FeatureServer/0
https://mohonkpreserve.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mohonk_deer_zones",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
