"""The Mountains to Sound Greenway Trust's map locations, read through WordPress REST as the site's own map
asks for them (`cm-map-location` with `_latlng=acf_loc_address`).

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
change check, the measured key, the terms and what holds it back.

- `mtsg_map_locations`: 185 locations, 182 with a coordinate: trails 47 (many named '…Trailhead'),
  heritage sites 40, parks 39, campgrounds 28, museums 17, picnic areas 8, visitor centres 3, keyed on
  the post id. The categories overlap; trailheads and campgrounds are points of interest and the rest
  places, split in dbt.
"""

from extract._ogc import json_features

CLAIMS = ("mtsg_map_locations",)
RESOURCES = [json_features(key) for key in CLAIMS]
