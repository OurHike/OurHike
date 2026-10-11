"""Vermont Agency of Transportation (rail trails): warnings (decision 122's held load, here since VTrans's row;
closures.py says how this folder came to be).

- `vtrans_rail_trail_warnings`: `VT_Rail_Trails_Warning_View/FeatureServer/4`, 17 warnings, detours and work
  zones (2026-10-09), 2 of them active by isActive.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("vtrans_rail_trail_warnings",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
