"""Hoosier Hikers Council: closures, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

The feed's last item is 23 months old, so it can carry dated history but cannot say "no closures
now". For the Knobstone, the DNR page is the live source. (Skeptic correction, 2026-10-01: the two
DNR PDFs are not current. In the page's HTML both links sit inside an HTML comment ( …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WordPress category RSS `https://www.hoosierhikerscouncil.org/category/trail-conditions/feed/`: 6 "
        'items, newest 2023-11-14 ("Second Knobstone Trail Closure"), oldest 2018-01-29. The Tecumseh page has '
        "a reroute notice and `/assets/Tecumseh_Trail_Reroute_202206.pdf`. Upstream: IN DNR "
        "`https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/` links closure "
        "and reroute PDFs (`fo-Knobstone-Trail-closure.pdf`, `fo-Knobstone-Trail-reroute-112023.pdf`).",
    ),
    where=(
        "https://www.hoosierhikerscouncil.org/category/trail-conditions/feed/",
        "https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/",
        "https://hoosierhikerscouncil.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
