"""City of Duluth Open Data: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

City of Duluth Open Data: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

It may be stale.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `ObstructionService/MapServer/0` "Obstructions": 5 points,
fields `Type`, `Comments`; item modified 2022-09-21. The attribute query returned HTTP 400, so the
content is unknown. | Skeptic adds: a second item, "ObstructionsService"
(`a699c2266ee0479ca9e3ea72b9a22fee`, owner a personal ArcGIS account, 2021-07-08), answers 404
"Service not found": the item is dead. The org also has a "Road Closure & Obstruction" Experience
app (2026-06-25), which is for streets.

Its `where`:
https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
