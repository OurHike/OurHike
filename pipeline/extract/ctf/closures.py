"""Colorado Trail Foundation: closures, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

The My Map `mid` could not be read (403). With it, this would be KML like FMST's. Ask the CTF.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://coloradotrail.org/traveling-the-ct/alerts/`: "a custom Google map with Trail updates … major '
        'trail obstructions, reroutes, and planned closures". `https://coloradotrail.org/category/closures/` is'
        ' a WP category, so a WP feed at `/category/closures/feed/` is likely (R). Posts include "Partial Trail'
        ' Closure & Detour (Segment 8)". New for 2026: a text-alert system.',
    ),
    where=(
        "https://coloradotrail.org/traveling-the-ct/alerts/",
        "https://coloradotrail.org/category/closures/",
        "https://coloradotrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
