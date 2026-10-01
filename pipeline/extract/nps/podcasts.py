"""National Park Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Place-tagged audio is the hiker-relevant part. The RSS shows are programming.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/multimedia/audio`: 5,173 items with `durationMs`, `transcript`, `latitude`/`longitude`, "
        "`geometryPoiId`. The sample is oral-history clips (Ellis Island). Podcast RSS per show: "
        "`https://www.nps.gov/rss/podcasts/podcast_xml.cfm?id=6686775` (Park Postcards, GOGA: 9 items with "
        "enclosures, newest 2021-09-22). Listing pages are under `nps.gov/podcasts/` (search).",
    ),
    where=(
        "https://www.nps.gov/rss/podcasts/podcast_xml.cfm?id=6686775",
        "https://nps.gov/podcasts/",
        "https://nps.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
