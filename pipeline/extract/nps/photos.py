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
"""

from extract._content import nps_content

CLAIMS = ("nps_gallery_assets",)
RESOURCES = [nps_content(key) for key in CLAIMS]
