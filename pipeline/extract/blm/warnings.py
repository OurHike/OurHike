"""Bureau of Land Management: warnings, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `blm_shooting_points`: BLM recreational shooting points, `BLM_Qualified_Shooting/FeatureServer/0`.
  Its row says why phase C should hold it back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

And 25 notice sources read here (decision 53 phase B, 2026-10-03, pages, feeds and WordPress):

- `blm_press_<part>`, 13 sources, the 13 state and office press-release feeds
  https://www.blm.gov/info/RSS-feeds lists: one row an item (FeedNotices) each. One of the 13 state
  and office press-release feeds https://www.blm.gov/info/RSS-feeds lists. A press-release feed
  mixes news with closures and restrictions, so its items are warnings until decision 7's classifier
  reads them, and the feed is a window of its newest items, never the list of what is in force. Each
  item's dc:creator names a staff member, and 11 of the 13 feeds' descriptions name press contacts
  with an e-mail address or a phone number (measured 2026-10-03); FeedNotices lands neither.

- `blm_fire_restrictions_<part>`, 12 sources, the 12 state fire-restriction pages
  https://www.blm.gov/programs/fire/fire-restrictions links on blm.gov: one notice for the page
  (PageNotice) each. One of the 12 state fire-restriction pages
  https://www.blm.gov/programs/fire/fire-restrictions links on blm.gov (Nevada's goes off-site to
  nevadafireinfo.org and is not read). A fire restriction is a warning: it closes campfires and
  sometimes areas, never the footpath by itself. Read daily: one of 12 BLM fire-restriction pages on
  www.blm.gov, each kept 2 s from the last request to that host, so 12 an hour would spend about 24
  s of the hourly lane's sequential change checks; read daily until phase F measures the lane's
  budget (@unvalidated: a restriction can start inside the day it is not read).

Not wired: https://www.blm.gov/blog/rss, a blog rather than releases; and Nevada's fire
restrictions, which BLM's index sends off-site to https://www.nevadafireinfo.org/restrictions, a
host whose robots.txt and terms nobody has read. black_hills/ and iditarod/ draw on
`blm_press_montana_dakotas` and `blm_press_alaska`.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import arcgis_layer, feed_notices, page_notice

STATES = (
    "national_office",
    "alaska",
    "arizona",
    "california",
    "colorado",
    "eastern_states",
    "idaho",
    "montana_dakotas",
    "nevada",
    "new_mexico",
    "oregon_washington",
    "utah",
    "wyoming",
)
FIRE_PAGES = (
    "alaska_fire_service",
    "arizona",
    "california",
    "colorado",
    "idaho",
    "montana",
    "new_mexico",
    "north_dakota",
    "oregon_washington",
    "south_dakota",
    "utah",
    "wyoming",
)
FIRE_CADENCE_REASON = "one of 12 BLM fire-restriction pages on www.blm.gov, each kept 2 s from the last request to that host, so 12 an hour would spend about 24 s of the hourly lane's sequential change checks; read daily until phase F measures the lane's budget (@unvalidated: a restriction can start inside the day it is not read)"

CLAIMS = (
    "blm_shooting_points",
    *(f"blm_press_{part}" for part in STATES),
    *(f"blm_fire_restrictions_{part}" for part in FIRE_PAGES),
)
RESOURCES = [
    arcgis_layer("blm_shooting_points"),
    *(feed_notices(f"blm_press_{part}", trust_validators=True) for part in STATES),
    *(
        page_notice(f"blm_fire_restrictions_{part}", cadence_override="daily", cadence_reason=FIRE_CADENCE_REASON)
        for part in FIRE_PAGES
    ),
]
