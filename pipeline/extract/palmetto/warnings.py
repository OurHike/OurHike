"""Palmetto Conservation Foundation: warnings, from the Palmetto Trail's hunting-season post, hourly (decision 53
phase B, 2026-10-03).

`palmetto_hunting_season` reads `/updates/post/hunting-season` as one PageNotice (extract/_notices.py),
read live under our agent on 2026-10-03 (robots.txt empty, no rules): the season runs late August to
early March, and hikers wear blaze orange. A standing seasonal warning; the post states no date, so the
row has none. Each passage's 'Trail on Hunting Grounds' field is a place attribute, not read here.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c7_regional_4), whose `checked` read: "`/updates/post/hunting-season` (2025-12-11): season late August
to early March, wear blaze orange, links to SC regulations."
"""

from extract._kinds import page_notice

CLAIMS = ("palmetto_hunting_season",)
RESOURCES = [page_notice("palmetto_hunting_season")]
