-- Each trail an accepted publishers.json row names, and whether the
-- organization may put a challenge on it (CH02, CH03): publisher_scope()'s
-- last step. A trail is in scope when it is a string that at least one
-- published POI carries as its `trail_id`. A trail nothing is placed on can
-- hold no challenge place, and a trail id spelled differently from the POIs'
-- (`at` for `AT`) is exactly how that happens.
--
-- An organization whose every trail is refused keeps its accepted row with
-- no trail in scope, so its challenges drop as "trail 'AT' is not one 'atc'
-- publishes", which is then true, rather than as an unknown organization
-- (int_challenges__publishers keeps the row).
with publishers as (
    select * from {{ ref('int_challenges__publishers') }}
    where accepted
),

pois as (
    select * from {{ ref('int_challenges__published_pois') }}
),

carried as (
    select distinct trail_id
    from pois
    where trail_id is not null
),

listed as (
    select
        publisher_position,
        org,
        unnest(cast(cast(trails_json as json) as json[])) as trail_json,
        generate_subscripts(
            cast(cast(trails_json as json) as json[]), 1
        ) as trail_position
    from publishers
),

named as (
    select
        *,
        case
            when json_type(trail_json) = 'VARCHAR'
                then json_extract_string(trail_json, '$')
        end as trail
    from listed
)

select
    cast(named.publisher_position as varchar) || '.'
    || cast(named.trail_position as varchar) as publisher_trail_id,
    named.publisher_position,
    named.trail_position,
    named.org,
    named.trail,
    carried.trail_id is not null as in_scope,
    case
        when carried.trail_id is null
            then
                named.org || ': trail ' || {{ python_repr('named.trail_json') }}
                || ' is carried by no published POI'
    end as problem
from named
left join carried on named.trail = carried.trail_id
