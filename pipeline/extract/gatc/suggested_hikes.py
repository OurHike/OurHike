"""Georgia Appalachian Trail Club: suggested hikes, published as dated club outings, and not landed
(decision 54 wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

The events feed (georgia-atclub.org/events/feed/) lists club outings, many members-only (the
coverage audit): dated group hikes. The trail guide is a page and a PDF, waves 4 and 5.

The note this replaces read, whole:

Georgia Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

The events are dated, and many are members-only. Publishing a members-only outing's meeting details
would go further than the club does, so they would be descriptions at most. The trail guide is the
durable content (SOURCE_SURVEY.md §5: "mile-by-mile").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "The lead's ruling of 2026-10-04 on events (quoted in the docstring); no request sent today.",
        '(the coverage audit, 2026-10-01) Events RSS `https://georgia-atclub.org/events/feed/`: club outings, e.g. "A.T. Series 2026: Tray Gap to Addis Gap" (2026-10-04, "Total mileage along the A.T. is 6.8 miles, then another 1.1 miles … 1,700 feet up, 2,400 down", marked Members-only). Also "Kennesaw Mountain Mid-Week Gentle Hike" and the Benton MacKaye Trail series. `/for-hikers/trail-guide/` and `Georgia-Appalachian-Trail-Guide.pdf` (41,000 bytes, 2023-04-12).',
    ),
    where=(
        "https://georgia-atclub.org/events/feed/",
        "https://georgia-atclub.org/",
    ),
    reason="not this type: dated group hikes, which the lead ruled are not suggested hikes (2026-10-04)",
)
