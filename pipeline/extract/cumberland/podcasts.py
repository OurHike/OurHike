"""Cumberland Trail / Tennessee State Parks: podcasts, nothing published (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Verdict kept.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Checked site navigation and a web search for a TN State Parks podcast.",
        "Skeptic re-checked (Measured 2026-10-01): `sitemap.xml` has 1,095 URLs and none with podcast or audio "
        'in it. Apple\'s podcast directory, searched for "Tennessee State Parks", lists no show by TSP. A web '
        'search found only other people\'s shows: "The Parkside Podcast" (City of Chattanooga and Hamilton '
        'County parks, on WUTC), "State of the State Parks" (independent hosts), and guest episodes on "The '
        'State of Sustainability" and the a named individual Podcast.',
    ),
    where=("https://tnstateparks.com/",),
)
