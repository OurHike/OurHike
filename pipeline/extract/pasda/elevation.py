"""PA DCNR's Maximum Elevations in Pennsylvania Counties, PASDA's `DCNR2/MapServer/3`: each county's high point.

67 points, the elevation in `Max_Elevat`, in feet: the layer names no unit,
and 3 points sit a median of 0.36 m from 3DEP read as feet and 1,553 m read as
metres (measured 2026-10-03; sources.json's `elevation_unit_comment`). An
on-prem layer with no date to fingerprint, so it is read whole each month.
Nothing reads it yet, and its `reaches_hikers` is false.

Not landed, and why: PAMAP's DEM, `imagery.pasda.psu.edu`'s
`PAMAP_DEM_mosaic/MapServer`, is a raster (its layers are Raster Layers, read
2026-10-03), and decision 35 lands no raster as data; 3DEP is the elevation
source for Pennsylvania.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("pasda_county_max_elevations",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
