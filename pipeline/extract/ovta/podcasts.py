"""Overmountain Victory Trail Association: podcasts, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The most podcast-like audio in the batch. A trail-sectioned audio tour

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAPI/multimedia/audio` ovvi 38, an audio tour in 17 sections ("OVERVIEW: Section 13 of 17", "MAP: Section 13.1")',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://ovta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
