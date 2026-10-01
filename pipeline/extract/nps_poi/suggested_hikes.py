"""National Park Service: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

A `/thingstodo` item is a point per hike, not a route. `geometryPoiId` joins to the POI layer.
`/tours` is the nearest NPS has to an itinerary: an ordered list of stops with directions between
them. It has no line geometry.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "API `/thingstodo`: 3,572 items; `q=hiking` gives 1,644. Each carries lat/long, `geometryPoiId`, season"
        " and pet descriptions.",
        "Skeptic adds (Measured 2026-10-01): API `/tours`, 717 items, of which `q=hike` matches 210. Each tour "
        "has `durationMin`/`durationMax`/`durationUnit` and an ordered `stops[]` list (`ordinal`, "
        '`directionsToNextStop`, `assetId`, `audioFileUrl`, `audioTranscript`). Example: "Japanese American '
        'Remembrance Trail", 2–4 h, 42 stops.',
    ),
    where=("https://nps.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
