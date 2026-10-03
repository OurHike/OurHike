"""Superior Hiking Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Several of these are crossing hazards a hiker needs before setting out.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same page:",
        '"The McCarthy Creek bridge is out … wet crossing"',
        'Gooseberry River washout ("bushwack around")',
        "a failed structure near Middle Gooseberry",
        "logging",
        "high-water fords (Encampment, Split Rock, no bridge)",
        'encampments with broken glass; Also each `/trail-section/` page has a "Trail Alerts" block (seasonal wasp hazard).',
    ),
    where=("https://superiorhiking.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
