"""Carolina Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

The peak and tower lists give names and elevations, not coordinates. Places would come from a join
(GNIS, OSM; @unvalidated). These fit the shape #1780 — Let a club publish a challenge — places on
its own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket
List …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "8 programmes under `https://carolinamountainclub.org/hiking/hiking-challenges/` (pages modified "
        "2026-08-14 to 2026-08-30): 100 Favorite Trails (FH100); AT/MST (~94 mi A.T. + ~150 mi MST, log "
        "`AT-MST-Log-240213.pdf`); Art Loeb Trail (30.1 mi, with The Pisgah Conservancy); Centennial (50 hiked "
        "miles + 50 trail-work hours); Lookout Tower Challenge (23 WNC lookout towers, with directions and "
        "one-way mileages); Pisgah 400 (every official trail in the Pisgah Ranger District); South Beyond 6000 "
        "(40 peaks; ascent record `SB6KAscentRecord-062325.pdf`); Waterfall & Cascade 100 (100+ waterfalls, "
        "list …",
    ),
    where=("https://carolinamountainclub.org/hiking/hiking-challenges/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
