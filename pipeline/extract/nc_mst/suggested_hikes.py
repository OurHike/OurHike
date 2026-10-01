"""NC Mountains-to-Sea Trail (state-published layer): suggested hikes, published, and not landed
(coverage audit 2026-10-01, batch b7_long_trails_states).

It is closer to trail attributes than to itineraries, and the blaze colour is useful.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page: 42 `/state-parks/<park>/trails` pages. Each holds a table of Trail Name, Blaze, Length, "
        'Difficulty and Use, with "Export Table Data" (Crowders Mountain: 11 trails).',
    ),
    where=("https://trails.nc.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
