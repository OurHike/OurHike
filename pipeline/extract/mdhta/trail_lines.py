"""The Maah Daah Hey Trail Association's lines, the 19 GeoJSON files its /trail-guide/ map loads.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `mdhta_trail_guide`: 22 lines from 19 files: the Maah Daah Hey (2025), White Butte (2025), the Coal
  Creek Loop (2024) and 16 connectors and spurs (2016), keyed on the geometry. Every vertex carries a Z,
  in metres by one vertex read against 3DEP (@unvalidated beyond it).

The trail also arrives via `usfs` `usfs_trails` (MAAH DAAH HEY 011807 and 011808, 31 features, 144.98
mi, the coverage audit); dbt deduplicates. The coverage audit counted 20 files; the page lists 19 today.
mdhta/elevation.py SHARES this resource. Before this the file was the `via usfs` note.
"""

from extract._gis_files import gis_file

CLAIMS = ("mdhta_trail_guide",)
RESOURCES = [gis_file(key) for key in CLAIMS]
