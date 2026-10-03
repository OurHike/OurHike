"""U.S. Fish and Wildlife Service: the National Wildlife Refuge System's trail inventory,
FWS_HQ_Trails_Cycle_3_Public_View layer 1.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `usfws_trail_segments`: FWS HQ trail segments, National Wildlife Refuges (USFWS). 6,420 lines, keyed on `GlobalID`.

Not landed: layer 2, Trails_Info, a table of 2,982 trail-level rows without geometry (coverage audit),
which a staging model could join to the segments.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usfws_trail_segments",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
