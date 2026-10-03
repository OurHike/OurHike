"""Colorado Parks & Wildlife — COTREX: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `cpw_managed_properties`: CPW Managed Properties (public access only), 920 polygon features; places
  kind `park`.
- `cpw_property_centroids`: CPW All Properties Centroid, 1,056 point features; no places kind.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cpw_managed_properties", "cpw_property_centroids")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
