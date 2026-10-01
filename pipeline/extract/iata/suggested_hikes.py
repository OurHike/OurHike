"""Ice Age Trail Alliance: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

robots.txt disallows every page. The maintainer decides whether to ask IATA or skip these. The
StoryMaps are on `storymaps.arcgis.com`, which IATA's robots.txt does not cover.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Pages: `/SegmentTour`, `/explore/plan-hike/day-hikes/`, `/recommended-hikes/backpacking-trips/` (links"
        ' read from the homepage). ArcGIS StoryMap "Virtual Segment Hike" `722d9a6b22e04f838a5336a434a96c9d` '
        "(owner a personal ArcGIS account, public). (Corrected by skeptic: the id first written here, "
        '`722abdd62fa64d47b7ab0316f921ebb6`, is a Web Map titled "PNWT" owned by a personal ArcGIS account, not'
        ' IATA\'s StoryMap. The right id came from an ArcGIS search for "Virtual Segment Hike", which has '
        "exactly one result.) a personal ArcGIS account also owns the StoryMaps Ice Age Trail Communities …",
    ),
    where=(
        "https://storymaps.arcgis.com",
        "https://iceagetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
