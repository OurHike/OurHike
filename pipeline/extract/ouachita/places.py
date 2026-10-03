"""Friends of the Ouachita Trail: places, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Extract once and split the rows: access points go to trailheads (POIs), and parks go to places.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The navigation PDF above has 46 rows marked "Access point" (FR crossings, highways), and names the '
        "state parks (Talimena, Queen Wilhelmina, Pinnacle Mountain).",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://friendsoftheouachita.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
