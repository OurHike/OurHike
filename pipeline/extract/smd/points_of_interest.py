"""Save Mount Diablo: points of interest, published by stewards with no club folder.

The points in SMD's area are East Bay Regional Park District's (drinking fountains, restrooms, park entrances)
and California State Parks' (campgrounds). Neither has a folder among trail_orgs.json's managing clubs, so
they wait on decision 54's wave 6, which adds folders for stewards like these. Nothing covers SMD's own
preserves.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "the coverage audit's read (2026-10-01): EBRPD's Drinking_Fountains/FeatureServer/6 (402 "
        "district-wide, 43 in SMD's box), Restrooms/FeatureServer/5 (272, 24) and "
        "Park_Entrances_PF/FeatureServer/4 (412, 52); CDPR's Campgrounds/FeatureServer/0 (531 statewide, 9 in"
        " the box)",
        "the extract's folder list, 2026-10-03: no folder for EBRPD or California State Parks, so no row is "
        "registered for them in this wave",
    ),
    where=(
        "https://services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Drinking_Fountains/FeatureServer/6",
        "https://services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/Campgrounds/FeatureServer/0",
    ),
    reason=("published by stewards with no club folder (EBRPD, California State Parks); waits on decision 54's wave 6"),
)
