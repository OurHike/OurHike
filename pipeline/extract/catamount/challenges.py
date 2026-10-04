"""Catamount Trail Association: challenges, a completion award with no list of places, and not landed (decision 54 wave
5, section K, 2026-10-04).

/ski-the-trail/end-to-enders/: an end-to-end certificate, pin and mug for skiing the whole Catamount Trail, and
its fastest known times. A ski trail's end-to-end is neither a hike nor a list of places.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Catamount Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Pages. Skeptic find (M): two more pages, both modified 2025-01-05. `/catamount-winter-challenge-series/`
is a monthly social-media challenge with sponsor prizes, not place-based.
`/cta-events/vermont-backcountry-challenge/` is an event page. Neither changes the verdict.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/ski-the-trail/end-to-enders/`: an end-to-end certificate, pin
and mug. `/fkts-on-the-catamount-trail/`.

Its `where`: https://catamounttrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /ski-the-trail/end-to-enders/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://catamounttrail.org/ski-the-trail/end-to-enders/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
