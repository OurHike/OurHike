"""Standing Stone Trail Club: warnings, from the trail-alerts page, hourly (decision 53 phase B, 2026-10-03).

`sstc_trail_alerts` reads https://www.standingstonetrail.org/trail-alerts as one PageNotice
(extract/_notices.py), read live under our agent on 2026-10-03 (Wix robots.txt: `User-agent: *` /
`Allow: /`). The club's one current page: "WEAR BLAZE ORANGE November 15 to December 15 ALL TRAIL
SECTIONS", "NO PARKING ANYTIME Little Augwick Creek Side of highway 522", and a link to DCNR's 2023
Rothrock State Forest activities PDF, which is stale and not read. Its hunting dates are explicit in
the text the reader does not parse; the page states no update date.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c8_regional_5): "Page. The hunting dates are explicit."
"""

from extract._kinds import page_notice

CLAIMS = ("sstc_trail_alerts",)
RESOURCES = [page_notice("sstc_trail_alerts")]
