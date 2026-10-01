"""Standing Stone Trail Club: elevation, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

A PDF image, not data. USGS 3DEP is the data path.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Elevation Profiles", '
        "`https://www.standingstonetrail.org/_files/ugd/30a84d_c0fcf7a229a64ae5b1b65623fe6fb97b.pdf` (2,512,468"
        " B, Last-Modified 2022-12-18).",
    ),
    where=("https://www.standingstonetrail.org/_files/ugd/30a84d_c0fcf7a229a64ae5b1b65623fe6fb97b.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
