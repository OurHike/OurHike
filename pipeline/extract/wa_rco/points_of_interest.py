"""Washington RCO — State Trails Database: points of interest, published, and not landed (coverage
audit 2026-10-01, batch b7_long_trails_states).

Same service as the loaded line.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Same service, `/1` Trailheads: 202, with `restrooms`, `potable_water`, `parking_`; last edit "
        '2026-04-22. `Recreation_Provider_Inventory/0` "Camping and Trail Points": 2,377 (2021-10-06). The '
        "Washington Hometown layers (2019) include `Camping_point` 1,072 and `Trail_Hiking_point` 1,757.",
    ),
    where=("https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
