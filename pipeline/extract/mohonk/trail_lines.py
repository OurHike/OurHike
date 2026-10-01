"""Mohonk Preserve's trails and carriage roads, `Mohonk_Preserve_Trails_and_Carriage_Roads/FeatureServer/0`.

304 polylines, last edited 2026-10-01, the day of the coverage audit (batch
b4_oprhp_mohonk_gatc), so the monthly refresh matters here. The Avenza map
is paid and is not a source.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mohonk_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
