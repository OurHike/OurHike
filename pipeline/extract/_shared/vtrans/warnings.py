"""Vermont Agency of Transportation (rail trails): warnings, held (decision 122; see closures.py beside this file).

- `vtrans_rail_trail_warnings`: `VT_Rail_Trails_Warning_View/FeatureServer/4`, 17 warnings, detours and work
  zones (2026-10-09), 2 of them active by isActive.
"""

from extract._kinds import arcgis_layer

TYPE = "warnings"
CLAIMS = ("vtrans_rail_trail_warnings",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
