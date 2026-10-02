{{ config(materialized='table') }}
-- Every published POI with its one-sentence `description`, or null where
-- nothing usable is stated. One row per POI.
--
-- THE A.T. FAMILY: lib/poi_description.py's describers (PO19), dispatched by
-- poi_type as export_poi.py's DESCRIBERS dispatches them, each composing
-- only from ATC's own inventory columns, so every clause is a fact ATC
-- states. A clause whose column is blank or holds a value no vocabulary
-- knows (the poi_description_terms seed) is dropped rather than guessed:
-- the sentence gets shorter, never wrong. A sentence that would only repeat
-- the card's type line ("Shelter.", "Privy.") is no description.
-- - shelter: storeys, exterior material, "sleeps N" from the capacity
--   (reference/shelter_capacity.json, never ATC's number, and the clause is
--   omitted where nobody stands behind one), what it has (fireplace, fire
--   ring, bear-proof food storage, porch), and the year it was built where
--   the year is plausible;
-- - campsite: group or not, then how many sites, tent pads and platforms;
-- - viewpoint: the arc swept clockwise from left to right bearing, rounded
--   to 5 degrees and never below 5, "panoramic" from 300, its middle as one
--   of eight compass points, and the landform it is seen from;
-- - parking: what you park on and whether there is room;
-- - privy: type, multi-seat, and "open to the air" for one with no
--   enclosure;
-- - water: the synthesized CSI point's own sentence
--   (int_points_of_interest__water), and describe_stream_point()'s for
--   fetch_trail_water.py's site water, a point that carries `sources`: the
--   stream's name or "A stream", "where it runs closest to the site", then
--   the flow claim in the words of whichever hydrography made it
--   (FLOW_WORDS; no claim where nobody classified the reach, because
--   silence is not a promise of year-round water) and who else mapped it.
--   opentrail's water carries a title and an icon and composes nothing in
--   the Python either.
-- Each ends with ATC's own `Comments`, attributed ("ATC notes: ..."), after
-- lib/atc_notes.py's clean_note() has dropped the sentences that are the
-- survey talking to itself (PO20).
--
-- THE OTHER ORGANIZATIONS: export_nearby_poi.py's compose_description(): the
-- asset value, title-cased where the organization writes capitals, "in" the
-- facility, both already cleaned of sentinels; nothing where there is no
-- asset.
{%- set p = 'noted.properties' -%}
{%- set rounding = var('poi_vista_arc_rounding_degrees') %}
with enriched as (
    select * from {{ ref('int_points_of_interest__enriched') }}
),

terms as (
    select * from {{ ref('poi_description_terms') }}
),

noted as (
    select
        poi_id,
        poi_type,
        phone_files,
        properties,
        capacity,
        synthesized_description,
        asset,
        facility,
        {{ poi_note_kept_text(
            "json_extract_string(properties, '$.comments')"
        ) }} as note_text
    from enriched
),

