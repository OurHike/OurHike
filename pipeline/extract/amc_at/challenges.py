"""AMC's A.T. committee: challenges, drawn from amc/challenges.py's `amc_four_thousand_footer_lists`
(decision 54 wave 5, section K, 2026-10-04).

The Four Thousand Footer Club the coverage audit names here is the Appalachian Mountain Club's own committee
(amc4000footer.org), and its lists land once, in amc/ (decision 34).

The note this replaces read, whole:

Appalachian Mountain Club (A.T. sections): challenges, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

A peak list in the same shape #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List is building. The peak
coordinates are not on the page (@unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): AMC Four Thousand Footer Club,
`https://www.amc4000footer.org/the-lists-we-recognize.html` (page). It recognises four lists: White
Mountain 4000-Footers, New England 4000-Footers, New England Hundred Highest, Northeast 111. Each
completion earns a certificate and a patch.

Its `where`: https://www.amc4000footer.org/the-lists-we-recognize.html

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "amc/challenges.py's amc_four_thousand_footer_lists reads https://www.amc4000footer.org/the-lists-we-recognize.html and its three list pages, 148 peaks, 2026-10-04",
    ),
    where=("https://www.amc4000footer.org/the-lists-we-recognize.html",),
    reason="drawn from amc/'s resource, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
