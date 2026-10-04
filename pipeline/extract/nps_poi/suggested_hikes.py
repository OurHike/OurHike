"""National Park Service (points of interest): suggested hikes, drawn from nps/suggested_hikes.py's
`nps_things_to_do and nps_tours` (decision 54 wave 3, section C, 2026-10-04).

NPS's things to do (`/thingstodo`) and tours (`/tours`) lands once, in nps/suggested_hikes.py; NPS's
list is read whole, nationally, so this folder, NPS's other, writes no resource for the same list
(decision 34).

The note this replaces read, whole:

National Park Service: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

A `/thingstodo` item is a point per hike, not a route. `geometryPoiId` joins to the POI layer.
`/tours` is the nearest NPS has to an itinerary: an ordered list of stops with directions between
them. It has no line geometry.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/thingstodo` (section C, 2026-10-04): landed by nps/suggested_hikes.py as nps_things_to_do and nps_tours, national.",
        "(the coverage audit, 2026-10-01) API `/thingstodo`: 3,572 items; `q=hiking` gives 1,644. Each carries lat/long, `geometryPoiId`, season and pet descriptions.",
        '(the coverage audit, 2026-10-01) Skeptic adds (Measured 2026-10-01): API `/tours`, 717 items, of which `q=hike` matches 210. Each tour has `durationMin`/`durationMax`/`durationUnit` and an ordered `stops[]` list (`ordinal`, `directionsToNextStop`, `assetId`, `audioFileUrl`, `audioTranscript`). Example: "Japanese American Remembrance Trail", 2–4 h, 42 stops.',
    ),
    where=(
        "https://developer.nps.gov/api/v1/thingstodo",
        "https://developer.nps.gov/api/v1/tours",
        "https://nps.gov/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
