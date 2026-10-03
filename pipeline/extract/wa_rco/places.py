"""Washington RCO — State Trails Database: places, extracted (decision 54, wave 1; live read 2026-10-03
under lib/user_agent.py's USER_AGENT).

- `wa_public_lands_inventory`: WA Public Lands Inventory 2019, 32,593 polygon features; places kind
  `park`.
- `wa_recreation_areas`: Recreation Areas (Recreation Provider Inventory), 5,221 polygon features;
  places kind `park`.

SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("wa_public_lands_inventory", "wa_recreation_areas")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="wa_public_lands_inventory",
        copy=(
            "https://services2.arcgis.com/TGEC20q86HQAeMS6/arcgis/rest/services/Recreation_Provider_Inventory/FeatureServer/1",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "Layer 1 of the Recreation Provider Inventory view, 'WA Public Lands Inventory 2019': 32,593 rows, the "
            "registered layer's count, with two of its columns (Land_Owner, Owner), read 2026-10-03",
            "The view's source is the 'Mapped Inventory For 2023' service (its Service2Service relation), which "
            "republished the 2019 inventory beside the 2023 recreation areas",
        ),
    ),
)
