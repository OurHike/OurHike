"""Texas Trail Tamers: points of interest, published by a steward with no club folder.

The points at McKinney Falls are Texas Parks and Wildlife's (Texas_State_Parks_Public_Areas), whose layer
carries its own restriction (decision 36: publish as non-commercial). TPWD has no folder among
trail_orgs.json's managing clubs, so it waits on decision 54's wave 6.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "the coverage audit's read (2026-10-01): Texas_State_Parks_Public_Areas/FeatureServer layers 0 to 3 "
        "under ParkName LIKE 'McKinney%': headquarters 1, buildings 13, campground areas 7, day-use areas 4; "
        "no water-source or trailhead layer",
        "the extract's folder list, 2026-10-03: no folder for TPWD, so no row is registered for it in this wave",
    ),
    where=("https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services/Texas_State_Parks_Public_Areas/FeatureServer",),
    reason="published by a steward with no club folder (TPWD); waits on decision 54's wave 6",
)
