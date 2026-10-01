"""No openly licensed DEC photo was found; the layer photo fields mostly point at DEC's internal drives."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "DEC's Flickr stream: 11,832 photos; pages 1, 2 and 10 (75 photos) all All Rights Reserved",
        "PHOTO_LINK on the land-asset layers: M:\\ drive paths; PHOTO_JSON: bare filenames",
        "dop/dop_campground/FeatureServer/0: campground sites with photo attachments, not lean-tos or trails",
    ),
    where=(
        "https://www.flickr.com/photos/nysdec/",
        "https://gisservices.dec.ny.gov/arcgis/rest/services/dop/dop_campground/FeatureServer/0",
    ),
    terms="Flickr: All Rights Reserved on every photo sampled",
)
