"""The Catamount Trail Association's access points, from its interactive map's data files.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `catamount_access_points`: 80 trailhead and parking access points with a PRIMARY flag (CSV with
  LATITUDE and LONGITUDE, 2017-11-27), keyed on the geometry.
"""

from extract._gis_files import gis_file

CLAIMS = ("catamount_access_points",)
RESOURCES = [gis_file(key) for key in CLAIMS]
