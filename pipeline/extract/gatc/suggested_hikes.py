"""Georgia Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

The events are dated, and many are members-only. Publishing a members-only outing's meeting details
would go further than the club does, so they would be descriptions at most. The trail guide is the
durable content (SOURCE_SURVEY.md §5: "mile-by-mile").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Events RSS `https://georgia-atclub.org/events/feed/`: club outings, e.g. "A.T. Series 2026: Tray Gap '
        'to Addis Gap" (2026-10-04, "Total mileage along the A.T. is 6.8 miles, then another 1.1 miles … 1,700 '
        'feet up, 2,400 down", marked Members-only). Also "Kennesaw Mountain Mid-Week Gentle Hike" and the '
        "Benton MacKaye Trail series. `/for-hikers/trail-guide/` and `Georgia-Appalachian-Trail-Guide.pdf` "
        "(41,000 bytes, 2023-04-12).",
    ),
    where=(
        "https://georgia-atclub.org/events/feed/",
        "https://georgia-atclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
