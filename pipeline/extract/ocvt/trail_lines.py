"""The Outdoor Club at Virginia Tech's own A.T. tracks, two GPX files linked from its trail-maintenance
page.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `ocvt_at_tracks`: 'Pine Swamp Branch Shelter to U.S. 460' and 'VA 611 to I-77', GPSBabel output of
  2009-08-25 with `ele` 0.0 throughout, keyed on the geometry.

Superseded by ATC's centerline (edited 2026-08-04), where the club's portion is drawn in dbt
(`centerline`, 16 features, 26.9 mi under OCVT, and `side_trails`, 7): a dated cross-check, deduplicated
after the load. Before this the file was the `via atc` note.
"""

from extract._gis_files import gis_file

CLAIMS = ("ocvt_at_tracks",)
RESOURCES = [gis_file(key) for key in CLAIMS]
