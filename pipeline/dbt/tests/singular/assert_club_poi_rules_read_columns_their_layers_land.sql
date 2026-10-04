-- Every field the club_poi_types and layer_rules seeds name for one of
-- decision 54's wave 1 point layers is a column that layer landed. A rule
-- whose field is missing never fires: a planned trailhead, a staff residence
-- or a water type that is not water would reach the type map unread, and a
-- typo in a seed would look like a quiet layer. Read off the layer's own
-- rows (each row's `properties` keeps a null column as a null member), so a
-- layer with no rows is not judged. Fails by returning each (layer, field)
-- the layer did not land.
with landed as (
    select distinct
        source_key,
        unnest(json_keys(properties)) as field
    from {{ ref('int_points_of_interest__club_unioned') }}
),

layers as (
    select distinct source_key from landed
),

named as (
    select
        source_key,
        field
    from {{ ref('club_poi_types') }}
    where field is not null
    union distinct
    select
        source_key,
        field
    from {{ ref('layer_rules') }}
    where field is not null
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
