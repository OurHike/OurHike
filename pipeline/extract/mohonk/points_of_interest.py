"""Mohonk Preserve: points of interest, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

Five points, hand-transcribable. OSM through `_shared/` may already hold them. That is unchecked.
Skeptic additions (Measured 2026-10-01): `/visit/camping/` (`modified` 2026-03-03) says "camping is
not permitted on Mohonk Preserve property". So there are no campsite POIs to find. The nearby …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No POI layer among the 24 services (each listed 2026-10-01). `mohonkpreserve.org/visit/trailheads/` "
        '(WP `modified` 2026-09-24): "Mohonk Preserve has five main trailheads", with addresses (Visitor '
        "Center, 3197 State Route 44/55, Gardiner) and hours, plus "
        "`wp-content/uploads/2021/05/Alternative_Routes_map.pdf`.",
    ),
    where=(
        "https://mohonkpreserve.org/visit/trailheads/",
        "https://mohonkpreserve.org/",
        "https://services8.arcgis.com/cQ05sucxF4UWabFF/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
