"""Ice Age Trail Alliance: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `iat_trail_communities`: Ice Age Trail Communities, 29 point features; places kind `town`.
- `iata_properties`: IATA Properties (fee-owned land), 44 polygon features; places kind `park`.
- `iata_land_ownership`: Land Ownership along the Ice Age Trail (public view), 194 polygon features; no
  places kind.

Not read: Land_Ownership_Preserve and the IATA_Lands hunting-regulation views in the same organization.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("iat_trail_communities", "iata_properties", "iata_land_ownership")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
