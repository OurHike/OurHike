"""Pacific Northwest Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

Symbols on an Illustrator map have no coordinates, so this is not a practical load. It is recorded
so that the dated note does not say "not published" when PNTA does publish it. The machine-readable
POIs live in FarOut, which is third-party and paid. Method note: the 29.9 MB overview PDF was …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'PDF only. `/pnta/maps/` (last modified 2026-05-27) links "View Overview Maps" at '
        "`/2024-section-maps-fvw/`, which 301s to "
        "`https://www.pnt.org/wp-content/uploads/2024/05/2024-Section-Maps-FVW.pdf` (29.9 MB, Adobe "
        'Illustrator, created 2024-05-03). Its text layer repeats the legend entries "Campground" and "Trail '
        'Town/ Resupply Point" on every sheet. The free 2026 Map Set (`/trail-map-download/`) is `MAPS '
        '2026.pdf` on Google Drive (`application/pdf`; not opened). `/pnta/maps/` describes it as "140 page set'
        ' of annually revised Strip Maps… detailed page notes which describe trail conditions" …',
    ),
    where=(
        "https://www.pnt.org/wp-content/uploads/2024/05/2024-Section-Maps-FVW.pdf",
        "https://pnt.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
