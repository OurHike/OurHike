"""City of Duluth Open Data: suggested hikes, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Events are not suggested hikes. If the plan ever takes events, the brochures are the source.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/parks/parks-trails/parks-listing/`, `/parkstrails-bikeways/` and `/trailsmap/` are park pages and "
        "maps. There is no hike list.",
        "Skeptic adds: a web search of the Parks & Recreation programme brochures (Fall 2025, Winter–Spring "
        "2026 PDFs on `duluthmn.gov/media/`) finds guided-hike events (a bi-weekly guided SHT series, Women "
        "Hike Duluth, a Glow Hike), not published hike descriptions.",
    ),
    where=(
        "https://duluthmn.gov/media/",
        "https://data-duluthmn.opendata.arcgis.com/",
    ),
)
