"""Wisconsin DNR Open Data: photos, could not be told (coverage audit 2026-10-01, batch
b7_long_trails_states).

Still UNKNOWN. The DNR website's own media or photo pages and their terms remain unread.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The 282 hosted services were scanned by name, but not for photo layers specifically, and the website was not checked.",
        "Skeptic adds (Measured): a keyword scan of all 1,222 public items in org `Ul9AyFFeFTjf08DW` for photo "
        "terms found only aerial-photo (orthoimagery) services under `arcgis_image/DW_Imagery`, which are "
        "imagery and not photos of features. A web search for a WDNR Flickr account found only other people's "
        "accounts. Snapshot Wisconsin's trail-camera wildlife photos go to Zooniverse.",
    ),
    where=(
        "https://data-wi-dnr.opendata.arcgis.com/",
        "https://dnrmaps.wi.gov/arcgis/rest/services",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
