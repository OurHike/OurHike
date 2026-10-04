"""National Park Service: photos, NPS's gallery assets read here, one row per photo (decision 54 wave
3, section C, 2026-10-04).

- `nps_gallery_assets`: NPS's gallery assets (`/multimedia/galleries/assets`) for the park codes
  nps_alerts' `park_codes` map lists, one manifest row per photo, never its pixels: 14,630 for the 27
  codes on 2026-10-04 (NPS's whole list held 206,685, so the API honours `parkCode`), about 30 pages
  a month. Each row carries its own `credit`, `copyright` and `constraintsInfo` ({constraint,
  grantingRights}), and THE LICENCE DIFFERS PHOTO BY PHOTO INSIDE ONE PARK'S LIST: of the first 500
  read, 12 carry 'Restrictions apply on use and/or reproduction (Copyrighted material)' and the rest
  'Public domain'. So a photo publishes on its own constraintsInfo or not at all, never on a park's
  or a gallery's. A national read is the maintainer's decision, as nps_alerts' is.

Each list is read by extract/_content.py's NpsContent, NpsAlerts' reader for another endpoint:
NPS_API_KEY from the environment as the gateway's `X-Api-Key` header, never in a URL, and without it
the change check raises Unavailable, so the table is withdrawn and never read as empty
(extract/_json_apis.py, 'THE KEY'). Every run reads the list (the API sends no validators), 500 a
page, stepping by the rows each page returns; the answer's own `total` is the count and the proof,
and a total that moves within one read or a repeated id raises. Rows land as NPS serves them, nested
lists as JSON, except the row's `person_fields`. dbt assigns each club folder its portion by each
row's own park list matched to nps_alerts' `park_codes` map (decision 34); the folders that draw on
these lists hold via notes naming them. The lane is the type's, monthly.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

National Park Service: photos, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Filter on `constraintsInfo.constraint == 'Public domain'`. Licence is per asset. Skeptic: not every
NPS-published photo is public domain. Some of NPS's Flickr photos are CC BY 2.0, so attribution has
to travel with them.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): API `/multimedia/galleries`: 10,507 galleries. All 3 sampled
had `constraintsInfo` "Public domain" (c9). My re-check got HTTP 429 (DEMO_KEY exhausted). NPGallery
was not opened. Skeptic adds (Measured 2026-10-01): NPS's Flickr account,
`https://www.flickr.com/photos/nationalparkservice/`, holds 513 photos. Of the 25 on its first page,
12 carry Flickr licence id 10 (Public Domain Mark) and 13 carry id 4 (CC BY 2.0). NPGallery
(`https://npgallery.nps.gov/`, "NPGallery Search") answers 200; no API was probed. A galleries retry
with DEMO_KEY returned no `total`.

Its `where`: https://www.flickr.com/photos/nationalparkservice/ https://npgallery.nps.gov/
https://nps.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import nps_content

CLAIMS = ("nps_gallery_assets",)
RESOURCES = [nps_content(key) for key in CLAIMS]