read as (
    select
        noted.*,
        -- clean_note()'s last test: None where no letter or digit is left.
        case
            when regexp_matches(noted.note_text, '[\pL\pN]')
                then noted.note_text
        end as note,
        {{ poi_built_clause(p) }} as built_clause,
        {{ poi_count(p, 'chimneys') }} > 0 as has_fireplace,
        {{ poi_count(p, 'metal_fir') }}
        + {{ poi_count(p, 'mortared') }} > 0 as has_fire_ring,
        {{ poi_count(p, 'food_boxe') }}
        + {{ poi_count(p, 'food_cabl') }}
        + {{ poi_count(p, 'food_pole') }} > 0 as has_food_storage,
        {{ poi_count(p, 'deck_lengt') }} > 0 as has_porch,
        {{ poi_whole_count(p, 'site_num') }} as site_count,
        {{ poi_whole_count(p, 'tent_pads') }} as tent_pad_count,
        {{ poi_whole_count(p, 'tent_plat') }} as tent_platform_count,
        {{ poi_whole_count(p, 'parking_s') }} as car_count,
        {{ poi_whole_count(p, 'ada_space') }} as accessible_count,
        {{ poi_coded(p, 'type') }} as type_code,
        {{ poi_coded(p, 'enclosure') }} as enclosure_code,
        -- _view_arc(): both bearings must be numbers, and 0 and 0 is a vista
        -- nobody surveyed.
        json_type(noted.properties, '$.left_beari')
        in ('UBIGINT', 'BIGINT', 'DOUBLE')
        and json_type(noted.properties, '$.right_bear')
        in ('UBIGINT', 'BIGINT', 'DOUBLE')
        and not (
            try_cast(
                json_extract_string(noted.properties, '$.left_beari') as double
            ) = 0
            and try_cast(
                json_extract_string(noted.properties, '$.right_bear') as double
            ) = 0
        ) as has_arc,
        try_cast(
            json_extract_string(noted.properties, '$.left_beari') as double
        ) as left_bearing,
        try_cast(
            json_extract_string(noted.properties, '$.right_bear') as double
        ) as right_bearing,
        storeys.phrase as storeys_phrase,
        material.phrase as material_phrase,
        surface.phrase as surface_phrase,
        privy_kind.phrase as privy_kind,
        vista_location.phrase as location_phrase
    from noted
    left join terms as storeys
        on
            storeys.vocabulary = 'storeys'
            and cast({{ poi_whole_count(p, 'stories') }} as varchar)
            = storeys.code
    left join terms as material
        on
            material.vocabulary = 'exterior_material'
            and {{ poi_coded(p, 'exterior_m') }} = material.code
    left join terms as surface
        on
            surface.vocabulary = 'parking_surface'
            and {{ poi_coded(p, 'surface') }} = surface.code
    left join terms as privy_kind
        on
            privy_kind.vocabulary = 'privy_type'
            and {{ poi_coded(p, 'type') }} = privy_kind.code
    left join terms as vista_location
        on
            vista_location.vocabulary = 'vista_location'
            -- The first of a semicolon-separated list, stripped, lower-cased.
            and lower({{ python_strip(
                "split_part(" ~ poi_coded(p, 'location') ~ ", ';', 1)"
            ) }}) = vista_location.code
),

arcs as (
    -- _view_arc(): the width swept clockwise, with Python's float modulo
    -- (always in [0, 360)), a coincident pair the whole horizon.
    select
        read.*,
        case
            when read.has_arc
                then coalesce(
                    nullif(
                        (
                            (read.right_bearing - read.left_bearing) % 360
                            + 360
                        ) % 360,
                        0
                    ),
                    360
                )
        end as arc_width_raw
    from read
),

arc_parts as (
    -- Rounded half to even, as round() rounds, then never narrower than the
    -- rounding step; the middle bearing rounded the same way.
    select
        arcs.*,
        greatest(
            cast(
                round_even(arcs.arc_width_raw / {{ rounding }}, 0) as bigint
            ) * {{ rounding }},
            {{ rounding }}
        ) as arc_width,
        cast(
            round_even(
                ((arcs.left_bearing + arcs.arc_width_raw / 2) % 360 + 360)
                % 360,
                0
            ) as bigint
        ) as arc_middle
    from arcs
),

