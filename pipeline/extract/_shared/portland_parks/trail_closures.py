"""Portland Parks & Recreation: the trail closures and delays page, hourly, extracted here once for every club
that draws on it (decision 53 phase B, 2026-10-03); fpc/ carries the `via` note naming it.

- `portland_parks_trail_closures`: https://www.portland.gov/parks/nature/trail-closures-and-delays,
  one PageNotice (extract/_notices.py).

Read live under our agent on 2026-10-03 after www.portland.gov's robots.txt, which asks `Crawl-delay: 2`
and disallows Drupal internals only; the reader keeps 2 s. The page states 'This page was updated on
September 28, 2026.', which lands as the row's date, and its <main> holds six sections: Springwater
Corridor Trail, Marquam Nature Park, Forest Park (the Ridge Trail parking area on NW Bridge Ave 'closed
indefinitely'), 'Wildwood Trail at mile 15.2 - Caution', River View Natural Area and Whitaker Ponds.
Its weak ETag and Last-Modified are both the render time (1791038341 is 2026-10-03 14:39:01 UTC, the
inventory), so neither is trusted. The Forest Park sections are FPC's; caution entries are warnings, split
in dbt (decision 7). No terms-of-use page exists (the footer's 'Terms and policies' covers ADA,
captioning, privacy and the site), so it publishes on decision 53's facts and a link.
"""

from extract._kinds import page_notice

TYPE = "closures"
CLAIMS = ("portland_parks_trail_closures",)
RESOURCES = [page_notice("portland_parks_trail_closures", crawl_delay=2)]
