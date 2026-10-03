"""TDEC's Tennessee State Parks hiking assets, campgrounds and campsites, and the Cumberland Trail's own trailheads, campsites and natural features.

Read live 2026-10-03 for decision 54's wave 1, on ArcGIS Online: the Tennessee State Parks layers on TDEC's
account (provider TDEC), the Cumberland Trail's on the CTSST account that the ctsst_* rows read as the
Cumberland Trail Conference's (provider CTC). tnstateparks.com, which the coverage audit found behind a
user-agent filter, was not fetched. The CTSST service's closure layers (Trail_Closures, Closures,
Public_Hazards_Closures) are notices, decision 53's, and not this file's.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "tn_state_parks_hiking_assets",
    "tn_state_parks_campgrounds",
    "tn_state_parks_campsites",
    "cumberland_trail_trailheads",
    "cumberland_trail_campsites",
    "cumberland_trail_natural_features",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
