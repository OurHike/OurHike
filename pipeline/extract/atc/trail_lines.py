"""ATC's line layers and its mile axis.

The centerline, side trails and treadway are ATC's own ANST layers. The half-mile
points are the A.T.'s mile axis, which the elevation calibration and every
mile-marker read are measured along (pipeline/ELT.md, "The folder contract").
All four are ArcGIS Online layers, so the change check is a 304 on the layer's
metadata.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("centerline", "side_trails", "at_treadway", "half_mile_points_from_springer")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
