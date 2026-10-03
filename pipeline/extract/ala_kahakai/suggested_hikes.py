"""Ala Kahakai Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Guided events. The upcoming/past split was empty in the JSON, so the items need the collection API

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `/activities-and-events` collection, `itemCount` 76 (Squarespace `?format=json` answers 200). "
        '`NPSAPI/tours` alka 5, incl. "Puʻuhonua — 1871 Trail" (18 stops, 1–2 h)',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://alakahakaitrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
