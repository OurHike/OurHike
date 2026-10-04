"""Washington-Rochambeau Revolutionary Route Association: suggested hikes, published only in an app (decision 54
wave 5, section K, 2026-10-04).

The 'Washington Rochambeau Trail' itineraries live in the STQRY app (App Store id6467008765), 'themed itineraries
... approximately 70-100 high-potential sites' (the store listing, through a search); an app's content is not a
page this pipeline reads, and its sites are historic stops, not hikes. No request sent today.

The note this replaces read, whole:

National Washington-Rochambeau Revolutionary Route Association: suggested hikes, published, and not
landed (coverage audit 2026-10-01, batch c11_nht).

App-only

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Own: STQRY app "Washington Rochambeau Trail" (App Store
id6467008765), "themed itineraries … approximately 70-100 high-potential sites" (store listing via
search)

Its `where`: https://mapservices.nps.gov/arcgis/rest/services https://w3r-us.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("(the coverage audit, 2026-10-01) the STQRY app 'Washington Rochambeau Trail', App Store id6467008765",),
    where=("https://w3r-us.org/",),
    reason="not published as a page: an app's itineraries of historic sites",
)
