"""National Park Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Audio tied to a place, which makes it the richest podcast source in this batch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("API `/multimedia/audio`: 5,173 items, with `durationMs`, `transcript`, `latitude`/`longitude`, `relatedParks`.",),
    where=("https://nps.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
