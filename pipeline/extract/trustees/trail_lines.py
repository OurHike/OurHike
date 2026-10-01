"""The Trustees of Reservations: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

No vector trail layer from `TTOR_2`: searches for trail/trails/parking/amenities found only coastal,
grassland and Bay Circuit items. Skeptic (M, 2026-10-01): the PDF URL now 301s to
`wp-content/uploads/2024/07/notchview-trail-map.pdf` (1,576,956 B). Paging all 188 `TTOR_2` items
turns up the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Per-property trail-map PDFs, e.g. "
        '`https://thetrustees.org/wp-content/uploads/2020/07/Notchview-Trail-Map.pdf`, and "Notchview Mobile '
        'Map" via Avenza. Not LOADED via massgis (corrections 2 and 3).',
    ),
    where=("https://thetrustees.org/wp-content/uploads/2020/07/Notchview-Trail-Map.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
