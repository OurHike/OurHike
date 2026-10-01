"""Standing Stone Trail Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The Sweet 16 is a place-based challenge, the same shape as #1780 — Let a club publish a challenge —
places on its own trails that hikers opt into and tag at camp — starting with the ATC's A.T. Summer
Bucket List.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'End 2 End Challenge (`/end-to-end-hiking-information`; applications "reviewed each year between '
        'November 1 and December 31"; `/end-to-end-honorees`). Sweet 16 Trail Challenge '
        "(`/sweet-16-trail-challenge`): visit 16 named points and answer a question at each. Its printable form"
        " is `/_files/ugd/30a84d_fedad42032324cbdb3666b1adea3a866.pdf` (212,556 B, Last-Modified 2024-12-29).",
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
