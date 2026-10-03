"""Society for the Protection of NH Forests: places, extracted (decision 54, wave 1; live read 2026-10-03
under lib/user_agent.py's USER_AGENT).

- `spnhf_public_access_properties`: Forest Society public access properties, 173 polygon features;
  places kind `park`.

SAME_AS below: copies of a registered layer, noted and never loaded (decision 34).
"""

from datetime import date

from extract._contract import SameAs
from extract._kinds import arcgis_layer

CLAIMS = ("spnhf_public_access_properties",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
SAME_AS = (
    SameAs(
        original="spnhf_public_access_properties",
        copy=("https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/ES_Public_Access_WFL1/FeatureServer/4",),
        confirmed=date(2026, 10, 3),
        checked=(
            "A web-map copy holding a 'public_access_props selection' of 34 polygons (read 2026-10-03), edited "
            "2020-04-26, in the same organization as the registered layer's 173 'public_access_props', with the same "
            "columns (Acres, Ownership, LocalName, Recreation, Agency, Prop_link)",
            "18 of 18 of its LocalName values are among the full layer's: a selection drawn from an earlier version of "
            "the same properties, the full layer being the newest of the five (the CPW precedent, 'of which the newest is"
            " extracted')",
        ),
    ),
    SameAs(
        original="spnhf_public_access_properties",
        copy=("https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/ES_Public_Access_Map_WFL1/FeatureServer/5",),
        confirmed=date(2026, 10, 3),
        checked=(
            "A web-map copy holding a 'public_access_props selection' of 34 polygons (read 2026-10-03), edited "
            "2020-04-26, in the same organization as the registered layer's 173 'public_access_props', with the same "
            "columns (Acres, Ownership, LocalName, Recreation, Agency, Prop_link)",
            "18 of 18 of its LocalName values are among the full layer's: a selection drawn from an earlier version of "
            "the same properties, the full layer being the newest of the five (the CPW precedent, 'of which the newest is"
            " extracted')",
        ),
    ),
    SameAs(
        original="spnhf_public_access_properties",
        copy=(
            "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/Public_access_map_05282020_WFL1/FeatureServer/4",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "A web-map copy holding a 'public_access_props selection' of 31 polygons (read 2026-10-03), edited "
            "2020-05-28, in the same organization as the registered layer's 173 'public_access_props', with the same "
            "columns (Acres, Ownership, LocalName, Recreation, Agency, Prop_link)",
            "16 of 26 of its LocalName values are among the full layer's: a selection drawn from an earlier version of "
            "the same properties, the full layer being the newest of the five (the CPW precedent, 'of which the newest is"
            " extracted')",
        ),
    ),
    SameAs(
        original="spnhf_public_access_properties",
        copy=(
            "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/ES_Public_Access_Map_4272020_WFL1/FeatureServer/4",
        ),
        confirmed=date(2026, 10, 3),
        checked=(
            "A web-map copy holding a 'public_access_props selection' of 32 polygons (read 2026-10-03), edited "
            "2020-05-11, in the same organization as the registered layer's 173 'public_access_props', with the same "
            "columns (Acres, Ownership, LocalName, Recreation, Agency, Prop_link)",
            "17 of 26 of its LocalName values are among the full layer's: a selection drawn from an earlier version of "
            "the same properties, the full layer being the newest of the five (the CPW precedent, 'of which the newest is"
            " extracted')",
        ),
    ),
)
