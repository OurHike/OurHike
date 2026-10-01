"""Iditarod Historic Trail Alliance: warnings, published, and not landed (coverage audit 2026-10-01,
batch p10_persist).

avalanche.org: explicit_restriction. Its API root says "Please contact avalanche.org / American
Avalanche Associate for permission" (sic, "Associate"). Batched below. MOA layer: licenseInfo empty,
so none_stated. Its `EDITOR` field holds 1 distinct value, a person's name or account, not copied.
The …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "avalanche.org `https://api.avalanche.org/v2/public/products/map-layer/CNFAIC` (GeoJSON) holds 4 "
        "forecast zones: Chugach State Park, Seward and Lost Lake, Summit Lake, and Turnagain Pass and "
        'Girdwood. Those are the Seward-to-Eagle-River segments. Today every zone reads `danger` "no rating", '
        "`off_season` true. Fields include `danger_level`, `travel_advice` and `warning`. Municipality of "
        "Anchorage "
        "`https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services/AvalancheZones/FeatureServer/0` "
        '("Historic Avalanche Zones within MOA", item `9e39d70c7c434187b95a99c3a144cdb2`, 2026-08-25) holds …',
    ),
    where=(
        "https://api.avalanche.org/v2/public/products/map-layer/CNFAIC",
        "https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services/AvalancheZones/FeatureServer/0",
        "https://avalanche.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
