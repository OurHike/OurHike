{{ config(materialized='table') }}
{%- set bound_mi = 0.37 %}
{%- set shown_bound_mi = '0.4' %}
-- GATC's water list placed on the A.T. from GATC's own mile points (decision
-- 75, the maintainer's poll of 2026-10-04: publish now, at low confidence,
-- placed from GATC's miles, with the document's date), each held where the
-- placement cannot be stood behind. One row per row of
-- stg_gatc__water_sources, typed as a record the POI family reads whole
-- (int_points_of_interest__unioned's GATC branch), as
-- int_points_of_interest__club_points' rows are.
--
-- WHAT GATC'S MILES COUNT FROM, measured 2026-10-04 rather than assumed:
-- the live PDF (sha256 e070c586..., Last-Modified 2026-03-02, embedded title
-- "GATC Water Update July 2020.xlsx"), parsed by lib/club_pdfs.py, against
-- ATC's live centerline (3,025 segments) and half-mile markers (4,395) made
-- into export_elevation.calibrated_trail_axis, the axis every published A.T.
-- mile comes off and int_trail_lines__mile_axis is held to. The A.T. list
-- counts northbound from Springer Mountain's summit (ATC's axis starts there
-- at 0.009): its Springer Mountain Shelter is GATC's 0.2 and ATC's 0.234. It
-- follows ATC's marker miles, not the centerline's own length: at the six
-- named places whose ATC point sits on the centerline (Three Forks, Justus
-- Creek, Woody Gap, Lance Creek, Neel Gap, Hogpen Gap: road crossings and
-- creek campsites, 12 to 41 m off it) GATC's mile and ATC's agree within
-- 0.122 mi through mile 38.3, where the geometric length from Springer is
-- 0.07 to 0.43 mi short of GATC's. North of Low Gap the shelters read 0.18
-- to 0.33 mi short of ATC's axis (Tray Mountain Shelter: GATC 58.1, ATC
-- 58.428), which a reroute since GATC measured, or the list's 2020 date,
-- would explain (Reasoned, not checked). So a mile is read straight off ATC's
-- axis, GATC's 20.7 as ATC's 20.7: what the measurement shows a GATC mile
-- is, with its disagreement carried rather than fitted away. The approach
-- trail's four rows count from Amicalola Falls along a trail the axis does
-- not carry, so they are held.
--
-- THE CHECK, against ATC's own points of the same name: ATC publishes no
-- water layer (WATER_SOURCES.md §4), so a source is checked against the
-- shelter, campsite or road gap's lot it is named for, the
-- gatc_water_atc_names seed's 18 pairs, each read onto the same axis. Their
-- disagreement along the trail, |GATC's mile - the namesake's axis mile|,
-- measured 2026-10-04: median 0.121 mi, worst 0.407 mi (Hawk Mountain's tent
-- sites against ATC's Hawk Mtn Campsite). The straight-line offset from the
-- placed point to the namesake: median 226 m, worst 1,490 m (Whitley Gap
-- Shelter, which is 1,455 m off the centerline down its side trail).
-- THE BOUND, {{ bound_mi }} mi, is derived from those 18 rather than picked:
-- Tukey's upper fence, Q3 + 1.5 IQR, is 0.3718 mi (Q1 0.0630, Q3 0.1865,
-- numpy's linear percentiles), rounded down so a borderline source is held.
-- One of the 18 lies past it, Hawk Mountain's tent sites, and is held: GATC
-- puts that water 0.4 mi W down a blue blaze past the tent sites, ATC's
-- campsite sits 85 m off the centerline, and nothing here says which is
-- right. The widest the bound passes is Tray Mountain Shelter's 0.328 mi.
-- The 43 sources with no namesake are placed on the measurement as a whole
-- and checked by nothing per source.
--
-- WHAT A CARD SAYS (CLAUDE.md, "Never let a display outrun its source"):
-- `description` says the point is placed from GATC's mile and not surveyed,
-- that the spot can be up to {{ shown_bound_mi }} mi off (the bound, rounded
-- up), and the document's own date and title, so "July 2020" reaches the
-- card beside 2026-03-02. Every source ships `low`, which the phone draws
-- hollow and the card says in words. `position_error_m` is the bound in
-- metres, and `placement` 'gatc_mile' names how the point was made, as the
-- Long Path guide's 'interpolated' does. `name` is GATC's entry whole: its
-- directions off the trail are the only way a hiker gets from the pin, which
-- marks the mile on the tread, to water down a side trail.
--
-- THE OTHER HOLDS, each the first reason a row gets:
-- - a mile no piece of the axis carries (a gap between pieces, or past the
--   axis's end), never moved to the nearest piece;
-- - a layer_rules `drop_where_contains` row on `entry`: GATC's own words say
--   the source is not water to rely on (Stover Creek Shelter's "Typically
--   very low or dry", where its next row is the creek GATC sends a hiker
--   to);
-- - its namesake reading more than the bound from GATC's mile.
-- A spigot (Neel Gap's) carries `water_source_kind` 'spigot', which the
-- layer_rules `plumbed_water` row reads in int_points_of_interest__cautioned
-- for decision 65's season caution.
--
-- A MILE TO A POINT: the piece whose calibrated range holds the mile (the
-- lower piece_id where two overlap, as axis_mile breaks a tie), and the
-- along-distance mile_at_along would read that mile at, inverted branch for
-- branch: unit slope before the first anchor and past the last, and the
-- interval between the last anchor at or below the mile and the next. A
-- zero-length piece carries nothing. `placed_mile` reads the point back
-- through axis_mile, and this model's test holds it to GATC's mile.
with sources as (
    select * from {{ ref('stg_gatc__water_sources') }}
),

axis as (
    select * from {{ ref('int_trail_lines__mile_axis') }}
    where length_m > 0
),

dry_rules as (
    select * from {{ ref('layer_rules') }}
    where
        source_key = 'gatc_water_sources'
        and rule = 'drop_where_contains'
),

carried as (
    -- The piece that carries each A.T. source's mile.
    select
        sources.water_source_key,
        sources.mile,
        axis.piece_id,
        axis.geom_5070,
        axis.length_m,
        axis.anchor_along_mi,
        axis.anchor_mile
    from sources
    inner join axis
        on
            sources.trail = 'at'
            and sources.mile between axis.start_mile and axis.end_mile
    qualify
        row_number() over (
            partition by sources.water_source_key order by axis.piece_id
        ) = 1
),

carriers as (
    -- How many of the piece's anchors sit at or below the mile.
    select
        *,
        len(anchor_mile) as anchors,
        len(list_filter(anchor_mile, lambda anchor: anchor <= mile)) as below
    from carried
),

alongs as (
    select
        water_source_key,
        piece_id,
        geom_5070,
        length_m,
        case
            when anchors = 1 or below = 0
                then
                    list_extract(anchor_along_mi, 1)
                    + (mile - list_extract(anchor_mile, 1))
            when below = anchors
                then
                    list_extract(anchor_along_mi, -1)
                    + (mile - list_extract(anchor_mile, -1))
            else
                list_extract(anchor_along_mi, below)
                + (mile - list_extract(anchor_mile, below))
                * (
                    list_extract(anchor_along_mi, below + 1)
                    - list_extract(anchor_along_mi, below)
                )
                / (
                    list_extract(anchor_mile, below + 1)
                    - list_extract(anchor_mile, below)
                )
        end * {{ var('mile_axis_metres_per_mile') }} as along_m
    from carriers
),

placed as (
    select
        water_source_key,
        piece_id,
        st_lineinterpolatepoint(
            geom_5070, greatest(0.0, least(1.0, along_m / length_m))
        ) as point_5070
    from alongs
),

read_back as {{ axis_mile('placed', ['water_source_key'], 'point_5070') }},

namesake_points as (
    select
        gatc_mile,
        entry_starts,
        atc_layer,
        atc_name,
        atc_global_id,
        st_transform(
            atc_geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as point_5070
    from {{ ref('int_points_of_interest__gatc_water_namesakes') }}
),

namesake_miles as {{ axis_mile(
    'namesake_points',
    ['gatc_mile', 'entry_starts', 'atc_layer', 'atc_name', 'atc_global_id'],
    'point_5070'
) }},

namesakes as (
    -- Each source's namesake, the nearer along the axis where ATC uses the
    -- Name twice.
    select
        sources.water_source_key,
        namesake_miles.atc_layer,
        namesake_miles.atc_name,
        abs(sources.mile - namesake_miles.mile) as gap_mi
    from sources
    inner join namesake_miles
        on
            sources.mile_text = namesake_miles.gatc_mile
            and starts_with(sources.entry, namesake_miles.entry_starts)
    qualify
        row_number() over (
            partition by sources.water_source_key
            order by abs(sources.mile - namesake_miles.mile)
        ) = 1
),

source_rows as (
    -- Each row as JSON, so a rule reads a field by the name its seed row gives.
    select
        water_source_key,
        to_json(sources) as row_json
    from sources
),

dry as (
    select
        source_rows.water_source_key,
        min(
            'layer_rules drop_where_contains: '
            || dry_rules.field
            || ' contains '
            || dry_rules.matches
        ) as reason
    from source_rows
    inner join dry_rules
        on contains(
            lower(
                json_extract_string(
                    source_rows.row_json, '$.' || dry_rules.field
                )
            ),
            lower(dry_rules.matches)
        )
    group by source_rows.water_source_key
),

judged as (
    select
        sources.*,
        placed.piece_id,
        st_transform(
            placed.point_5070, 'EPSG:5070', 'EPSG:4326', always_xy := true
        ) as placed_point,
        read_back.mile as read_back_mile,
        namesakes.atc_layer as namesake_layer,
        namesakes.atc_name as namesake_name,
        namesakes.gap_mi as namesake_gap_mi,
        case
            when sources.trail = 'approach'
                then
                    'approach trail: GATC counts these miles from Amicalola '
                    || 'Falls, along a trail ATC''s mile axis does not carry'
            when placed.water_source_key is null
                then
                    'no piece of ATC''s mile axis carries GATC''s mile '
                    || sources.mile_text
            when dry.reason is not null then dry.reason
            when namesakes.gap_mi > {{ bound_mi }}
                then
                    'ATC''s '
                    || namesakes.atc_layer
                    || ' point '
                    || namesakes.atc_name
                    || ' reads '
                    || printf('%.3f', namesakes.gap_mi)
                    || ' mi along the trail from GATC''s mile '
                    || sources.mile_text
                    || ', past the {{ bound_mi }} mi bound'
        end as rule_drop_reason,
        coalesce(
            try_strptime(left(sources.document_created, 10), '%Y-%m-%d'),
            try_strptime(
                sources.document_last_modified, '%a, %d %b %Y %H:%M:%S GMT'
            )
        ) as document_date,
        nullif(
            trim(
                regexp_replace(
                    sources.document_title, '\.(xlsx?|docx?|pdf)$', '', 'i'
                )
            ),
            ''
        ) as document_name
    from sources
    left join placed on sources.water_source_key = placed.water_source_key
    left join read_back
        on sources.water_source_key = read_back.water_source_key
    left join namesakes
        on sources.water_source_key = namesakes.water_source_key
    left join dry on sources.water_source_key = dry.water_source_key
),

described as (
    select
        judged.*,
        -- Only on a source that ships: a held one has no point to describe.
        case
            when judged.rule_drop_reason is null
                then
                    'Water source at GATC''s mile '
                    || judged.mile_text
                    || ' on the A.T., placed from that mile and not '
                    || 'surveyed, so the spot can be up to '
                    || '{{ shown_bound_mi }} mi off. From GATC''s water list'
                    || coalesce(
                        ', a PDF of '
                        || strftime(judged.document_date, '%Y-%m-%d')
                        || coalesce(
                            ' titled "' || judged.document_name || '"', ''
                        ),
                        ''
                    )
                    || '.'
        end as description,
        regexp_matches(lower(judged.entry), '\bspigot\b') as is_spigot
    from judged
)

select
    water_source_key as poi_key,
    source_key,
    club,
    entry as name,
    source_id,
    source_key || ':' || source_id as derived_id,
    'water' as poi_type,
    'low' as confidence,
    rule_drop_reason,
    trail,
    mile_text as gatc_mile,
    printf('%.3f', read_back_mile) as placed_mile,
    piece_id as placed_piece_id,
    namesake_layer,
    namesake_name,
    printf('%.3f', namesake_gap_mi) as namesake_gap_mi,
    description,
    'gatc_mile' as placement,
    document_url as source_url,
    cast(
        round({{ bound_mi }} * {{ var('mile_axis_metres_per_mile') }})
        as integer
    ) as position_error_m,
    case when is_spigot then 'spigot' end as water_source_kind,
    st_astext(placed_point) as geom_wkt,
    json_object(
        'trail', trail,
        'gatc_mile', mile_text,
        'on_at_axis', placed_point is not null,
        'water_source_kind', case when is_spigot then 'spigot' end,
        'document_url', document_url,
        'document_title', document_title
    ) as properties,
    _loaded_at
from described
