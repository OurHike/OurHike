"""Maah Daah Hey Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No association show. Third party: Trails Worth Hiking Ep. 56 (2025-02-02); The Stable Cyclist.",
        'Skeptic: no podcast post type among the 10 in `wp-sitemap.xml`. The Apple directory searched by "Maah '
        "Daah Hey\" lists 14 shows, none of them the association's.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://mdhta.com/",
    ),
)
