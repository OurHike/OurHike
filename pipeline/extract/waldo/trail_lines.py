"""Waldo County Trails Coalition: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

The PDF has 3 geospatial-marker hits (`LGIDict`/`Measure`/`GPTS`), so it is probably georeferenced.
PDF is the lowest machine grade. ArcGIS has 0 results for "Hills to Sea".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.hillstosea.org/maps`: a full map plus 6 section PDFs, e.g. `/s/H2S_Section3_2025.pdf` "
        '(5,234,479 B, Illustrator, 1 page). The page also says "download section maps in the Avenza Maps phone'
        ' app".',
    ),
    where=("https://www.hillstosea.org/maps",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
