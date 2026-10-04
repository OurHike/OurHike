"""The Catamount Trail Association's lines: its interactive map's GeoJSON and its GPX download.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `catamount_main_trail`: 793 lines by SURFACE (2023-09-19), keyed on the geometry after 4 exact copies.
- `catamount_side_trails`: 325 lines by SURFACE (2017-11-27), keyed on the geometry after 1 exact copy.
- `catamount_full_route`: the December 2022 GPX download's 6 tracks, among them 'OLD CT - Camels Hump',
  a former alignment; the same zip's KML is the same 6 lines and is not read.

A SKI TRAIL: every line is a winter route, much of it on snowmobile corridors and unplowed roads, and
needs layer_rules' season before it draws. GeoJSON beats GPX: the association's page says the map and
GPX 'were last updated in 2021, so some reroutes will not be available', while its section PDFs were
updated in 2025 (the coverage audit). On ArcGIS the association's own `catamounttrail` account holds
only tile layers, offline map areas and a web map with no operational layer.
"""

from extract._gis_files import gis_file

CLAIMS = ("catamount_main_trail", "catamount_side_trails", "catamount_full_route")
RESOURCES = [gis_file(key) for key in CLAIMS]
