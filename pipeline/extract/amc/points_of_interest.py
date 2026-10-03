"""Appalachian Mountain Club: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

The A.T. shelters are already loaded via `atc` (`shelters`), so these need deduplication after
extract-load. Skeptic spot-check: `agol_wmnf_lodging/0` = 35 (2026-05-26) and `AMC_Destinations/0` =
61 (layer last edit 2025-01-21).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../agol_wmnf_lodging/FeatureServer/0`: 35: Campsite 20, Hut 8, Lodge 3, Cabin 2, Seasonal 2, with "
        "`How_to_Access`. Last edit 2026-05-26. `.../AMC_Destinations/FeatureServer/0`: 61: Tentsite 14, "
        "Shelter 12, Cabin 8, White Mountain Hut 8, Campsite 7, Lodge 7. `.../NET_POI_CT/FeatureServer/30`: 205"
        " (View 156, Shelter 7, Campsite 3; 2022). `NET_Parking_CT`: 64. `Trailheads_and_Parking_Lots`: 106. "
        "NET site `OvernightSites.geo_.json`: 10 (Shelter 4, Tentsite 3, Cabin 2, Group 1). "
        "`Parking.geo_.json`: 106.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://services9.arcgis.com/mxpFc8oFRyNIV03y/arcgis/rest/services",
        "https://outdoors.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
