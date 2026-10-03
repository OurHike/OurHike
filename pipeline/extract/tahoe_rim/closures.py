"""Tahoe Rim Trail Association: closures, from the current-trail-conditions page, hourly (decision 53 phase B,
2026-10-03).

`trta_trail_conditions` reads https://tahoerimtrail.org/current-trail-conditions/ (WordPress page 16) as
one PageNotice (extract/_notices.py), read live under our agent on 2026-10-03 after the site's
robots.txt (the path allowed, no Crawl-delay). Its date is the page's own 'Updated August 17, 2026', the
newest of its stamps (nine segments carry their own 'Last Updated: 6/24/26' to '7/7/26'); its
Last-Modified is the request time and is not trusted. The page has no <main> or <article>, so the
region is <body> (15,355 characters that day): Spooner backcountry construction closures, Watson Lake's
dispersed camping closing November 15, the bear-canister rule. Cloudflare's passive challenge-platform
script sits on the full 200 page and is not a wall.

The segments mix closures and warnings, so warnings.py shares this file. Each segment's 'Water Sources'
line is a water condition, not a warning (decision 2), and is left for the water path. The layers
`Camping_Prohibited/0` (12 polygons, 2016) and `Camping_Restrictions/0` (1, 2020) are standing rules,
not notices.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
b7_long_trails_states), whose `checked` named this page, per segment, 'Updated August 17, 2026'.
"""

from extract._kinds import page_notice

CLAIMS = ("trta_trail_conditions",)
RESOURCES = [page_notice("trta_trail_conditions")]
