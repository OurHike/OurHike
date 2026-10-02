{{ config(materialized='table') }}
-- A table: the distance check is the family's one heavy step, and three models
-- and its tests read the result.
-- Every item of every challenge file that int_challenges__files let through
-- to its items, resolved as lib/challenges.py's resolve_challenge() loop and
-- resolve_item() resolve it (CH01, CH03-CH09), with the first refusal in
-- `problem` and the item as it publishes in `published_item`. Null
-- `problem` means the item publishes.
--
-- THE REFUSALS, IN THE PYTHON'S ORDER, because an item reports its first:
--   an id (CH10), then a repeat of an earlier item's id ("duplicate item
--   id": the first keeps it, since tags are keyed by item id, and a repeat
--   of an item that itself dropped is still a repeat);
--   a declared section; a well-formed mystery (CH07); a title, unless it is
--   a mystery;
--   the match (CH06): an object, one of the seven kinds, then the kind's own
--   checks, the places' among them (CH01, CH03, CH04, CH05); a photo that is
--   https or nothing.
--
-- A PLACE (`place`, each of `places_all`, a walked section's two ends) is a
-- published POI id (int_challenges__published_pois), on the challenge's
-- trail, with a mile and a coordinate; its mile, coordinate and name are
-- the published record's own, cut as _place() cuts them (3 and 6 places,
-- with Python's rounding: printf's fixed format read back as a double,
-- which wk/poi's python_round() measured against round() on 517,613 doubles). `places_all` is all or
-- nothing. A walked section's ends are never measured against the trail.
--
-- THE RADIUS CHECK (CH04), for a `place` or `places_all` place that is not
-- `off_trail`: the place is refused when its distance from the A.T.
-- centerline (int_challenges__centerline) is more than its radius. The
-- distance is the smaller of two great-circle distances, by
-- challenges_haversine_m(), the Python's own formula:
--   - to the point on the nearest centerline chain closest to the place,
--     both found in EPSG:5070 (ST_ClosestPoint) and read back in lon/lat;
--   - to the nearest centerline vertex within 0.1 degree, which is today's
--     whole measure (trail_distance_index(), whose 3x3 search of 0.05-degree
--     cells reaches no farther).
-- Each is the distance to a point on the line, so neither reads shorter
-- than the line's own great-circle distance, and the smaller is never
-- longer than today's nearest vertex. Reasoned from those two facts: this
-- admits a place a vertex gap refused and no place outside its radius, the
-- direction pipeline/ELT.md's known-difference row claims. EPSG:5070's own
-- metres are not used to decide, because they lean with direction (measured
-- 2026-10-02 at 41 N 74 W: a 30.0 m east-west pair read 29.83 m, a
-- north-south one 30.21 m), which would admit a place up to about 0.6% past
-- its radius. The message prints the distance where the Python printed "more
-- than a grid cell" for a place more than a cell from every vertex.
--
-- WITH NO CENTERLINE (CH13) the check is skipped, as the Python skips it;
-- the warn test challenges_distance_check_has_a_centerline_to_measure_against
-- is what says so, where export_challenges.py printed a ::warning::.
--
-- SEALED MYSTERY TITLES (CH07): a mystery item with a title and a reveal_on
-- ships its title as `sealed_title`, base64 of the stripped title's UTF-8
-- bytes, and `title` null, through the reveal_on day itself, compared with
-- the build date (var challenges_build_date, else the build's UTC date). A
-- mystery with no title ships none and nothing to unseal; one with a title
-- and no reveal_on ships the title in the clear, as the Python does.
--
-- WHERE THIS IS STRICTER THAN THE PYTHON, deliberately, each in the unit
-- test and in tests/test_dbt_challenges_parity.py's list: an item id or a
-- section id with a trailing newline passes _id_ok() (re.match's `$`) and is
-- refused here (challenges_id_ok()).
{%- set build_date = var('challenges_build_date') %}
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

-- The types at least one published POI carries, of lib/poi_schema.py's
-- POI_TYPES: build_output()'s `published_types`. `trailhead` is declared and
-- the ATC publishes none, so "tag any trailhead" would be an item nobody
-- could ever tag.
published_types as (
    select coalesce(list(distinct poi_type), cast([] as varchar[])) as poi_types
    from pois
    where list_contains({{ var('challenges_poi_types') }}, poi_type)
),

known_orgs as (
    select coalesce(list(org), cast([] as varchar[])) as orgs
    from publishers
),

build as (
    select
        {% if build_date -%}
        cast('{{ build_date }}' as date)
        {%- else -%}
        cast(timezone('UTC', now()) as date)
        {%- endif %} as build_date
),

items as (
    select
        challenge_file_key,
        trail,
        cast(cast(section_ids as json) as varchar[]) as section_ids,
        unnest(cast(cast(items_json as json) as json[])) as item_json,
        generate_subscripts(cast(cast(items_json as json) as json[]), 1) as item_position
    from challenge_files
),

fields as (
    select
        *,
        coalesce(json_type(item_json), 'NULL') as item_type,
        json_extract(item_json, '$.id') as item_id_json,
        json_extract(item_json, '$.section') as section_json,
        json_extract(item_json, '$.mystery') as mystery_json,
        json_extract(item_json, '$.title') as title_json,
        json_extract(item_json, '$.note') as note_json,
        json_extract(item_json, '$.note_by') as note_by_json,
        json_extract(item_json, '$.photo') as photo_json,
        json_extract(item_json, '$.match') as match_json,
        coalesce(json_type(json_extract(item_json, '$.match')), 'NULL') as match_type,
        json_extract(item_json, '$.match.kind') as kind_json,
        -- Each value a message quotes, as Python's repr() prints it, once.
        {{ python_repr("json_extract(item_json, '$.section')") }} as section_repr,
        {{ python_repr("json_extract(item_json, '$.match.kind')") }} as kind_repr,
        {{ python_repr("json_extract(item_json, '$.match.type')") }} as poi_type_repr,
        {{ python_repr("json_extract(item_json, '$.match.org')") }} as workday_org_repr
    from items
),

kinds as (
    select
        *,
        coalesce(json_type(item_json), 'NULL') = 'OBJECT'
        and {{ challenges_id_ok('item_id_json') }} as id_ok,
        case
            when
                match_type = 'OBJECT'
                and json_type(kind_json) = 'VARCHAR'
                and list_contains(
                    {{ var('challenges_match_kinds') }}, json_extract_string(kind_json, '$')
                )
                then json_extract_string(kind_json, '$')
        end as kind,
        coalesce(json_type(mystery_json), 'NULL') as mystery_type,
        json_extract(mystery_json, '$.number') as mystery_number_json,
        json_extract(mystery_json, '$.reveal_on') as reveal_on_json,
        {{ challenges_text('title_json') }} as title
    from fields
),

-- The radius a place kind or poi_type is held to: the match's own, else the
-- kind's default; then the bounds, then Python's round() to a whole metre.
radii as (
    select
        *,
        json_extract(match_json, '$.radius_m') as radius_json,
        case kind
            when 'place' then {{ var('challenges_default_radius_m_place') }}
            when 'places_all' then {{ var('challenges_default_radius_m_places_all') }}
            when 'poi_type' then {{ var('challenges_default_radius_m_poi_type') }}
        end as default_radius_m
    from kinds
),

radius_checked as (
    select
        *,
        case
            when radius_json is null then cast(default_radius_m as double)
            when json_type(radius_json) in ('BIGINT', 'UBIGINT', 'DOUBLE')
                then cast(radius_json as double)
        end as radius_raw,
        case
            when
                radius_json is not null
                and coalesce(json_type(radius_json), 'NULL') not in ('BIGINT', 'UBIGINT', 'DOUBLE')
                then 'radius_m is not a number'
            when
                radius_json is not null
                and not cast(radius_json as double)
                between {{ var('challenges_min_radius_m') }} and {{ var('challenges_max_radius_m') }}
                then
                    'radius_m ' || {{ python_plain_repr('radius_json') }} || ' is outside '
                    || '{{ var("challenges_min_radius_m") }}-{{ var("challenges_max_radius_m") }} m'
        end as radius_problem
    from radii
),

matches as (
    select
        *,
        cast(printf('%.0f', radius_raw) as integer) as radius_m,
        -- A place kind's `off_trail` is true only when it is JSON true.
        coalesce(
            json_type(json_extract(match_json, '$.off_trail')) = 'BOOLEAN'
            and json_extract_string(match_json, '$.off_trail') = 'true', false
        ) as place_off_trail
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
        generate_subscripts(cast(json_extract(match_json, '$.pois') as json[]), 1) as place_position,
        '' as end_label,
        unnest(cast(json_extract(match_json, '$.pois') as json[])) as poi_json
    from matches
    where kind = 'places_all' and json_type(json_extract(match_json, '$.pois')) = 'ARRAY'
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
        case
            when json_type(place_refs.poi_json) = 'VARCHAR' and json_extract_string(place_refs.poi_json, '$') != ''
                then json_extract_string(place_refs.poi_json, '$')
        end as poi_id,
        {{ python_repr('place_refs.poi_json') }} as poi_repr,
        pois.poi_id as published_poi_id,
        pois.trail_id,
        pois.poi_type,
        pois.name as poi_name,
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

-- The places the radius check measures: a place kind's, not off_trail,
-- published with a coordinate. Measured only where a centerline exists.
measured_pois as (
    select distinct
        published_poi_id as poi_id,
        lon,
        lat
    from places
    where
        kind in ('place', 'places_all')
        and not place_off_trail
        and published_poi_id is not null
        and lat is not null
        and lon is not null
),

measured as (
    select
        poi_id,
        lon,
        lat,
        st_transform(st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true) as point_5070
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
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true) as geom_5070
    from chains
),

vertices as (
    select
        st_x(struct_extract(vertex, 'geom')) as vertex_lon,
        st_y(struct_extract(vertex, 'geom')) as vertex_lat
    from (select unnest(st_dump(st_points(geom))) as vertex from chains) as dumped
),

nearest_chain as (
    select
        measured.poi_id,
        arg_min(chains_5070.trail_line_id, st_distance(measured.point_5070, chains_5070.geom_5070)) as trail_line_id
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
    inner join chains_5070 on nearest_chain.trail_line_id = chains_5070.trail_line_id
),

nearest_vertex as (
    select
        measured.poi_id,
        min({{ challenges_haversine_m('measured.lon', 'measured.lat', 'vertices.vertex_lon', 'vertices.vertex_lat') }})
            as vertex_m
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
            {{ challenges_haversine_m('measured.lon', 'measured.lat', 'st_x(closest_points.closest)', 'st_y(closest_points.closest)') }},
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
        case
            when places.kind in ('place', 'places_all') and not places.place_off_trail
                then distances.distance_m
        end as distance_m,
        places.end_label || case
            when places.poi_id is null then 'names no poi'
            when places.published_poi_id is null
                then 'poi ' || places.poi_id || ' is not in the published POIs'
            when not coalesce(places.trail_id = places.trail, false)
                then
                    'poi ' || places.poi_id || ' is on trail '
                    || coalesce({{ python_str_repr('places.trail_id') }}, 'None')
                    || ', not ' || {{ python_str_repr('places.trail') }}
            when places.mile is null then 'poi ' || places.poi_id || ' has no published mile'
            when places.lat is null or places.lon is null
                then 'poi ' || places.poi_id || ' has no coordinate'
            when
                places.kind in ('place', 'places_all')
                and not places.place_off_trail
                and distances.distance_m > places.radius_m
                then
                    'poi ' || places.poi_id || ' is ' || printf('%.0f', distances.distance_m)
                    || ' m from the trail, past its ' || places.radius_m
                    || ' m radius - mark the match off_trail if reaching it means leaving the trail'
        end as place_problem,
        cast(printf('%.3f', places.mile) as double) as place_mile,
        {{ python_strip("coalesce(places.poi_name, '')") }} as place_name,
        json_object(
            'poi', places.poi_id,
            'name', {{ python_strip("coalesce(places.poi_name, '')") }},
            'poi_type', {{ python_strip("coalesce(places.poi_type, '')") }},
            'mile', cast(printf('%.3f', places.mile) as double),
            'lat', cast(printf('%.6f', places.lat) as double),
            'lon', cast(printf('%.6f', places.lon) as double)
        ) as published_place
    from places
    left join distances on places.published_poi_id = distances.poi_id
),

item_places as (
    select
        challenge_file_key,
        item_position,
        arg_min(place_problem, place_position) filter (where place_problem is not null) as place_problem,
        count(*) as place_count,
        -- places_all's `len(set(map(str, ids))) != len(ids)`: two places the
        -- same once each is printed as str().
        count(distinct {{ python_str('poi_json', 'poi_repr') }}) as distinct_places,
        to_json(list(published_place order by place_position)) as published_places,
        cast(to_json(list(
            case when distance_m is not null then printf('%.3f', distance_m) end
            order by place_position
        )) as varchar) as place_distances,
        arg_min(place_mile, place_position) as from_end_mile,
        arg_max(place_mile, place_position) as to_end_mile,
        arg_min(place_name, place_position) as from_end_name,
        arg_max(place_name, place_position) as to_end_name
    from place_checks
    group by challenge_file_key, item_position
),

repeats as (
    select
        challenge_file_key,
        item_position,
        row_number() over (
            partition by challenge_file_key, json_extract_string(item_id_json, '$')
            order by item_position
        ) > 1 as is_repeat
    from kinds
    where id_ok
),

checked as (
    select
        matches.*,
        item_places.place_problem,
        item_places.place_count,
        item_places.distinct_places,
        item_places.published_places,
        item_places.place_distances,
        item_places.from_end_mile,
        item_places.to_end_mile,
        item_places.from_end_name,
        item_places.to_end_name,
        coalesce(repeats.is_repeat, false) as is_repeat,
        json_extract(matches.match_json, '$.type') as poi_type_json,
        json_extract(matches.match_json, '$.off_trail') as off_trail_json,
        json_extract(matches.match_json, '$.value') as value_json,
        json_extract(matches.match_json, '$.min_fraction') as fraction_json,
        json_extract(matches.match_json, '$.org') as workday_org_json,
        json_extract(matches.match_json, '$.pois') as pois_json,
        case
            when matches.mystery_type = 'NULL' then null
            when matches.mystery_type != 'OBJECT' then 'mystery is not an object'
            when
                coalesce(json_type(matches.mystery_number_json), 'NULL') not in ('BIGINT', 'UBIGINT')
                or try_cast(matches.mystery_number_json as hugeint) < 1
                then 'mystery needs a number from 1'
            when
                coalesce(json_type(matches.reveal_on_json), 'NULL') != 'NULL'
                and not {{ challenges_date_ok('matches.reveal_on_json') }}
                then 'mystery reveal_on is not a YYYY-MM-DD date'
        end as mystery_problem
    from matches
    left join item_places
        on
            matches.challenge_file_key = item_places.challenge_file_key
            and matches.item_position = item_places.item_position
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
                    || array_to_string({{ var('challenges_match_kinds') }}, ', ')
            when checked.kind in ('place', 'places_all')
                then coalesce(
                    checked.radius_problem,
                    case
                        when
                            checked.kind = 'places_all'
                            and (
                                coalesce(json_type(checked.pois_json), 'NULL') != 'ARRAY'
                                or json_array_length(checked.pois_json) < 2
                            )
                            then 'places_all names fewer than two pois'
                    end,
                    case
                        when checked.distinct_places != checked.place_count then 'names the same poi twice'
                    end,
                    checked.place_problem
                )
            when checked.kind = 'poi_type'
                then coalesce(
                    checked.radius_problem,
                    case
                        when
                            not coalesce(
                                json_type(checked.poi_type_json) = 'VARCHAR'
                                and list_contains(published_types.poi_types, json_extract_string(checked.poi_type_json, '$')),
                                false
                            )
                            then 'poi type ' || checked.poi_type_repr || ' is not a published type'
                    end,
                    case
                        when
                            checked.off_trail_json is not null
                            and coalesce(json_type(checked.off_trail_json), 'NULL') != 'BOOLEAN'
                            then 'off_trail must be true or false'
                    end
                )
            when checked.kind = 'elevation_min_ft'
                then case
                    when
                        not coalesce(
                            json_type(checked.value_json) in ('BIGINT', 'UBIGINT', 'DOUBLE')
                            and try_cast(checked.value_json as double) > 0,
                            false
                        )
                        then 'elevation_min_ft needs a positive value'
                end
            when checked.kind = 'section_walked'
                then coalesce(
                    checked.place_problem,
                    case
                        when checked.from_end_mile = checked.to_end_mile then 'both ends resolve to the same mile'
                    end,
                    case
                        when
                            checked.fraction_json is not null
                            and not coalesce(
                                json_type(checked.fraction_json) in ('BIGINT', 'UBIGINT', 'DOUBLE')
                                and try_cast(checked.fraction_json as double) > 0
                                and try_cast(checked.fraction_json as double) <= 1,
                                false
                            )
                            then 'min_fraction must be in (0, 1]'
                    end
                )
            when checked.kind = 'workday' then case
                when
                    coalesce(json_type(checked.workday_org_json), 'NULL') != 'NULL'
                    and not coalesce(
                        json_type(checked.workday_org_json) = 'VARCHAR'
                        and list_contains(known_orgs.orgs, json_extract_string(checked.workday_org_json, '$')),
                        false
                    )
                    then 'workday org ' || checked.workday_org_repr || ' is not a known organization'
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
                    'type', json_extract_string(checked.poi_type_json, '$'),
                    'radius_m', checked.radius_m,
                    'off_trail', coalesce(
                        json_type(checked.off_trail_json) = 'BOOLEAN'
                        and json_extract_string(checked.off_trail_json, '$') = 'true',
                        false
                    )
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
                    'from_mile', least(checked.from_end_mile, checked.to_end_mile),
                    'to_mile', greatest(checked.from_end_mile, checked.to_end_mile),
                    'from_name', case
                        when checked.from_end_mile <= checked.to_end_mile then checked.from_end_name
                        else checked.to_end_name
                    end,
                    'to_name', case
                        when checked.from_end_mile <= checked.to_end_mile then checked.to_end_name
                        else checked.from_end_name
                    end,
                    'min_fraction', coalesce(
                        try_cast(checked.fraction_json as double),
                        cast({{ var('challenges_default_min_fraction') }} as double)
                    )
                )
            when 'workday'
                then json_object(
                    'kind', checked.kind,
                    'org', case
                        when json_type(checked.workday_org_json) = 'VARCHAR'
                            then json_extract_string(checked.workday_org_json, '$')
                    end,
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
                    'item id must be lowercase words joined by hyphens, at most '
                    || '{{ var("challenges_id_max_chars") }} characters'
            when match_checked.is_repeat then 'duplicate item id'
            when
                not coalesce(
                    json_type(match_checked.section_json) = 'VARCHAR'
                    and list_contains(match_checked.section_ids, json_extract_string(match_checked.section_json, '$')),
                    false
                )
                then 'section ' || match_checked.section_repr || ' is not declared'
            when match_checked.mystery_problem is not null then match_checked.mystery_problem
            when match_checked.title = '' and match_checked.mystery_type = 'NULL' then 'item has no title'
            when match_checked.match_problem is not null then match_checked.match_problem
            when not {{ challenges_https_ok('match_checked.photo_json') }} then 'photo must be an https URL'
        end as problem,
        -- Sealed through the reveal day itself, against the build's date.
        coalesce(
            match_checked.mystery_type = 'OBJECT'
            and match_checked.title != ''
            and json_type(match_checked.reveal_on_json) = 'VARCHAR'
            and try_cast(json_extract_string(match_checked.reveal_on_json, '$') as date) >= build.build_date,
            false
        ) as sealed
    from match_checked
    cross join build
)

select
    challenge_file_key || ':' || cast(item_position as varchar) as item_key,
    challenge_file_key,
    item_position,
    case when id_ok then json_extract_string(item_id_json, '$') end as item_id,
    case when id_ok then json_extract_string(item_id_json, '$') else '<no id>' end as report_label,
    kind,
    problem,
    sealed,
    place_distances,
    case
        when problem is not null then null
        when mystery_type = 'NULL'
            then json_object(
                'id', json_extract_string(item_id_json, '$'),
                'section', json_extract_string(section_json, '$'),
                'title', nullif(title, ''),
                'note', nullif({{ challenges_text('note_json') }}, ''),
                'note_by', nullif({{ challenges_text('note_by_json') }}, ''),
                'photo', {{ challenges_https('photo_json') }},
                'match', published_match
            )
        when sealed
            then json_object(
                'id', json_extract_string(item_id_json, '$'),
                'section', json_extract_string(section_json, '$'),
                'title', null,
                'note', nullif({{ challenges_text('note_json') }}, ''),
                'note_by', nullif({{ challenges_text('note_by_json') }}, ''),
                'photo', {{ challenges_https('photo_json') }},
                'match', published_match,
                'mystery', json_object(
                    'number', cast(mystery_number_json as hugeint),
                    'reveal_on', json_extract_string(reveal_on_json, '$')
                ),
                'sealed_title', to_base64(encode(title))
            )
        else json_object(
            'id', json_extract_string(item_id_json, '$'),
            'section', json_extract_string(section_json, '$'),
            'title', nullif(title, ''),
            'note', nullif({{ challenges_text('note_json') }}, ''),
            'note_by', nullif({{ challenges_text('note_by_json') }}, ''),
            'photo', {{ challenges_https('photo_json') }},
            'match', published_match,
            'mystery', json_object(
                'number', cast(mystery_number_json as hugeint),
                'reveal_on', case
                    when json_type(reveal_on_json) = 'VARCHAR' then json_extract_string(reveal_on_json, '$')
                end
            )
        )
    end as published_item
from resolved
