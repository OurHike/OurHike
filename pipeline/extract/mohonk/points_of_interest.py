"""Mohonk Preserve: points of interest, published with addresses and no coordinate, and not landed (decision 54,
wave 5, read live 2026-10-04).

"Mohonk Preserve has five main trailheads", each with a street address and hours (Visitor Center, 3197 State
Route 44/55, Gardiner), and no fix: a point is never looked up from an address, so nothing places them here.
Camping "is not permitted on Mohonk Preserve property" (/visit/camping/, the coverage audit's skeptic,
2026-10-01), so there are no campsites to find, and none of the preserve's 24 ArcGIS services holds a POI layer.
OSM, through `_shared/`, may hold the five; unchecked.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (`Crawl-delay: 10`, honoured), then /visit/trailheads/, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 125,693 bytes, the five trailheads with addresses and hours, one Google "
        "Maps link, no coordinate in the page; it links Alternative_Routes_map.pdf (2021-05), a map.",
        "the coverage audit (2026-10-01, batch b4_oprhp_mohonk_gatc): no POI layer among the 24 services, each listed that day.",
    ),
    where=("https://mohonkpreserve.org/visit/trailheads/", "https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services"),
    reason="published with addresses and no coordinate: a point is never geocoded from an address",
)