phrased as (
    select
        *,
        {{ poi_note_clause('note') }} as note_clause,
        -- FEATURES and CAMPSITE_FEATURES, in the order they read.
        list_filter(
            [
                case when has_fireplace then 'a fireplace' end,
                case when has_fire_ring then 'a fire ring' end,
                case
                    when has_food_storage
                        then 'bear-proof food storage'
                end,
                case when has_porch then 'a porch' end
            ],
            lambda phrase: phrase is not null
        ) as shelter_features,
        list_filter(
            [
                case when has_fire_ring then 'a fire ring' end,
                case
                    when has_food_storage
                        then 'bear-proof food storage'
                end
            ],
            lambda phrase: phrase is not null
        ) as campsite_features,
        list_filter(
            [
                case
                    when site_count > 0
                        then {{ poi_plural('site_count', "'site'") }}
                end,
                case
                    when tent_pad_count > 0
                        then {{ poi_plural(
                            'tent_pad_count', "'tent pad'"
                        ) }}
                end,
                case
                    when tent_platform_count > 0
                        then {{ poi_plural(
                            'tent_platform_count', "'tent platform'"
                        ) }}
                end
            ],
            lambda phrase: phrase is not null
        ) as campsite_counts,
        list_filter(
            [
                case
                    when car_count > 0
                        then
                            'room for '
                            || {{ poi_plural('car_count', "'car'") }}
                end,
                case
                    when accessible_count > 0
                        then {{ poi_plural(
                            'accessible_count', "'accessible space'"
                        ) }}
                end
            ],
            lambda phrase: phrase is not null
        ) as parking_counts,
        concat_ws(
            ' ', storeys_phrase, material_phrase, 'shelter'
        ) as shelter_head,
        concat_ws(
            ' ',
            case when enclosure_code = '2' then 'Multi-seat' end,
            privy_kind,
            'privy'
        ) as privy_head,
        case
            when not has_arc
                then
                    case
                        when location_phrase is not null
                            then 'A view'
                    end
            when arc_width >= {{ var('poi_vista_panorama_degrees') }}
                then 'A panoramic view'
            else
                -- _article(): read aloud, 80 is "eighty" and 180 is "one
                -- hundred and eighty".
                case
                    when
                        left(cast(arc_width as varchar), 1) = '8'
                        and arc_width < 100
                        then 'An'
                    else 'A'
                end
                || ' '
                || cast(arc_width as varchar)
                || '° view '
                || list_extract(
                    {{ var('poi_compass_points') }},
                    cast(
                        floor((arc_middle % 360) / 45.0 + 0.5)
                        as bigint
                    ) % 8 + 1
                )
        end as vista_head
    from arc_parts
),

sentences as (
    select
        phrased.*,
        case phrased.poi_type
            when 'shelter'
                then
                    upper(left(phrased.shelter_head, 1))
                    || substr(phrased.shelter_head, 2)
                    || coalesce(
                        ', sleeps ' || cast(phrased.capacity as varchar), ''
                    )
                    || case
                        when len(phrased.shelter_features) > 0
                            then ', with ' || {{ poi_join_phrases(
                                'phrased.shelter_features'
                            ) }}
                        else ''
                    end
                    || '.'
                    || phrased.built_clause
                    || phrased.note_clause
            when 'campsite'
                then
                    case
                        when phrased.type_code = '1'
                            then 'Designated group campsite'
                        else 'Designated campsite'
                    end
                    || case
                        when len(phrased.campsite_counts) > 0
                            then ', ' || {{ poi_join_phrases(
                                'phrased.campsite_counts'
                            ) }}
                        else ''
                    end
                    || case
                        when len(phrased.campsite_features) > 0
                            then ', with ' || {{ poi_join_phrases(
                                'phrased.campsite_features'
                            ) }}
                        else ''
                    end
                    || '.'
                    || phrased.note_clause
            when 'parking'
                then
                    case
                        when phrased.type_code = 'Roadside/Shoulder'
                            then 'Roadside parking'
                        when phrased.surface_phrase is not null
                            then
                                upper(left(phrased.surface_phrase, 1))
                                || lower(substr(phrased.surface_phrase, 2))
                                || ' parking area'
                        else 'Parking area'
                    end
                    || case
                        when len(phrased.parking_counts) > 0
                            then ', ' || {{ poi_join_phrases(
                                'phrased.parking_counts'
                            ) }}
                        else ''
                    end
                    || '.'
                    || phrased.note_clause
            when 'privy'
                then
                    upper(left(phrased.privy_head, 1))
                    || substr(phrased.privy_head, 2)
                    || case
                        when phrased.enclosure_code = '0'
                            then ', open to the air with no enclosure'
                        else ''
                    end
                    || '.'
                    || phrased.built_clause
                    || phrased.note_clause
            when 'viewpoint'
                then
                    case
                        when phrased.vista_head is null
                            then nullif(trim(phrased.note_clause), '')
                        else
                            phrased.vista_head
                            || coalesce(' from ' || phrased.location_phrase, '')
                            || '.'
                            || phrased.note_clause
                    end
        end as atc_sentence
    from phrased
),

