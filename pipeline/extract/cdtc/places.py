"""Continental Divide Trail Coalition: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `cdtc_gateway_communities`: CDT Gateway Communities 2026, 27 point features; places kind `town`.
- `cdtc_trail_sections`: CDT Trail Sections 2026, 128 polyline features; no places kind.

CDT_States (5 state polygons with Census population columns) is a copy of other publishers' boundaries;
Post_Office_view and CDTC_Mapsheets were not read.
SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("cdtc_gateway_communities", "cdtc_trail_sections")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="cdtc_trail_sections",
        copy=(
            "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/2026_CDT_Trail_Sections_2_view/FeatureServer/0",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "A second hosted view beside the registered one: 128 rows on each with the same (Section_Number, Mileage) "
            "pairs, the same columns, the same layer lastEditDate 2026-09-24 (read 2026-10-03)",
            "Only the registered view's item states a licence ('CC BY'); this one's licenseInfo is empty",
        ),
    ),
)
