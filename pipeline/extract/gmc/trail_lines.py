"""Green Mountain Club: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The Long Trail north of Maine Junction is in no loaded row. `licenseInfo` is empty. The owner is not
on `_agol_accepted_owners`. The layer advertises Create/Update/Delete/Editing (see Terms).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services/TRAIL_MASTER/FeatureServer/0` "
        "(ArcGIS layer, owner `GMC_Special_Projects`): 403 polylines, last edit 2026-09-24. By TrailType: LT "
        "177 segments / 259.9 mi, ST 144 / 175.5 mi, AT-only 23 / 46.4 mi, SP 54 / 7.3 mi, OT 4 / 6.6 mi, MA 1 "
        "/ 3.9 mi. Fields include TrailName, MaintName, TrailType, AT, Length_mi, Source, Sourcedate. Also "
        "`MileMarkers_LT/FeatureServer/0` (259 points, field `Mile`). The A.T. overlap is already LOADED via "
        "`atc`.",
    ),
    where=(
        "https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services/TRAIL_MASTER/FeatureServer/0",
        "https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services/MileMarkers_LT/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
