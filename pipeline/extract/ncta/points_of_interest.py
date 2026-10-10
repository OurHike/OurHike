"""NCTA's own point layer, the one beside the registered line: water, shelters, camping, parking and fords.

Read live 2026-10-03 for decision 54's wave 1; sources.json's ncta_points row has the counts, the
measured key and why `source` is never asked for. A ford is a hazard, not an amenity. The per-state
half-mile marker layers the coverage audit names are mile markers, not points of interest, and are
not extracted here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ncta_points",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
