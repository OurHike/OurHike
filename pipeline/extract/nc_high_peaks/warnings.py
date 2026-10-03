"""NC High Peaks Trail Association: warnings, from the club's list of trails open since Hurricane Helene, hourly
(decision 53 phase B, 2026-10-03).

`nchpta_open_trails` reads https://nchighpeaks.org/2024Hikes as one PageNotice (extract/_notices.py),
read live under our agent on 2026-10-03 after the site's robots.txt (Drupal's default, nothing matching
the page, no Crawl-delay). Its title is 'Hiking Trails Currently Open in Our Area' and its date the
page's own 'Update 7/30/2025'.

AN INVERSE LIST, FOURTEEN MONTHS OLD. The page names the trails that are open, not the ones that are
closed, so a trail's absence from it is never a closure, and it is filed here, as a warning at most,
rather than in closures.py. Its date must ride with it everywhere it shows.

The land managers' own alerts for the Black Mountains arrive through usfs/closures.py's
`usfs_r08_northcarolina_alerts` (no slug names the Black Mountains, the coverage audit) and nps/'s
Blue Ridge Parkway alerts (0 on 2026-10-03).

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p09_persist), which recorded nothing published by the club for warnings and named the land managers'
channels: the National Forests in North Carolina's 60 alert pages, NPS's BLRI alerts and NC State
Parks' banners.
"""

from extract._kinds import page_notice

CLAIMS = ("nchpta_open_trails",)
RESOURCES = [page_notice("nchpta_open_trails")]
