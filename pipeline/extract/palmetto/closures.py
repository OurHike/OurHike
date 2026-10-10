"""Palmetto Conservation Foundation: closures, from the Palmetto Trail's current-closures post, hourly (decision
53 phase B, 2026-10-03).

`palmetto_trail_closures` reads the post as one PageNotice (extract/_notices.py), read live under our
agent on 2026-10-03; www.palmettotrail.org's robots.txt answered 200 with an empty body (no rules). The
post is edited in place, by region, with dated lines ('7/15/26: ENOREE PASSAGE ... still not 100% open'),
and states no update date of its own, so the row has none; its Last-Modified (2026-08-25 on that read)
is older than the request but is not trusted. The row lands the post's title, a hash of its <main> and
the link.

THE URL CARRIES A DATE (`trail-closures-updated-2-5-26`). If the club starts a new closures post, this
URL may stop answering or stop changing. A 404 raises every hour rather than reading the closures as
lifted (the reader's rule); a page that stops changing cannot be told from a quiet trail, which is
@unvalidated until somebody watches /updates for a newer closures post.

Each passage page's 'Trail Alerts' block (33 pages, the inventory) is a later per-page reader, not read.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c7_regional_4): "Page. The single post is edited in place." Its `checked` listed the Enoree Passage's
"hard stops" at miles 20.5, 24.5 and 30 (7/15/26), damage at Fort Jackson (8/11/26), and a Peak to
Prosperity section closing from October 19.
"""

from extract._kinds import page_notice

CLAIMS = ("palmetto_trail_closures",)
RESOURCES = [page_notice("palmetto_trail_closures")]
