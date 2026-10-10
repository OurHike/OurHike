"""The Ozark Highlands Trail's major trailheads, segment by segment, from OHTA's trail page, read through
WordPress page 15's REST route.

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent) and registered in
sources.json, where the row carries the count, the measured key and what holds it back.

- `ohta_major_trailheads`: 41 trailheads in four segments, keyed on the segment and the name; a trailhead at a
  segment's end is listed, and lands, under both segments.

The FAQ's 14 public campgrounds and its water ("In the drier months (July – September) the water can be hard
to find … stash some water") are prose with no fix (the coverage audit, 2026-10-01), so no water or campground
point is published to load beyond the campground trailheads the lists name.
"""

from extract._pages_points import page_points

CLAIMS = ("ohta_major_trailheads",)
RESOURCES = [page_points(key) for key in CLAIMS]
