"""National Mormon Trails Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/MOPI_NHT/0`: 1 line, 1:100k (2025-08-04). `nps_trails`: 0. Own `/maps/`, `/maps-2/` and "
        '`/interactive-map/` read "COMING SOON"',
    ),
    where=("https://mormontrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
