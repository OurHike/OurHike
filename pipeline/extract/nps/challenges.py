"""National Park Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

The Passport booklet is America's National Parks' (a partner). The stamp locations are NPS API data.
A candidate for #1780 — Let a club publish a challenge — places on its own trails that hikers opt
into and tag at camp — starting with the ATC's A.T. Summer Bucket List only once they are geocoded:
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'API `/passportstamplocations`: 1,092 (label, type, parks). The first was "A.G. Gaston Motel (Temporarily Closed)".',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://nps.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
