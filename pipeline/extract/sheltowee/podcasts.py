"""Sheltowee Trace Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'No STA show. Third party: Hike, "Sheltowee Trace Trail with a named individual" (2024-08-06); Kentucky'
        " Arts & Culture (2022-10-21).",
        'Skeptic: no podcast URL among the 101 in `sitemap.xml`. The Apple directory searched by "Sheltowee" '
        "lists 15 shows, none of them the STA's.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://sheltoweetrace.org/",
    ),
)
