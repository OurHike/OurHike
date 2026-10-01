"""Tahoe Rim Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

The per-segment "Water Sources" lines are water conditions, not warnings (decision 2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format page, the same one: snow, bugs, downed trees, and "As of January 1, 2024, bear proofing of all '
        'smellables… is required in all areas of the Tahoe Rim Trail."',
    ),
    where=(
        "https://services7.arcgis.com/NchnBpgTjegMVinZ/arcgis/rest/services",
        "https://tahoerimtrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
