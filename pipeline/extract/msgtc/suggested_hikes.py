"""Monadnock-Sunapee Greenway Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Thin: a page with a handful of route recommendations, not section guides. The guidebook and Super
Map are still sold. "No hike descriptions online" was too strong.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.msgtc.org/faq/`: "Best Route up or down Mount Sunapee — We recommend taking the Summit '
        'Trail (also the SRK Trail) (2.1 miles)", "Best Route to Lucia\'s Lookout from Pillsbury State Park — We'
        ' recommend taking the Bear Pond Trail to the Greenway Trail north", plus the end-to-end length note '
        '("your hike will be about 53 miles overall").',
    ),
    where=("https://www.msgtc.org/faq/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
