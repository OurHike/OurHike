"""Keystone Trails Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

A closure fact buried in map markers. A dlt resource would need a rule for which markers are hazards
(@unvalidated). On the A.T., `atc_trail_updates` covers it (1 Outerbridge bear warning). Skeptic,
2026-10-01: this is the only hazard marker in all 6 maps, so the "likely more" in Worth loading …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The Quehanna CalTopo map carries a marker titled "Corporation Dam (bridge out as of 2025)". There is '
        "no closures page: `news.html` is the president's letter, and `report-a-trail-issue.html` is a form.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://kta-hike.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
