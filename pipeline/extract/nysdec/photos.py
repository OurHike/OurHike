"""NYS DEC: photos, on Flickr and on an ArcGIS layer, and not landed (decision 54 wave 3, section C,
2026-10-04).

NEEDS A KEY OURHIKE DOES NOT HOLD: a photo's licence is per photo, and Flickr states it only through
its API's `license` field (flickr.people.getPublicPhotos with `extras=license`), which needs a
Flickr API key, issued by Flickr at https://www.flickr.com/services/apps/create/. No FLICKR_API_KEY
is in the extract's environment (checked 2026-10-04), so no Flickr reader is written; an account's
licence is never a photo's (the round brief's item 2). With a key, the reader reads it from the
environment and answers UNKNOWN without it, as NPS_API_KEY does (extract/_json_apis.py). DEC's own
pages sampled All Rights Reserved on every photo (75 of 75, the coverage audit), which a per-photo
read would record photo by photo. dop/dop_campground's Campsites layer (6,125 points, photo
attachments) is an ArcGIS layer with no sources.json row, wave 1's format, named in section C's
hand-back.

The note this replaces read, whole:

No openly licensed DEC photo was found; the layer photo fields mostly point at DEC's internal
drives.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) DEC's Flickr stream: 11,832 photos; pages 1, 2 and 10 (75 photos) all All Rights Reserved",
        "(the coverage audit, 2026-10-01) PHOTO_LINK on the land-asset layers: M:\\ drive paths; PHOTO_JSON: bare filenames",
        "(the coverage audit, 2026-10-01) dop/dop_campground/FeatureServer/0: campground sites with photo attachments, not lean-tos or trails",
    ),
    where=(
        "https://www.flickr.com/services/apps/create/",
        "https://www.flickr.com/photos/nysdec/",
        "https://gisservices.dec.ny.gov/arcgis/rest/services/dop/dop_campground/FeatureServer/0",
    ),
    terms="Flickr: All Rights Reserved on every photo sampled",
    reason="needs a key OurHike does not hold (Flickr's API, for each photo's own licence); the ArcGIS layer is wave 1's",
)
