"""DEC's statewide hiking trails, the DEC Info Locator's layer 2.

An on-prem ArcGIS Server, and its registry row declares no maintained date
field, so the change check answers UNKNOWN and the layer is read whole every
monthly run (extract/_kinds.py, ArcgisLayer._onprem_check). The coverage audit
read `max(UPDATED)` 2026-09-16 on this layer (batch b3_nys_dec); declaring
`freshness.field: UPDATED` on the row would let unchanged months skip.
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("dec_hiking_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="dec_hiking_trails",
        copy=("https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services/DEC_Trails/FeatureServer/1",),
        confirmed=date(2026, 10, 1),
        checked=(
            "DEC's ArcGIS Online 'Hiking Trails' layer holds 5,292 polylines, the same count as dil_trails/2 "
            "(returnCountOnly on both, 2026-10-01); the on-prem layer is DEC's own and the one the registry holds",
        ),
    ),
)
