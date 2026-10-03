"""Appalachian Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The Akey advisory is a water-source warning and belongs on that POI's card. That is not drought
(decision 2), but where it lands is for the maintainer to decide. The facility conditions were four
months stale on 2026-10-01. Skeptic spot-check: `/weather-trail-conditions/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'NET Massachusetts: "It is advised at this time to not use the water source at the Harold Akey tent '
        'site until further notice" (Section 3, West Springfield). The weather-trail-conditions page has dated '
        'condition text per facility, e.g. Highland Center "05/30/26 … snow, ice above 3000 ft". There are news'
        " posts such as `.../news/bear-canisters-required-pemigewasett/`.",
    ),
    where=("https://outdoors.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
