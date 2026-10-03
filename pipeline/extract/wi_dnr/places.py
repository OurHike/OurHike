"""Wisconsin DNR Open Data: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `wdnr_managed_properties`: DNR Managed Land Property Search Layer, 1,978 polygon features; places kind
  `park`.

LF_DNR_REC_OPPS_WTM_Ext/MapServer/14 answered HTTP 500 on 2026-10-03 and the service lists layers 1 to 4
only.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("wdnr_managed_properties",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
