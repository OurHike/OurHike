{{ config(materialized='table') }}
-- A table: the radius check is this family's one heavy step, and three
-- models and their tests read the result.
--
-- One row per item of each challenge file int_challenges__files passes,
-- checked as lib/challenges.py's resolve_challenge() and resolve_item() do
-- (CH01, CH03-CH10). `problem` is the first refusal, in the Python's order
-- (the `resolved` CTE); where it is null, `published_item` publishes. A
-- repeated id loses to the first, since tags are keyed by item id, even
-- when the first is refused.
--
-- A place (`place`, each of `places_all`, a `section_walked` end) must be a
-- published POI on the challenge's trail with a mile and a coordinate, and
-- publishes that POI's name, mile, lat and lon, rounded as _place() rounds
-- them. One bad place refuses a whole `places_all` item.
--
-- The radius check (CH04), for `place` and `places_all` places not marked
-- `off_trail`: the smaller of two challenges_haversine_m() distances, to
-- the closest point on the nearest centerline chain (ST_ClosestPoint in
-- EPSG:5070) and to the nearest vertex within 0.1 degree (all that today's
-- trail_distance_index() measures), must not exceed the radius. Reasoned:
-- both points lie on the line, so neither undershoots the true distance
-- and the smaller never exceeds today's; this admits places a gap between
-- vertices refused, and none outside their radius (pipeline/ELT.md's
-- known-difference row). EPSG:5070 metres do not decide, because they vary
-- with bearing (measured 2026-10-02 at 41 N 74 W: a 30.0 m pair read
-- 29.83 m east-west, 30.21 m north-south), enough to admit a place 0.6%
-- past its radius. The refusal prints the distance, where the Python said
-- "more than a grid cell". With no centerline (CH13) the check is skipped,
-- and the warn test
-- challenges_distance_check_has_a_centerline_to_measure_against says so.
--
-- Sealed titles (CH07): a mystery with a title and a reveal_on publishes
-- `sealed_title` (base64) and a null `title` through the reveal_on day,
-- against var challenges_build_date (default: today in UTC).
--
-- Stricter than the Python on purpose: an id ending in a newline is
-- refused (challenges_id_ok() says why; tests/test_dbt_challenges_parity.py
-- lists it).
with challenge_files as (
    select * from {{ ref('int_challenges__files') }}
    where misplaced_problem is null and challenge_problem is null
),

pois as (
    select * from {{ ref('int_challenges__published_pois') }}
),

centerline as (
    select * from {{ ref('int_challenges__centerline') }}
),

publishers as (
    select * from {{ ref('int_challenges__publishers') }}
    where accepted
),

