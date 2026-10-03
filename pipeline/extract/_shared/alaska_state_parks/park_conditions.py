"""Alaska State Parks (the Division of Parks and Outdoor Recreation): the current park conditions page, hourly,
extracted here once for every club that draws on it (decision 53 phase B, 2026-10-03). The division has
no club folder (decision 18), so it lives in _shared/, and alaska_trails/ carries the `via` note naming
it (decision 34). Alaska State Parks manages 49 of the Alaska Long Trail's 286 segments (the inventory).

- `alaska_state_parks_conditions`: https://dnr.alaska.gov/parks/asp/curevnts.htm, one PageNotice
  (extract/_notices.py).

Read live under our agent on 2026-10-03 after dnr.alaska.gov's robots.txt: its `User-agent: *` group
ends `Disallow: /`, and `Allow: /parks` is the longer match for this path, so the page is allowed; no
Crawl-delay. The page states 'Last Update: September 30, 2026', which lands as the row's date, and its
<main> links 28 per-park PDF condition reports (denalireport.pdf, chugachreport.pdf and the rest), later
PDF candidates, not read. Its title is the region's first <h1>, the division's name. No terms are
linked from the page and none were read, so it publishes on decision 53's facts and a link.
"""

from extract._kinds import page_notice

TYPE = "closures"
CLAIMS = ("alaska_state_parks_conditions",)
RESOURCES = [page_notice("alaska_state_parks_conditions")]