stream_terms as (
    -- STREAM_SOURCES, STREAM_CLAIMS and FLOW_WORDS as three maps.
    select
        map(
            list(code order by code) filter (
                where vocabulary = 'stream_source'
            ),
            list(phrase order by code) filter (
                where vocabulary = 'stream_source'
            )
        ) as source_names,
        map(
            list(code order by code) filter (
                where vocabulary = 'stream_claim'
            ),
            list(phrase order by code) filter (
                where vocabulary = 'stream_claim'
            )
        ) as claims,
        map(
            list(code order by code) filter (
                where vocabulary = 'stream_flow'
            ),
            list(phrase order by code) filter (
                where vocabulary = 'stream_flow'
            )
        ) as flow_words
    from terms
),

streams as (
    -- describe_water() hands a point with `sources` to
    -- describe_stream_point().
    select
        noted.poi_id,
        json_extract_string(noted.properties, '$.sources[*]') as sources,
        coalesce(
            nullif(json_extract_string(noted.properties, '$.name'), ''),
            'A stream'
        ) as subject,
        map_extract_value(
            stream_terms.flow_words,
            coalesce(json_extract_string(noted.properties, '$.flow'), '')
        ) as flow_word,
        json_extract_string(noted.properties, '$.flow_source') as flow_source,
        stream_terms.source_names,
        stream_terms.claims
    from noted
    cross join stream_terms
    where
        noted.phone_files = 'poi_by_type'
        and noted.poi_type = 'water'
        and coalesce(json_array_length(noted.properties, '$.sources'), 0) > 0
),

claimed as (
    -- The flow claim is attributed to whoever made it, and only where a
    -- flow word exists.
    select
        streams.*,
        case
            when
                streams.flow_word is not null
                and coalesce(
                    map_contains(streams.source_names, streams.flow_source),
                    false
                )
                then streams.flow_source
        end as claimant
    from streams
),

stream_sentences as (
    select
        poi_id,
        subject
        || ', where it runs closest to the site.'
        || case
            when claimant is not null
                then
                    ' '
                    || map_extract_value(source_names, claimant)
                    || ' '
                    || map_extract_value(claims, claimant)
                    || ' '
                    || flow_word
                    || '.'
                    || case
                        when
                            len(list_filter(
                                sources,
                                lambda source: source != claimant
                                and map_contains(source_names, source)
                            )) > 0
                            then
                                ' Also mapped by '
                                || {{ poi_join_phrases(
                                    "list_transform(list_filter(sources, "
                                    ~ "lambda source: source != claimant "
                                    ~ "and map_contains(source_names, source)), "
                                    ~ "lambda source: "
                                    ~ "map_extract_value(source_names, source))"
                                ) }}
                                || '.'
                        else ''
                    end
            when
                len(list_filter(
                    sources, lambda source: map_contains(source_names, source)
                )) > 0
                then
                    ' Mapped by '
                    || {{ poi_join_phrases(
                        "list_transform(list_filter(sources, "
                        ~ "lambda source: map_contains(source_names, source)), "
                        ~ "lambda source: "
                        ~ "map_extract_value(source_names, source))"
                    ) }}
                    || '.'
            else ''
        end as stream_sentence
    from claimed
),

with_streams as (
    select
        sentences.*,
        stream_sentences.stream_sentence
    from sentences
    left join stream_sentences on sentences.poi_id = stream_sentences.poi_id
),

described as (
    select
        poi_id,
        case
            when phone_files = 'nearby_poi'
                then
                    case
                        when asset is not null
                            then
                                case
                                    when {{ python_isupper('asset') }}
                                        then {{ python_title('asset') }}
                                    else asset
                                end
                                || coalesce(' in ' || facility, '')
                                || '.'
                    end
            when synthesized_description is not null
                then synthesized_description
            when stream_sentence is not null then stream_sentence
            -- The sentences that would only repeat the card's type line.
            when
                atc_sentence in (
                    'Shelter.',
                    'Privy.',
                    'Parking area.',
                    'Designated campsite.',
                    'Designated group campsite.'
                )
                then null
            else atc_sentence
        end as description
    from with_streams
)

select
    enriched.*,
    described.description
from enriched
inner join described on enriched.poi_id = described.poi_id
