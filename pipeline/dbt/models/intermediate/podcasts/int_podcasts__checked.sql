-- Every row of reference/podcast_episodes.json, read and checked against
-- lib/podcasts.py's validate() (#1683, #1690, #1718), with the first rule it
-- breaks in `rule_id` and why in `problem`. Null in both means the row
-- publishes. The test on this model fails the build if any row has a
-- problem, so a list that would drop a row writes nothing: export_podcasts.py
-- refuses an upload on any drop for the same reason (PC07).
--
-- THE RULES, IN validate()'S ORDER, because a row reports only its first:
--   PC08 an object                  PC09 minutes      PC05 pois and places
--   PC03 only the known fields      PC10 hikes        PC04 links
--   PC01 the Spotify id             PC02 at_miles     PC11 reviewed
--   PC06 each episode once                            PC12 at least one anchor
--   PC08 a title and a show
-- (pipeline/ELT.md's podcasts rule table). The fields and app hosts are
-- seeds, and the id pattern and mile ceiling are vars, each held to its
-- Python constant by tests/test_dbt_podcasts_parity.py, which also runs
-- validate() over this model's unit test and compares the two.
--
-- A FIELD IS ITS JSON, READ ONCE. The extract lands each row as written
-- (ReviewedFile's `verbatim`), so a field's JSON type is checked the way
-- validate() checks a Python type: "34" is not a length and true is not a
-- number. json_type is 'NULL' for a field that is null or absent, the two
-- cases row.get() does not tell apart. Strings are stripped by
-- python_strip(), which strips exactly what str.strip() does.
--
-- WHERE THIS IS STRICTER THAN validate(), deliberately, each a row validate()
-- would publish and this refuses, all three in the unit test:
--   - `reviewed` must be YYYY-MM-DD, as both messages say. Python 3.11's
--     date.fromisoformat() also takes 20260929 and 2026-W40-4.
--   - the Spotify id must end at its 22nd character. re.match's `$` also
--     matches before a trailing newline, which would then be spliced into
--     the phone's URL.
--   - a link's scheme and host are read as written. urlsplit() first strips
--     leading spaces and control characters, and the phone would then open
--     the link with them still in it.
-- Messages render a value as JSON, where validate() uses Python's repr.
with episodes as (
    select * from {{ ref('base_podcasts__podcast_episodes') }}
),

ledger as (
    select * from {{ ref('base_ourhike__poi_identity') }}
),

row_fields as (
    select list(field_name order by field_name) as allowed
    from {{ ref('podcast_row_fields') }}
),

app_hosts as (
    select
        app,
        list(hostname order by hostname) as hostnames
    from {{ ref('podcast_app_link_hosts') }}
    group by app
),

known_apps as (
    select string_agg(app, ', ' order by app) as apps
    from app_hosts
),

fields as (
    select
        episodes.episode_row_key,
        episodes.file_row,
        episodes.episode,
        row_fields.allowed,
        json_type(episodes.episode) as episode_type,
        json_extract(episodes.episode, '$.spotify_id') as spotify_id_json,
        json_extract(episodes.episode, '$.title') as title_json,
        json_extract(episodes.episode, '$.show') as show_json,
        json_extract(episodes.episode, '$.minutes') as minutes_json,
        json_extract(episodes.episode, '$.hikes') as hikes_json,
        json_extract(episodes.episode, '$.at_miles') as at_miles_json,
        json_extract(episodes.episode, '$.pois') as pois_json,
        json_extract(episodes.episode, '$.places') as places_json,
        json_extract(episodes.episode, '$.links') as links_json,
        json_extract(episodes.episode, '$.reviewed') as reviewed_json
    from episodes
    cross join row_fields
),

typed as (
    select
        *,
        coalesce(json_type(spotify_id_json), 'NULL') as spotify_id_type,
        coalesce(json_type(title_json), 'NULL') as title_type,
        coalesce(json_type(show_json), 'NULL') as show_type,
        coalesce(json_type(minutes_json), 'NULL') as minutes_type,
        coalesce(json_type(hikes_json), 'NULL') as hikes_type,
        coalesce(json_type(at_miles_json), 'NULL') as at_miles_type,
        coalesce(json_type(pois_json), 'NULL') as pois_type,
        coalesce(json_type(places_json), 'NULL') as places_type,
        coalesce(json_type(links_json), 'NULL') as links_type,
        coalesce(json_type(reviewed_json), 'NULL') as reviewed_type,
        case
            when episode_type = 'OBJECT'
                then list_sort(list_filter(
                    json_keys(episode),
                    lambda k: not list_contains(allowed, k)
                ))
        end as unknown_fields,
        case
            when json_type(hikes_json) = 'ARRAY'
                then cast(hikes_json as json[])
        end as hike_items,
        case
            when json_type(at_miles_json) = 'ARRAY'
                then cast(at_miles_json as json[])
        end as at_miles_items,
        case
            when json_type(pois_json) = 'ARRAY'
                then cast(pois_json as json[])
        end as poi_items,
        case
            when json_type(places_json) = 'ARRAY'
                then cast(places_json as json[])
        end as place_items
    from fields
),

-- Each field as a value, where its JSON type allows one, and each list's
-- items as validate() reads them.
parsed as (
    select
        *,
        case
            when spotify_id_type = 'VARCHAR'
                then json_extract_string(spotify_id_json, '$')
        end as spotify_id,
        case
            when title_type = 'VARCHAR'
                then nullif(
                    {{ python_strip("json_extract_string(title_json, '$')") }},
                    ''
                )
        end as title,
        case
            when show_type = 'VARCHAR'
                then nullif(
                    {{ python_strip("json_extract_string(show_json, '$')") }},
                    ''
                )
        end as show_name,
        case
            when minutes_type = 'UBIGINT'
                then try_cast(json_extract_string(minutes_json, '$') as bigint)
        end as minutes,
        coalesce(list_bool_and(list_transform(
            hike_items,
            lambda h: json_type(h) = 'VARCHAR'
            and {{ python_strip("json_extract_string(h, '$')") }} != ''
        )), true) as hikes_are_ids,
        coalesce(list_bool_and(list_transform(
            poi_items,
            lambda p: json_type(p) = 'VARCHAR'
            and {{ python_strip("json_extract_string(p, '$')") }} != ''
        )), true) as pois_are_ids,
        coalesce(list_bool_and(list_transform(
            place_items,
            lambda p: json_type(p) = 'VARCHAR'
            and {{ python_strip("json_extract_string(p, '$')") }} != ''
        )), true) as places_are_names,
        -- The first [start, end] pair with a problem: its shape, then its
        -- range. A boolean is not a number, as in validate().
        list_filter(list_transform(
            at_miles_items,
            lambda pair: case
                when
                    not coalesce(
                        json_type(pair) = 'ARRAY'
                        and json_array_length(pair) = 2
                        and json_type(json_extract(pair, '$[0]'))
                        in ('UBIGINT', 'BIGINT', 'DOUBLE')
                        and json_type(json_extract(pair, '$[1]'))
                        in ('UBIGINT', 'BIGINT', 'DOUBLE'),
                        false
                    )
                    then
                        'each at_miles entry must be [start, end], not '
                        || cast(pair as varchar)
                when
                    not coalesce(
                        0 <= try_cast(
                            json_extract_string(pair, '$[0]') as double
                        )
                        and try_cast(
                            json_extract_string(pair, '$[0]') as double
                        ) < try_cast(
                            json_extract_string(pair, '$[1]') as double
                        )
                        and try_cast(
                            json_extract_string(pair, '$[1]') as double
                        ) <= {{ var('podcast_max_at_mile') }},
                        false
                    )
                    then
                        'at_miles ' || cast(pair as varchar)
                        || ' must run forward, inside 0 to '
                        || '{{ var("podcast_max_at_mile") }}'
            end
        ), lambda m: m is not null)[1] as first_pair_problem,
        coalesce(list_transform(
            hike_items,
            lambda h: {{ python_strip("json_extract_string(h, '$')") }}
        ), []) as hikes,
        coalesce(list_transform(
            at_miles_items,
            lambda pair: [
                try_cast(json_extract_string(pair, '$[0]') as double),
                try_cast(json_extract_string(pair, '$[1]') as double)
            ]
        ), []) as at_miles,
        -- As written for the ledger lookup and the repeat check, which
        -- validate() makes before stripping; stripped for publishing.
        list_transform(
            poi_items, lambda p: json_extract_string(p, '$')
        ) as poi_ids_as_written,
        coalesce(list_transform(
            poi_items,
            lambda p: {{ python_strip("json_extract_string(p, '$')") }}
        ), []) as pois,
        list_transform(
            place_items,
            lambda p: {{ python_strip("json_extract_string(p, '$')") }}
        ) as place_names,
        -- JSON, not a map, until the mart: dbt 2.0.6's unit tests cannot
        -- parse a MAP column type ("Failed to parse column type 'map(varchar
        -- not null, varchar)'", 2026-10-01).
        case
            when links_type = 'OBJECT' then links_json
            else cast('{}' as json)
        end as links
    from typed
),

-- PC05, tag by tag: each tagged POI live in the ledger under the name beside
-- it, for the rows whose pois and places have the right shape.
tags as (
    select
        episode_row_key,
        unnest(poi_ids_as_written) as poi_id,
        unnest(place_names) as place_name,
        generate_subscripts(poi_ids_as_written, 1) as tag_number
    from parsed
    where
        pois_type = 'ARRAY'
        and len(poi_items) > 0
        and pois_are_ids
        and places_type = 'ARRAY'
        and len(place_items) = len(poi_items)
        and places_are_names
        and len(list_distinct(poi_ids_as_written)) = len(poi_ids_as_written)
),

tag_checks as (
    select
        tags.episode_row_key,
        tags.tag_number,
        case
            when ledger.poi_id is null
                then tags.poi_id || ' has never been a published POI'
            when ledger.retired is not null
                then
                    tags.poi_id || ' (' || coalesce(ledger.name, 'None')
                    || ') was retired on ' || ledger.retired
                    || coalesce(
                        '; it was superseded by '
                        || nullif(ledger.superseded_by, ''),
                        ''
                    )
            -- Not `is distinct from`, which SQLFluff 4.3.0's DuckDB dialect
            -- cannot parse; the place name is never null here.
            when not coalesce(ledger.name = tags.place_name, false)
                then
                    tags.poi_id || ' is '
                    || coalesce(cast(to_json(ledger.name) as varchar), 'null')
                    || ' in the POI ledger, not '
                    || cast(to_json(tags.place_name) as varchar)
        end as tag_problem
    from tags
    left join ledger on tags.poi_id = ledger.poi_id
),

tag_problems as (
    select
        episode_row_key,
        arg_min(tag_problem, tag_number)
        filter (where tag_problem is not null) as tag_problem
    from tag_checks
    group by episode_row_key
),

-- PC04, app by app in sorted order, as validate() walks sorted(items()).
link_maps as (
    select
        episode_row_key,
        cast(links_json as map (varchar, json)) as link_map
    from parsed
    where links_type = 'OBJECT'
),

link_entries as (
    select
        episode_row_key,
        link_map,
        unnest(list_sort(map_keys(link_map))) as app,
        generate_subscripts(map_keys(link_map), 1) as link_number
    from link_maps
),

-- A host as urlsplit() reads one: the authority after `//`, after its last
-- `@` and before its first `:`, lowercased.
link_urls as (
    select
        episode_row_key,
        link_number,
        app,
        map_extract_value(link_map, app) as link_json,
        case
            when json_type(map_extract_value(link_map, app)) = 'VARCHAR'
                then json_extract_string(map_extract_value(link_map, app), '$')
        end as link_text
    from link_entries
),

link_parts as (
    select
        *,
        lower(regexp_extract(
            link_text, '^([A-Za-z][A-Za-z0-9+.-]*):', 1
        )) as scheme,
        lower(regexp_replace(
            regexp_replace(
                regexp_extract(
                    link_text, '^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]*)', 1
                ),
                '^.*@', ''
            ),
            ':.*$', ''
        )) as hostname
    from link_urls
),

link_checks as (
    select
        link_parts.episode_row_key,
        link_parts.link_number,
        case
            when app_hosts.app is null
                then
                    'links has an unknown app '
                    || cast(to_json(link_parts.app) as varchar)
                    || '; known: ' || known_apps.apps
            when
                not coalesce(
                    link_parts.scheme = 'https'
                    and list_contains(app_hosts.hostnames, link_parts.hostname),
                    false
                )
                then
                    'links.' || link_parts.app || ' must be an https link on '
                    || array_to_string(app_hosts.hostnames, ' or ')
                    || ', not ' || cast(link_parts.link_json as varchar)
        end as link_problem
    from link_parts
    cross join known_apps
    left join app_hosts on link_parts.app = app_hosts.app
),

link_problems as (
    select
        episode_row_key,
        arg_min(link_problem, link_number)
        filter (where link_problem is not null) as link_problem
    from link_checks
    group by episode_row_key
),

-- One column per check, null where the row passes it.
checks as (
    select
        parsed.episode_row_key,
        parsed.file_row,
        parsed.spotify_id,
        parsed.title,
        parsed.show_name,
        parsed.minutes,
        parsed.hikes,
        parsed.at_miles,
        parsed.pois,
        parsed.links,
        case
            when parsed.episode_type != 'OBJECT' then 'not an object'
        end as not_object,
        case
            when len(parsed.unknown_fields) > 0
                then
                    'unknown field(s) '
                    || array_to_string(parsed.unknown_fields, ', ')
        end as unknown_field,
        case
            when
                not coalesce(regexp_full_match(
                    parsed.spotify_id, '{{ var("podcast_spotify_id_pattern") }}'
                ), false)
                then
                    'spotify_id must be the 22 characters after /episode/ '
                    || 'in its link'
        end as bad_spotify_id,
        case
            when parsed.title is null or parsed.show_name is null
                then 'title and show are both required'
        end as no_title,
        case
            when
                parsed.minutes_type != 'NULL'
                and not coalesce(parsed.minutes > 0, false)
                then
                    'minutes must be a positive whole number or absent, not '
                    || cast(parsed.minutes_json as varchar)
        end as bad_minutes,
        case
            when
                parsed.hikes_type != 'NULL'
                and not (parsed.hikes_type = 'ARRAY' and parsed.hikes_are_ids)
                then
                    'hikes must be a list of hike ids, not '
                    || cast(parsed.hikes_json as varchar)
        end as bad_hikes,
        case
            when parsed.at_miles_type = 'NULL' then null
            when parsed.at_miles_type != 'ARRAY'
                then
                    'at_miles must be a list of [start, end] pairs, not '
                    || cast(parsed.at_miles_json as varchar)
            else parsed.first_pair_problem
        end as bad_at_miles,
        case
            when parsed.pois_type = 'NULL' and parsed.places_type = 'NULL'
                then null
            when
                not (
                    parsed.pois_type = 'ARRAY'
                    and len(parsed.poi_items) > 0
                    and parsed.pois_are_ids
                )
                then
                    'pois must be a list of published POI ids, not '
                    || coalesce(cast(parsed.pois_json as varchar), 'null')
            when
                not (
                    parsed.places_type = 'ARRAY'
                    and len(parsed.place_items) = len(parsed.poi_items)
                    and parsed.places_are_names
                )
                then
                    'places must name each of pois, in the same order, so a '
                    || 'diff can be read'
            when
                len(list_distinct(parsed.poi_ids_as_written))
                != len(parsed.poi_ids_as_written)
                then 'the same POI is listed twice in pois'
            else tag_problems.tag_problem
        end as bad_pois,
        case
            when parsed.links_type = 'NULL' then null
            when parsed.links_type != 'OBJECT'
                then
                    'links must be an object of app -> link, not '
                    || cast(parsed.links_json as varchar)
            else link_problems.link_problem
        end as bad_links,
        case
            when parsed.reviewed_type != 'VARCHAR'
                then 'reviewed must be a date, YYYY-MM-DD'
            when
                not coalesce(
                    regexp_full_match(
                        json_extract_string(parsed.reviewed_json, '$'),
                        '\d{4}-\d{2}-\d{2}'
                    )
                    and try_strptime(
                        json_extract_string(parsed.reviewed_json, '$'),
                        '%Y-%m-%d'
                    ) is not null,
                    false
                )
                then
                    'reviewed ' || cast(parsed.reviewed_json as varchar)
                    || ' is not a YYYY-MM-DD date'
        end as bad_reviewed,
        case
            when
                len(parsed.hikes) = 0
                and len(parsed.at_miles) = 0
                and len(parsed.pois) = 0
                then
                    'needs at least one of hikes, at_miles or pois, or it '
                    || 'shows nowhere'
        end as no_anchor
    from parsed
    left join tag_problems
        on parsed.episode_row_key = tag_problems.episode_row_key
    left join link_problems
        on parsed.episode_row_key = link_problems.episode_row_key
),

-- PC06: validate() remembers an id only once its row has passed every
-- check, so the row that keeps an id is the first with no problem at all,
-- and a later row with no problem before the repeat check is the repeat.
kept as (
    select
        spotify_id,
        min(file_row) as kept_row
    from checks
    where
        coalesce(
            not_object, unknown_field, bad_spotify_id, no_title, bad_minutes,
            bad_hikes, bad_at_miles, bad_pois, bad_links, bad_reviewed,
            no_anchor
        ) is null
    group by spotify_id
),

repeats as (
    select
        checks.*,
        case
            when kept.kept_row < checks.file_row
                then 'the same episode is listed twice; merge the two rows'
        end as repeated
    from checks
    left join kept on checks.spotify_id = kept.spotify_id
)

select
    episode_row_key,
    file_row,
    'row ' || file_row || coalesce(' (' || spotify_id || ')', '') as row_label,
    spotify_id,
    title,
    show_name,
    minutes,
    hikes,
    at_miles,
    pois,
    links,
    case
        when not_object is not null then 'PC08'
        when unknown_field is not null then 'PC03'
        when bad_spotify_id is not null then 'PC01'
        when repeated is not null then 'PC06'
        when no_title is not null then 'PC08'
        when bad_minutes is not null then 'PC09'
        when bad_hikes is not null then 'PC10'
        when bad_at_miles is not null then 'PC02'
        when bad_pois is not null then 'PC05'
        when bad_links is not null then 'PC04'
        when bad_reviewed is not null then 'PC11'
        when no_anchor is not null then 'PC12'
    end as rule_id,
    coalesce(
        not_object, unknown_field, bad_spotify_id, repeated, no_title,
        bad_minutes, bad_hikes, bad_at_miles, bad_pois, bad_links,
        bad_reviewed, no_anchor
    ) as problem
from repeats
