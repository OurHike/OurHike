"""Arizona Trail Association: photos, as manifest rows read from six of ATA's own ArcGIS layers, never their pixels.

Section K of decision 54 handed these back as ArcGIS photo fields; read live on 2026-10-10 (robots.txt first,
lib/user_agent.py's agent, 2 s or more between requests to one host) and registered in sources.json, where each row
carries its counts, its measured key, the fields it never asks for, and the terms, which state nothing.

- `ata_sign_photos`, `ata_gate_photos`, `ata_road_crossing_photos`, `ata_other_inventory_photos`: layers 0, 1, 2
  and 8 of the Scenic Resources view, ATA's inventory of the trail's signs (2,117), gates (305), road crossings
  (230) and other features (26), each with its own position and one photograph's URL in `Link`, on
  www.giseifert.com: "what does this junction look like" (the coverage audit, 2026-10-01). Keyed on `GlobalID`.
- `ata_storymap_photos` and `ata_storymap_running_photos`: the two public views of ATA's StoryMap photo points, 174
  and 14, each a Flickr photograph in `pic_url`. The hosted layer behind them refuses an anonymous request, and the
  two views share no photograph (compared 2026-10-10), so each is its own row. Keyed on `pic_url`.

Each row's `where` keeps only rows whose photo field holds a URL. No layer states a licence for its photographs,
and the coverage audit read ATA's Flickr account as All rights reserved, so every row reaches no hiker
(reaches_hikers false) until the maintainer rules on photographs with no stated licence. The layers are ATA's own,
on ATA's ArcGIS Online organization, which AZGeo's hub lists: not_available.toml [azgeo.photos] draws on this file
(decision 34).
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "ata_sign_photos",
    "ata_gate_photos",
    "ata_road_crossing_photos",
    "ata_other_inventory_photos",
    "ata_storymap_photos",
    "ata_storymap_running_photos",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
