"""Bureau of Land Management: photos, arriving on the recreation sites layer, which
points_of_interest.py's `blm_recreation_sites` lands (decision 54 wave 3, section C, 2026-10-04).

BLM_Natl_Recreation/MapServer/3 carries `PHOTO_LINK` and `PHOTO_TEXT` on 783 rec sites (the coverage
audit's skeptic, 2026-10-01), each a link to a photo on BLM's Flickr, so the manifest rows arrive
with that layer, and this type shares it (never pixels: bytes never enter DuckDB). EACH PHOTO'S
LICENCE IS ON FLICKR, NOT ON THE LAYER: the account's first page sampled CC BY 4.0, and an account's
licence is never a photo's, so no photo of this layer publishes until a per-photo read lands one.
That read is Flickr's API, which needs a key OurHike does not hold (issued by Flickr at
https://www.flickr.com/services/apps/create/).

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Bureau of Land Management: photos, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Corrected by skeptic: BLM's Flickr photos are CC BY 4.0, not public domain, so attribution is
required and the credit must travel with each photo. Licence is still per photo, so read it at fetch
time.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `BLM_Natl_Recreation/MapServer/3`: 794 rec sites carry
`PHOTO_LINK` / `PHOTO_TEXT`, all sampled on `live.staticflickr.com` (BLM's Flickr). Skeptic
(Measured 2026-10-01): today 783 rec sites have a non-empty `PHOTO_LINK`. BLM's Flickr account
(`https://www.flickr.com/photos/mypubliclands/`, "Bureau of Land Management | Flickr", 8,816
photos): all 25 photos on its first page carry Flickr licence id 11. One photo page
(`/photos/mypubliclands/55114923117/`) links `creativecommons.org/licenses/by/4.0`, so id 11 is CC
BY 4.0.

Its `where`: https://www.flickr.com/photos/mypubliclands/
https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation/MapServer/3
https://live.staticflickr.com https://creativecommons.org/licenses/by/4.0 https://blm.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "points_of_interest"
