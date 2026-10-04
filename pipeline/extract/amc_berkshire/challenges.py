"""AMC Berkshire: challenges, a dated anniversary challenge with no list of places, and not landed (decision 54
wave 5, section K, 2026-10-04).

The 150th Anniversary Challenge: 150 'miles worth' of any activities between 2026-01-01 and 2026-10-31, registered
by e-mail, for a patch. A tally of miles is not a list of places.

The note this replaces read, whole:

AMC Berkshire Chapter: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

It expires in 30 days and is activity-based, not place-based. Probably out of #1780's shape (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/150-anniversary-challenge.cgi` (page): 150 "miles worth" of
activities between 2026-01-01 and 2026-10-31, earning a patch. Registration is by email.

Its `where`: https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://amcberkshire.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /150-anniversary-challenge.cgi",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://amcberkshire.org/150-anniversary-challenge.cgi",),
    reason="not this type: a tally of activity miles in a dated window, no list of places",
)
