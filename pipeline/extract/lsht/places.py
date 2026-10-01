"""Lone Star Hiking Trail Club: places, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The 14-trailhead table (directions, Google links). The guide's off-trail support list (accommodation, "
        "shuttle, resupply). The SHNF compartment numbers per section.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://lonestartrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
