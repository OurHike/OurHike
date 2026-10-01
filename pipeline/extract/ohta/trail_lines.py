"""Ozark Highlands Trail Association: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c8_regional_5).

It is captioned "For illustrative purposes only", so it must not outrank the USFS line. The Lower
Buffalo bushwhack is not in USFS data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `usfs` → `usfs_trails`: `OZARK HIGHLANDS TRAIL`, 16 features, 132.50 mi (081002, 8 / 40.22; "
        "081003, 1 / 1.79; 081004, 4 / 64.36; 081005, 3 / 26.13). `nps_trails`: 3 BUFF features. Own geometry "
        "(AVAILABLE, not loaded): Google My Maps `mid=1T9D3RqcVbXKh8XFmVGrJFF7C6c7wH00`, exported as KML from "
        "`https://www.google.com/maps/d/kml?mid=1T9D3RqcVbXKh8XFmVGrJFF7C6c7wH00&forcekml=1`: 167,342 B, 5 "
        'LineStrings ("Boston Mountains", "OHT/BRT", "Lower Buffalo Bushwhack", "Sylamore", "Lake Norfork").',
    ),
    where=("https://www.google.com/maps/d/kml?mid=1T9D3RqcVbXKh8XFmVGrJFF7C6c7wH00&forcekml=1",),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
