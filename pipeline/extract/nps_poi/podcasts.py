"""National Park Service (points of interest): podcasts, drawn from nps/podcasts.py's
`nps_multimedia_audio` (decision 54 wave 3, section C, 2026-10-04).

NPS's audio list (`/multimedia/audio`) lands once, in nps/podcasts.py; NPS's list is read whole,
nationally, so this folder, NPS's other, writes no resource for the same list (decision 34).

The note this replaces read, whole:

National Park Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Audio tied to a place, which makes it the richest podcast source in this batch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/multimedia/audio` (section C, 2026-10-04): landed by nps/podcasts.py as nps_multimedia_audio, national.",
        "(the coverage audit, 2026-10-01) API `/multimedia/audio`: 5,173 items, with `durationMs`, `transcript`, `latitude`/`longitude`, `relatedParks`.",
    ),
    where=(
        "https://developer.nps.gov/api/v1/multimedia/audio",
        "https://nps.gov/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
