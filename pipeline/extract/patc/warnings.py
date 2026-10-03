"""Potomac Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

`Trail_Maintenance_Needs` advertises `Create,Delete,Update,Editing` to an anonymous request
(Measured). I did not test whether an anonymous write would succeed, and nobody should. A layer the
public may be able to write is not a statement by the steward, so do not load it without PATC's …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'hikethetuscarora.org section guides (22 sections on 7 pages): per-section "Advisory" lines, e.g. '
        '"Narrow shoulder along PA-34… extremely rocky tread… No camping in State Game Lands #170 and #230. '
        'Exercise caution in SGLs during hunting season". `/tuscarora-trail-sections` links a "Hunting '
        'Advisory" (WV DNR). `Trail_Maintenance_Needs/0`: 46 points (Trail_Problem: Other 32, Blowdown 6, Steps'
        " Needed 4, De-rocking 2, Wet Crossing 1), 2025-10-14",
    ),
    where=("https://hikethetuscarora.org",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
