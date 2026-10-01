"""Standing Stone Trail Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page. That closure expired but is still linked, so dates must be honoured or it reads as live.
Skeptic, a second notice page with different years: `pages-sitemap.xml` also lists
`/trail-closure-notice` (title "\\\\\\Trail Relocation Notice"). Its "NOTICE 1" is the same
Sheepskin Hollow–Vanderbilts …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail-alerts`: "NOTICE: NO PARKING ANYTIME Little Augwick Creek Side of highway 522". '
        '`/copy-of-trail-relocation-notice`: "currently closed between Sheepskin Hollow Road and Vanderbilts '
        'Folly from October 1, 2022 to January 1, 2023".',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
