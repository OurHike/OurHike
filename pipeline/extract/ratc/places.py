"""Roanoke Appalachian Trail Club: places, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

ATC `parking` (22) and `communities` are LOADED. The overnight-parking rule per lot is what is
missing.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same Triple Crown page: a trailhead directory with overnight rules. Trout Creek (VA 620, "Overnight '
        'parking allowed"); Dragon\'s Tooth USFS lot ("Overnight parking is NOT allowed"); McAfee Knob NPS lot '
        '("DO NOT PARK ALONG 311 … ticketed and towed"); Catawba Sustainability Center (25 spaces, no '
        "overnight); Catawba Community Center (~15 spaces). Google Maps coordinates are in the links.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://ratc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
