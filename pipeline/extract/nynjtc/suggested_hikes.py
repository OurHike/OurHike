"""NYNJTC's hike write-ups through the Hike Finder export: 385 hikes, 113 with a published GPX track.

Counts from the registry row, 2026-09-15; the export is behind a site
password, read from HIKEFINDER_PASSWORD, which this sandbox does not hold,
so nothing here was re-read today. The host's robots.txt asks for a 10 s
crawl delay (read 2026-10-01) and the resource keeps it, about 83 minutes a
month. Not landed: the 21 public `hike` posts on nynjtc.org, 10 of which join
the export by name (coverage audit, batch b2_nynjtc, skeptic pass).
"""

from extract._kinds import published_hikes

CLAIMS = ("nynjtc_hike_finder",)
RESOURCES = [published_hikes(key) for key in CLAIMS]
