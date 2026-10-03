"""AMC Berkshire Chapter: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

Water source and capacity per site, on the A.T. sites ATC already places. Fires are banned at Upper
Goose Pond Cabin and Laurel Ridge. Skeptic, 2026-10-01: spot-check passed ("Wilbur Clearing … Small
shelter (capacity 6) … Water source on blue blaze trail"). The page now says "last updated: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.amc-wma.org/documents-more.cgi?id=13` "Campsites and Shelters on the Massachusetts A.T." '
        "(page, dated 04-Jan-2025). It runs north to south with shelter capacity, tent platforms and pads, "
        'privy, bear box and water source per site (e.g. "Wilbur Clearing … Small shelter (capacity 6) … Water '
        'source on blue blaze trail"). LOADED via atc (code 5): shelters 11, campsites 19, privies 18, parking '
        "31, viewpoints 45, bridges 30.",
    ),
    where=("https://www.amc-wma.org/documents-more.cgi?id=13",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
