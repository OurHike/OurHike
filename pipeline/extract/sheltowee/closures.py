"""Sheltowee Trace Association: closures, from the alerts page, hourly (decision 53 phase B, 2026-10-03).

`sta_alerts` reads https://sheltoweetrace.org/alerts as one PageNotice (extract/_notices.py), read live
under our agent on 2026-10-03. Squarespace's robots.txt there allows /alerts and disallows its
`?format=json` twin for every agent, so the page is read and the JSON is not. The page holds 6 items:
the headline closure 'Spring Tornado Closes Trace From Highway 80 to Highway 192' (southbound miles
183.9 to 201.4, "a 2-year projected closing", the coverage audit), four 'Map and Route Updates' (the
Blue Herron Bridge closure, the Red River Suspension Bridge's high-water route) and 'Dogs on the
Trace'. The row lands the page's title, a hash of <main> and the link; the page states no date, and
its weak ETag is not trusted. The category RSS feeds are stale (newest 2021-03-28) and are not read.

The items are closures and warnings both, split in dbt (decision 7), so warnings.py shares this file.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c8_regional_5): "The page is live, but the RSS is not ... Read the page, not the feed."
"""

from extract._kinds import page_notice

CLAIMS = ("sta_alerts",)
RESOURCES = [page_notice("sta_alerts")]
