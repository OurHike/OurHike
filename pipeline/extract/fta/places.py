"""Florida Trail Association: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `fta_gateway_communities`: Florida Trail gateway communities, 17 point features; places kind `town`.
- `fta_managed_conservation_areas`: Managed Conservation Areas along the Florida Trail, 103 polygon
  features; places kind `park`.

Gateway_Community_Businesses (129) is commercial listings, left out unless the maintainer wants
businesses (coverage audit).
SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("fta_gateway_communities", "fta_managed_conservation_areas")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="fta_gateway_communities",
        copy=("https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/Gateway_Communities/FeatureServer/0",),
        confirmed=date(2026, 10, 3),
        checked=(
            "The registered layer is a hosted view: its item's Service2Service relation names this feature service as its"
            " source (read 2026-10-03)",
            "17 rows on each, the same 17 GlobalID values, the same layer lastEditDate 2026-06-25",
        ),
    ),
)
