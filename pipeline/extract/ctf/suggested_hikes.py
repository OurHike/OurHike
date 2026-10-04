"""Colorado Trail Foundation: suggested hikes, behind a wall that refuses our agent (decision 54 wave 5,
section K, 2026-10-04).

coloradotrail.org answered HTTP 403 to lib/user_agent.py's agent on 2026-10-04, robots.txt included (read as no
rule, RFC 9309), as it did to decision 53's inventory (SiteDistrict's WAF, ctf/closures.py). The 33 segment pages
the coverage audit read sit behind it; nothing past it was asked, and no other agent was tried.

The note this replaces read, whole:

Colorado Trail Foundation: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same segment pages (33 segments; e.g. Segment 1, "16.8 miles
with 2,830 feet of elevation gain").

Its `where`: https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services
https://coloradotrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://coloradotrail.org/: HTTP 403 (2,337 bytes) to our agent, 2026-10-04; robots.txt also 403",),
    where=("https://coloradotrail.org/",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
