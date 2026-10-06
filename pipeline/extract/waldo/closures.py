"""Waldo County Trails Coalition: closures, from the Hills to Sea Trail's closures page, hourly (decision 53
phase B, 2026-10-03).

`hills_to_sea_closures` reads https://www.hillstosea.org/closures as one PageNotice (extract/_notices.py),
read live under our agent on 2026-10-03 after the Squarespace site's robots.txt (no rule matching
/closures, no Crawl-delay). The trail crosses private land, and its '2026 Closures' are by town
(Montville, Unity, Waldo), eight dated lines such as 'Closed from Oct 3 thru Dec 12 (Closure includes
Sundays)', plus 'The trail on Hogback Mountain in Montville remains closed until further notice'.
SAFETY, the day of the read: several hunting closures start on 2026-10-03. The page states no date and
sends no Last-Modified, so the row's only date will be OurHike's first sight of it; its weak ETag is not
trusted. The row lands the title, a hash of <main> and the link.

The page's 'Hunting Seasons' section is the warnings half, so not_available.toml [waldo.warnings] shares this file. The
/maps page carries no hunting or orange text in its HTML (the coverage audit's 'Wear orange' line may
sit inside map images) and is not read.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c4_regional_1): "A page. Safety-relevant now: several closures start late September or Oct 3."
"""

from extract._kinds import page_notice

CLAIMS = ("hills_to_sea_closures",)
RESOURCES = [page_notice("hills_to_sea_closures")]
