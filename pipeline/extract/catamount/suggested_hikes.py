"""Catamount Trail Association: suggested hikes, none: its sections are ski tours (decision 54 wave 4, section
K, 2026-10-04).

The Catamount Trail is a cross-country ski trail the length of Vermont: /ski-the-trail/ct-section-list/ divides it
into '31 sections that all make for reasonable day tours' on skis, each a page with a GeoPDF and a description. A
ski tour is not a suggested hike.

The note this replaces read, whole:

Catamount Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

These are ski tours, not hikes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 31 section pages under `/ski-the-trail/ct-section-list/`. Each has
a length, a difficulty, a GeoPDF and a "Written Description & Shuttle Directions" PDF.

Its `where`: https://catamounttrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://catamounttrail.org/ski-the-trail/ct-section-list/ (HTTP 200, 184,545 bytes, 2026-10-04T17:39:19Z): 31 section links, 'The full length of the Catamount Trail has been divided into 31 sections that all make for reasonable day tours'",
    ),
    where=("https://catamounttrail.org/ski-the-trail/ct-section-list/",),
    reason="not this type: ski tours, not hikes",
)
