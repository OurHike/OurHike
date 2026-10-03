"""City of Duluth Open Data: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `duluth_parks_news`: City of Duluth Parks & Recreation news, one notice for the page (PageNotice).
  The parks department's table of press releases (1,370 rows from 2009, 137 of whose headlines
  contain 'clos'), one notice for the page. It is not scoped to closures, so per-item rows would
  publish every press release; the page's hash moves with any of them. Each row carries its own
  'UPDATED 09/26/2013'-style stamp and the page states none of its own, so the stated-date step is
  off (`date_pattern=None`) and the notice lands no date.

Not read: the ObstructionService MapServer the coverage audit named
(https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services/ObstructionService/MapServer/0),
whose path the inventory could not resolve (400 'Invalid URL'; its own skeptic found the second item
dead, 2022).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

City of Duluth Open Data: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

No feed was found. The city's `RoadClosures/` services are for streets.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: the `duluthmn.gov/parks/` news list carries trail
closures, e.g. "Portion of Chester Park Trail Closed Due to Washout" (2017-08-29); "Closed" appears
46 times on the page. `/parks/cancellations/` lists programme cancellations.

Its `where`: https://duluthmn.gov/parks/ https://data-duluthmn.opendata.arcgis.com/
https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("duluth_parks_news",)
RESOURCES = [page_notice("duluth_parks_news", date_pattern=None)]
