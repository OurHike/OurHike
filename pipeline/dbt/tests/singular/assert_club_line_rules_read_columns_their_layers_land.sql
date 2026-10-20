-- Every field the layer_rules seed names for a club trail-line layer is a
-- column that layer landed, as
-- assert_club_poi_rules_read_columns_their_layers_land holds for the point
-- layers. A rule whose field is missing reads every line as null: a
-- drop_where row then never fires, so a road draws as trail; a closed_where
-- row never fires, so a closed bridge draws with no closure on it; and a
-- keep_only_where row leaves every line out, so the whole trail vanishes.
-- NGPC's Cowboy Trail rows (road_status, condition) are the first rules to
-- read a status. Read off the layer's own rows (each row's `properties`
-- keeps a null column as a null member), so a layer with no rows is not
-- judged. Fails by returning each (layer, field) the layer did not land.
with landed as (
    select distinct
        source_key,
        unnest(json_keys(properties)) as field
    from {{ ref('int_trail_lines__unioned') }}
),

layers as (
    select distinct source_key from landed
),

named as (
    select distinct
        source_key,
        field
    from {{ ref('layer_rules') }}
    where
        field is not null
        and rule in ('drop_where', 'keep_only_where', 'closed_where')
)

select
    named.source_key,
    named.field
from named
inner join layers on named.source_key = layers.source_key
left join landed
    on
        named.source_key = landed.source_key
        and named.field = landed.field
where landed.field is null
