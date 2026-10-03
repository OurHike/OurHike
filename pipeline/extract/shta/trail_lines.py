"""Superior Hiking Trail Association: the Superior Hiking Trail's lines, SHTA's own 2025 alignment and Lake
County's layer of the trail.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `shta_line_2025`: Superior Hiking Trail main line, 2025 (SHTA). 55 lines, keyed on geometry.
- `shta_spurs_and_loops`: Superior Hiking Trail spurs and loops, 2025 (SHTA). 182 lines, keyed on geometry.
- `shta_spirit_mountain_spur_2025`: Spirit Mountain spur, 2025 (SHTA). 1 line, keyed on the registry key alone.
- `lake_county_superior_hiking_trail`: Superior Hiking Trail (Lake County, Minnesota). 576 lines, keyed on geometry.

Four datasets of the same ground with NCTA's `ncta_superior_hiking_trail` (ncta/), Duluth's
`duluth_superior_hiking_trail` (duluth/) and usfs_trails' 36 segments: deduplication is dbt's. The SHTA
service's other layers are campsites and trailheads (points) and parcels and easements (polygons), not
trail lines.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "shta_line_2025",
    "shta_spurs_and_loops",
    "shta_spirit_mountain_spur_2025",
    "lake_county_superior_hiking_trail",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
