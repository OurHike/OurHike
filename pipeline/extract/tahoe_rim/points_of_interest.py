"""TRTA's water sources, campgrounds, points of interest and newest trailhead layer.

Read live 2026-10-03 for decision 54's wave 1. NOT EXTRACTED, ON PURPOSE: TRTA's Vistas layer
(Vistas/FeatureServer/0, 297 points) is its Adopt-a-Vista dedication list. Its `Name` and `VISTA_DEDI`
name private individuals on most rows, memorials among them, so it is a roster rather than a map
layer and loads nowhere (pipeline/ELT.md, 'Who may publish', rule 8). The vistas themselves are
Type 'Vista' in tahoe_rim_points_of_interest. The two older trailhead layers are SAME_AS notes below.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = (
    "tahoe_rim_water_sources",
    "tahoe_rim_campgrounds",
    "tahoe_rim_points_of_interest",
    "tahoe_rim_trailheads",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="tahoe_rim_trailheads",
        copy=(
            "https://services7.arcgis.com/NchnBpgTjegMVinZ/arcgis/rest/services/Trailheads/FeatureServer/0",
            "https://services7.arcgis.com/NchnBpgTjegMVinZ/arcgis/rest/services/TRT_Trailheads/FeatureServer/0",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "three TRTA layers of the same 22 trailheads, Name unique on each (22 of 22): "
            "Trailheads_New_info_Tahoe_Rim_Trail last edited 2024-10-21, Trailheads 2023-02-21 and "
            "TRT_Trailheads 2017-03-26 (editingInfo, read 2026-10-03). The newest is extracted, as CPW's "
            "newest COTREX copy is; the older two carry other attribute columns (Accessible, Trailhead_Type) "
            "and were not compared row by row.",
        ),
    ),
)
