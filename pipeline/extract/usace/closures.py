"""US Army Corps of Engineers: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `usace_sam_closed_rec_areas`: USACE Mobile District closed recreation areas,
  `Closed_Recreation_Area_Public_View/FeatureServer/0`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

US Army Corps of Engineers: closures, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Too stale and too local to count as a feed. Recorded so nobody re-finds it and thinks it is one.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Mobile District
`.../Closed_Recreation_Area_Public_View/FeatureServer/0`: 2 polygons, last edit 2023-03-18.
Otherwise per-lake HTML pages.

Its `where`: https://usace.army.mil/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usace_sam_closed_rec_areas",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
