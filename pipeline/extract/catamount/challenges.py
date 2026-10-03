"""Catamount Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Pages. Skeptic find (M): two more pages, both modified 2025-01-05.
`/catamount-winter-challenge-series/` is a monthly social-media challenge with sponsor prizes, not
place-based. `/cta-events/vermont-backcountry-challenge/` is an event page. Neither changes the
verdict.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/ski-the-trail/end-to-enders/`: an end-to-end certificate, pin and mug. `/fkts-on-the-catamount-trail/`.",),
    where=("https://catamounttrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