-- lib/poi_schema.py's POI_TYPES that at least one published POI carries
-- (build_output()'s `published_types`): `trailhead` is declared but the ATC
-- publishes none, so an item asking for one could never be tagged.
published_types as (
    select
        coalesce(
            list(distinct poi_type), cast([] as varchar[])
        ) as poi_types
    from pois
    where list_contains({{ var('challenges_poi_types') }}, poi_type)
),

known_orgs as (
    select coalesce(list(org), cast([] as varchar[])) as orgs
    from publishers
),

-- The var is read inline, without a Jinja `if` or `set`, because SQLFluff
-- renders the whole model again for each (measured 2026-10-02, sqlfluff
-- 4.3.0: an `if` here made three renderings, a `set` two). A var that is
-- not a date fails the cast rather than falling back.
build as (
    select
        coalesce(
            cast(
                nullif('{{ var("challenges_build_date") or "" }}', '') as date
            ),
            cast(timezone('UTC', now()) as date)
        ) as build_date
),

items as (
    select
        challenge_file_key,
        trail,
        cast(cast(section_ids as json) as varchar[]) as section_ids,
        unnest(cast(cast(items_json as json) as json[])) as item_json,
        generate_subscripts(cast(cast(items_json as json) as json[]), 1)
            as item_position
    from challenge_files
),

fields as (
    select
        *,
        coalesce(json_type(item_json), 'NULL') as item_type,
        json_extract(item_json, '$.id') as item_id_json,
        json_extract(item_json, '$.section') as section_json,
        json_extract(item_json, '$.mystery') as mystery_json,
        json_extract(item_json, '$.mystery.number') as mystery_number_json,
        json_extract(item_json, '$.mystery.reveal_on') as reveal_on_json,
        json_extract(item_json, '$.title') as title_json,
        json_extract(item_json, '$.note') as note_json,
        json_extract(item_json, '$.note_by') as note_by_json,
        json_extract(item_json, '$.photo') as photo_json,
        json_extract(item_json, '$.match') as match_json,
        json_extract(item_json, '$.match.kind') as kind_json,
        json_extract(item_json, '$.match.radius_m') as radius_json,
        json_extract(item_json, '$.match.pois') as pois_json,
        json_extract(item_json, '$.match.type') as poi_type_json,
        json_extract(item_json, '$.match.off_trail') as off_trail_json,
        json_extract(item_json, '$.match.value') as value_json,
        json_extract(item_json, '$.match.min_fraction') as fraction_json,
        json_extract(item_json, '$.match.org') as workday_org_json,
        -- Each value a message quotes, as Python's repr() prints it, once.
        {{ python_repr("json_extract(item_json, '$.section')") }}
            as section_repr,
        {{ python_repr("json_extract(item_json, '$.match.kind')") }}
            as kind_repr,
        {{ python_repr("json_extract(item_json, '$.match.type')") }}
            as poi_type_repr,
        {{ python_repr("json_extract(item_json, '$.match.org')") }}
            as workday_org_repr
    from items
),

-- Each field's type and text, once, for the checks and the published item.
typed as (
    select
        *,
        coalesce(json_type(match_json), 'NULL') as match_type,
        coalesce(json_type(mystery_json), 'NULL') as mystery_type,
        json_extract_string(item_id_json, '$') as item_id_text,
        case
            when json_type(kind_json) = 'VARCHAR'
                then json_extract_string(kind_json, '$')
        end as kind_text,
        case
            when json_type(section_json) = 'VARCHAR'
                then json_extract_string(section_json, '$')
        end as section_text,
        case
            when json_type(poi_type_json) = 'VARCHAR'
                then json_extract_string(poi_type_json, '$')
        end as poi_type_text,
        case
            when json_type(workday_org_json) = 'VARCHAR'
                then json_extract_string(workday_org_json, '$')
        end as workday_org_text,
        case
            when json_type(reveal_on_json) = 'VARCHAR'
                then json_extract_string(reveal_on_json, '$')
        end as reveal_on_text,
        coalesce(json_type(mystery_number_json), 'NULL')
        in ('BIGINT', 'UBIGINT') as mystery_number_is_whole,
        try_cast(mystery_number_json as hugeint) as mystery_number,
        coalesce(json_type(reveal_on_json), 'NULL') != 'NULL'
            as reveal_on_given,
        {{ challenges_date_ok('reveal_on_json') }} as reveal_on_ok,
        coalesce(json_type(radius_json), 'NULL')
        in ('BIGINT', 'UBIGINT', 'DOUBLE') as radius_is_number,
        coalesce(json_type(pois_json), 'NULL') = 'ARRAY'
        and json_array_length(pois_json) >= 2 as names_two_pois,
        coalesce(json_type(off_trail_json), 'NULL') as off_trail_type,
        -- A place kind's, and poi_type's, `off_trail` is true only when it
        -- is JSON true.
        coalesce(
            json_type(off_trail_json) = 'BOOLEAN'
            and json_extract_string(off_trail_json, '$') = 'true',
            false
        ) as place_off_trail,
        coalesce(
            json_type(value_json) in ('BIGINT', 'UBIGINT', 'DOUBLE')
            and try_cast(value_json as double) > 0,
            false
        ) as value_ok,
        coalesce(
            json_type(fraction_json) in ('BIGINT', 'UBIGINT', 'DOUBLE')
            and try_cast(fraction_json as double) > 0
            and try_cast(fraction_json as double) <= 1,
            false
        ) as fraction_ok,
        coalesce(
            try_cast(fraction_json as double),
            cast({{ var('challenges_default_min_fraction') }} as double)
        ) as min_fraction,
        {{ challenges_text('title_json') }} as title,
        {{ challenges_text('note_json') }} as note_text,
        {{ challenges_text('note_by_json') }} as note_by_text,
        {{ challenges_https_ok('photo_json') }} as photo_ok,
        {{ challenges_https('photo_json') }} as photo_url
    from fields
),

kinds as (
    select
        *,
        item_type = 'OBJECT' and {{ challenges_id_ok('item_id_json') }}
            as id_ok,
        case
            when
                match_type = 'OBJECT'
                and list_contains(
                    {{ var('challenges_match_kinds') }}, kind_text
                )
                then kind_text
        end as kind,
        coalesce(list_contains(section_ids, section_text), false)
            as section_declared,
        case
            when reveal_on_given then try_cast(reveal_on_text as date)
        end as reveal_on_date
    from typed
),

-- The radius a place kind or poi_type is held to: the match's own, else the
-- kind's default; then the bounds, then Python's round() to a whole metre.
radii as (
    select
        *,
        case kind
            when 'place'
                then {{ var('challenges_default_radius_m_place') }}
            when 'places_all'
                then {{ var('challenges_default_radius_m_places_all') }}
            when 'poi_type'
                then {{ var('challenges_default_radius_m_poi_type') }}
        end as default_radius_m
    from kinds
),

radius_checked as (
    select
        *,
        case
            when radius_json is null then cast(default_radius_m as double)
            when radius_is_number then cast(radius_json as double)
        end as radius_raw,
        case
            when radius_json is not null and not radius_is_number
                then 'radius_m is not a number'
            when
                radius_json is not null
                and not cast(radius_json as double)
                between {{ var('challenges_min_radius_m') }}
                and {{ var('challenges_max_radius_m') }}
                then
                    'radius_m ' || {{ python_plain_repr('radius_json') }}
                    || ' is outside '
                    || '{{ var("challenges_min_radius_m") }}-'
                    || '{{ var("challenges_max_radius_m") }} m'
        end as radius_problem
    from radii
),

matches as (
    select
        *,
        cast(printf('%.0f', radius_raw) as integer) as radius_m
    from radius_checked
),

-- Every place an item names, in order: a place's `poi`, each of
-- places_all's `pois`, and a walked section's two ends.
place_refs as (
    select
        challenge_file_key,
        item_position,
        1 as place_position,
        '' as end_label,
        json_extract(match_json, '$.poi') as poi_json
    from matches
    where kind = 'place'
    union all
    select
        challenge_file_key,
        item_position,
        generate_subscripts(cast(pois_json as json[]), 1) as place_position,
        '' as end_label,
        unnest(cast(pois_json as json[])) as poi_json
    from matches
    where kind = 'places_all' and json_type(pois_json) = 'ARRAY'
    union all
    select
        challenge_file_key,
        item_position,
        1 as place_position,
        'from_poi ' as end_label,
        json_extract(match_json, '$.from_poi') as poi_json
    from matches
    where kind = 'section_walked'
    union all
    select
        challenge_file_key,
        item_position,
        2 as place_position,
        'to_poi ' as end_label,
        json_extract(match_json, '$.to_poi') as poi_json
    from matches
    where kind = 'section_walked'
),

places as (
    select
        place_refs.*,
        matches.kind,
        matches.trail,
        matches.radius_m,
        matches.place_off_trail,
        -- The places the radius check measures: a place kind's, not
        -- off_trail.
        matches.kind in ('place', 'places_all')
        and not matches.place_off_trail as is_measured,
        case
            when
                json_type(place_refs.poi_json) = 'VARCHAR'
                and json_extract_string(place_refs.poi_json, '$') != ''
                then json_extract_string(place_refs.poi_json, '$')
        end as poi_id,
        {{ python_repr('place_refs.poi_json') }} as poi_repr,
        coalesce({{ python_str_repr('pois.trail_id') }}, 'None')
            as poi_trail_repr,
        {{ python_str_repr('matches.trail') }} as trail_repr,
        pois.poi_id as published_poi_id,
        pois.trail_id,
        {{ python_strip("coalesce(pois.name, '')") }} as poi_name,
        {{ python_strip("coalesce(pois.poi_type, '')") }} as poi_type,
        pois.mile,
        pois.lat,
        pois.lon
    from place_refs
    inner join matches
        on
            place_refs.challenge_file_key = matches.challenge_file_key
            and place_refs.item_position = matches.item_position
    left join pois
        on
            json_type(place_refs.poi_json) = 'VARCHAR'
            and json_extract_string(place_refs.poi_json, '$') = pois.poi_id
),

-- Each POI the radius check measures, published with a coordinate. Measured
-- only where a centerline exists.
measured_pois as (
    select distinct
        published_poi_id as poi_id,
        lon,
        lat
    from places
    where
        is_measured
        and published_poi_id is not null
        and lat is not null
        and lon is not null
),

measured as (
    select
        poi_id,
        lon,
        lat,
        st_transform(
            st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as point_5070
    from measured_pois
),

chains as (
    select
        trail_line_id,
        st_geomfromgeojson(geom_geojson) as geom
    from centerline
),

chains_5070 as (
    select
        trail_line_id,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
            as geom_5070
    from chains
),

vertices as (
    select
        st_x(struct_extract(vertex, 'geom')) as vertex_lon,
        st_y(struct_extract(vertex, 'geom')) as vertex_lat
    from (
        select unnest(st_dump(st_points(geom))) as vertex
        from chains
    ) as dumped
),

nearest_chain as (
    select
        measured.poi_id,
        arg_min(
            chains_5070.trail_line_id,
            st_distance(measured.point_5070, chains_5070.geom_5070)
        ) as trail_line_id
    from measured
    cross join chains_5070
    group by measured.poi_id
),

closest_points as (
    select
        measured.poi_id,
        st_transform(
            st_closestpoint(chains_5070.geom_5070, measured.point_5070),
            'EPSG:5070', 'EPSG:4326', always_xy := true
        ) as closest
    from measured
    inner join nearest_chain on measured.poi_id = nearest_chain.poi_id
    inner join chains_5070
        on nearest_chain.trail_line_id = chains_5070.trail_line_id
),

nearest_vertex as (
    select
        measured.poi_id,
        min(
            {{ challenges_haversine_m(
                'measured.lon', 'measured.lat',
                'vertices.vertex_lon', 'vertices.vertex_lat'
            ) }}
        ) as vertex_m
    from measured
    inner join vertices
        on
            abs(vertices.vertex_lon - measured.lon) <= 0.1
            and abs(vertices.vertex_lat - measured.lat) <= 0.1
    group by measured.poi_id
),

distances as (
    select
        measured.poi_id,
        least(
            {{ challenges_haversine_m(
                'measured.lon', 'measured.lat',
                'st_x(closest_points.closest)', 'st_y(closest_points.closest)'
            ) }},
            nearest_vertex.vertex_m
        ) as distance_m
    from measured
    inner join closest_points on measured.poi_id = closest_points.poi_id
    left join nearest_vertex on measured.poi_id = nearest_vertex.poi_id
),

place_checks as (
    select
        places.*,
        -- Only where this item measures it: the same POI may be measured for
        -- another item while this one is off_trail or a walked section's end.
        case when places.is_measured then distances.distance_m end
            as distance_m,
        places.end_label || case
            when places.poi_id is null then 'names no poi'
            when places.published_poi_id is null
                then 'poi ' || places.poi_id || ' is not in the published POIs'
            when not coalesce(places.trail_id = places.trail, false)
                then
                    'poi ' || places.poi_id || ' is on trail '
                    || places.poi_trail_repr || ', not ' || places.trail_repr
            when places.mile is null
                then 'poi ' || places.poi_id || ' has no published mile'
            when places.lat is null or places.lon is null
                then 'poi ' || places.poi_id || ' has no coordinate'
            when
                places.is_measured
                and distances.distance_m > places.radius_m
                then
                    'poi ' || places.poi_id || ' is '
                    || printf('%.0f', distances.distance_m)
                    || ' m from the trail, past its ' || places.radius_m
                    || ' m radius - mark the match off_trail if reaching it'
                    || ' means leaving the trail'
        end as place_problem,
        -- places_all's `len(set(map(str, ids))) != len(ids)`: two places the
        -- same once each is printed as str().
        {{ python_str('places.poi_json', 'places.poi_repr') }} as poi_str,
        {{ python_round('places.mile', 3) }} as place_mile,
        json_object(
            'poi', places.poi_id,
            'name', places.poi_name,
            'poi_type', places.poi_type,
            'mile', {{ python_round('places.mile', 3) }},
            'lat', {{ python_round('places.lat', 6) }},
            'lon', {{ python_round('places.lon', 6) }}
        ) as published_place
    from places
    left join distances on places.published_poi_id = distances.poi_id
),

item_places as (
    select
        challenge_file_key,
        item_position,
        arg_min(place_problem, place_position)
        filter (where place_problem is not null) as place_problem,
        count(*) as place_count,
        count(distinct poi_str) as distinct_places,
        to_json(list(published_place order by place_position))
            as published_places,
        cast(
            to_json(
                list(
                    case
                        when distance_m is not null
                            then printf('%.3f', distance_m)
                    end
                    order by place_position
                )
            ) as varchar
        ) as place_distances,
        arg_min(place_mile, place_position) as from_end_mile,
        arg_max(place_mile, place_position) as to_end_mile,
        arg_min(poi_name, place_position) as from_end_name,
        arg_max(poi_name, place_position) as to_end_name
    from place_checks
    group by challenge_file_key, item_position
),

-- A walked section's ends in mile order, as it publishes them.
item_ends as (
    select
        *,
        least(from_end_mile, to_end_mile) as low_mile,
        greatest(from_end_mile, to_end_mile) as high_mile,
        case
            when from_end_mile <= to_end_mile then from_end_name
            else to_end_name
        end as low_name,
        case
            when from_end_mile <= to_end_mile then to_end_name
            else from_end_name
        end as high_name
    from item_places
),

repeats as (
    select
        challenge_file_key,
        item_position,
        row_number() over (
            partition by challenge_file_key, item_id_text
            order by item_position
        ) > 1 as is_repeat
    from kinds
    where id_ok
),

checked as (
    select
        matches.*,
        item_ends.place_problem,
        item_ends.place_count,
        item_ends.distinct_places,
        item_ends.published_places,
        item_ends.place_distances,
        item_ends.from_end_mile,
        item_ends.to_end_mile,
        item_ends.low_mile,
        item_ends.high_mile,
        item_ends.low_name,
        item_ends.high_name,
        coalesce(repeats.is_repeat, false) as is_repeat,
        case
            when matches.mystery_type = 'NULL' then null
            when matches.mystery_type != 'OBJECT'
                then 'mystery is not an object'
            when
                not matches.mystery_number_is_whole
                or matches.mystery_number < 1
                then 'mystery needs a number from 1'
            when matches.reveal_on_given and not matches.reveal_on_ok
                then 'mystery reveal_on is not a YYYY-MM-DD date'
        end as mystery_problem
    from matches
    left join item_ends
        on
            matches.challenge_file_key = item_ends.challenge_file_key
            and matches.item_position = item_ends.item_position
    left join repeats
        on
            matches.challenge_file_key = repeats.challenge_file_key
            and matches.item_position = repeats.item_position
),

match_checked as (
    select
        checked.*,
        case
            when checked.match_type != 'OBJECT' then 'match is not an object'
            when checked.kind is null
                then
                    'match kind ' || checked.kind_repr || ' is not one of '
                    || array_to_string(
                        {{ var('challenges_match_kinds') }}, ', '
                    )
            when checked.kind in ('place', 'places_all')
                then coalesce(
                    checked.radius_problem,
                    case
                        when
                            checked.kind = 'places_all'
                            and not checked.names_two_pois
                            then 'places_all names fewer than two pois'
                    end,
                    case
                        when checked.distinct_places != checked.place_count
                            then 'names the same poi twice'
                    end,
                    checked.place_problem
                )
            when checked.kind = 'poi_type'
                then coalesce(
                    checked.radius_problem,
                    case
                        when
                            not coalesce(
                                list_contains(
                                    published_types.poi_types,
                                    checked.poi_type_text
                                ),
                                false
                            )
                            then
                                'poi type ' || checked.poi_type_repr
                                || ' is not a published type'
                    end,
                    case
                        when
                            checked.off_trail_json is not null
                            and checked.off_trail_type != 'BOOLEAN'
                            then 'off_trail must be true or false'
                    end
                )
            when checked.kind = 'elevation_min_ft'
                then case
                    when not checked.value_ok
                        then 'elevation_min_ft needs a positive value'
                end
            when checked.kind = 'section_walked'
                then coalesce(
                    checked.place_problem,
                    case
                        when checked.from_end_mile = checked.to_end_mile
                            then 'both ends resolve to the same mile'
                    end,
                    case
                        when
                            checked.fraction_json is not null
                            and not checked.fraction_ok
                            then 'min_fraction must be in (0, 1]'
                    end
                )
            when checked.kind = 'workday' then case
                when
                    checked.workday_org_json is not null
                    and json_type(checked.workday_org_json) != 'NULL'
                    and not coalesce(
                        list_contains(
                            known_orgs.orgs, checked.workday_org_text
                        ),
                        false
                    )
                    then
                        'workday org ' || checked.workday_org_repr
                        || ' is not a known organization'
            end
        end as match_problem,
        -- What the match publishes as, by kind.
        case checked.kind
            when 'place'
                then json_object(
                    'kind', checked.kind,
                    'radius_m', checked.radius_m,
                    'off_trail', checked.place_off_trail,
                    'places', checked.published_places
                )
            when 'places_all'
                then json_object(
                    'kind', checked.kind,
                    'radius_m', checked.radius_m,
                    'off_trail', checked.place_off_trail,
                    'places', checked.published_places
                )
            when 'poi_type'
                then json_object(
                    'kind', checked.kind,
                    'type', checked.poi_type_text,
                    'radius_m', checked.radius_m,
                    'off_trail', checked.place_off_trail
                )
            when 'elevation_min_ft'
                then json_object(
                    'kind', checked.kind,
                    'value', try_cast(checked.value_json as double)
                )
            when 'section_walked'
                then json_object(
                    'kind', checked.kind,
                    'trail', checked.trail,
                    'from_mile', checked.low_mile,
                    'to_mile', checked.high_mile,
                    'from_name', checked.low_name,
                    'to_name', checked.high_name,
                    'min_fraction', checked.min_fraction
                )
            when 'workday'
                then json_object(
                    'kind', checked.kind,
                    'org', checked.workday_org_text,
                    'trail', checked.trail
                )
            when 'self_report' then json_object('kind', checked.kind)
        end as published_match
    from checked
    cross join published_types
    cross join known_orgs
),

resolved as (
    select
        match_checked.*,
        build.build_date,
        case
            when not match_checked.id_ok
                then
                    'item id must be lowercase words joined by hyphens, '
                    || 'at most {{ var("challenges_id_max_chars") }} characters'
            when match_checked.is_repeat then 'duplicate item id'
            when not match_checked.section_declared
                then
                    'section ' || match_checked.section_repr
                    || ' is not declared'
            when match_checked.mystery_problem is not null
                then match_checked.mystery_problem
            when
                match_checked.title = ''
                and match_checked.mystery_type = 'NULL'
                then 'item has no title'
            when match_checked.match_problem is not null
                then match_checked.match_problem
            when not match_checked.photo_ok then 'photo must be an https URL'
        end as problem,
        -- Sealed through the reveal day itself, against the build's date.
        coalesce(
            match_checked.mystery_type = 'OBJECT'
            and match_checked.title != ''
            and match_checked.reveal_on_date >= build.build_date,
            false
        ) as sealed
    from match_checked
    cross join build
)

select
    challenge_file_key || ':' || cast(item_position as varchar) as item_key,
    challenge_file_key,
    item_position,
    case when id_ok then item_id_text end as item_id,
    case when id_ok then item_id_text else '<no id>' end as report_label,
    kind,
    problem,
    sealed,
    place_distances,
    case
        when problem is not null then null
        when mystery_type = 'NULL'
            then json_object(
                'id', item_id_text,
                'section', section_text,
                'title', nullif(title, ''),
                'note', nullif(note_text, ''),
                'note_by', nullif(note_by_text, ''),
                'photo', photo_url,
                'match', published_match
            )
        when sealed
            then json_object(
                'id', item_id_text,
                'section', section_text,
                'title', null,
                'note', nullif(note_text, ''),
                'note_by', nullif(note_by_text, ''),
                'photo', photo_url,
                'match', published_match,
                'mystery', json_object(
                    'number', mystery_number,
                    'reveal_on', reveal_on_text
                ),
                'sealed_title', to_base64(encode(title))
            )
        else json_object(
            'id', item_id_text,
            'section', section_text,
            'title', nullif(title, ''),
            'note', nullif(note_text, ''),
            'note_by', nullif(note_by_text, ''),
            'photo', photo_url,
            'match', published_match,
            'mystery', json_object(
                'number', mystery_number,
                'reveal_on', reveal_on_text
            )
        )
    end as published_item
from resolved
