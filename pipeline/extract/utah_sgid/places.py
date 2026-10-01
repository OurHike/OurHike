"""Utah UGRC — SGID Trails and Pathways: places, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`UtahMunicipalBoundaries/0`: 261 (2026-09-22). `state_park_boundaries_dissolved/0`: 47. "
        "`state_park_points_for_website/0`: 54, last edit 2026-10-01. Also `UtahWildernessAreas`, "
        "`CitiesTownsLocations`, `UtahGNISPlaceNames`.",
    ),
    where=("https://gis.utah.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
