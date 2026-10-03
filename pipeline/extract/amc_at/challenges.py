"""Appalachian Mountain Club (A.T. sections): challenges, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

A peak list in the same shape #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List is building. The
peak coordinates are not on the page (@unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "AMC Four Thousand Footer Club, `https://www.amc4000footer.org/the-lists-we-recognize.html` (page). It "
        "recognises four lists: White Mountain 4000-Footers, New England 4000-Footers, New England Hundred "
        "Highest, Northeast 111. Each completion earns a certificate and a patch.",
    ),
    where=("https://www.amc4000footer.org/the-lists-we-recognize.html",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
