"""Washington-Rochambeau Revolutionary Route Association: podcasts, audio only inside an app (decision 54 wave 5,
section K, 2026-10-04).

The STQRY app's 'seven hours of narrated stories and interviews' (its store listing) is audio inside an app, with no
feed or page this pipeline reads; an interview's guests are person fields in any case. No request sent today.

The note this replaces read, whole:

National Washington-Rochambeau Revolutionary Route Association: podcasts, published, and not landed
(coverage audit 2026-10-01, batch c11_nht).

App-only

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Own: the same app, "seven hours of narrated stories and
interviews" (store listing)

Its `where`: https://mapservices.nps.gov/arcgis/rest/services https://w3r-us.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) the STQRY app's listing: 'seven hours of narrated stories and interviews'",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://w3r-us.org/",),
    reason="not published as a feed or page: the audio lives in an app",
)
