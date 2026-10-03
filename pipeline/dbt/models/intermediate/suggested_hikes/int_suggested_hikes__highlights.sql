-- The curated highlights resolved against the published POIs: one row per
-- row of reference/highlights.json, in file order, with the first rule it
-- breaks (`problem`, null where it publishes) in lib/highlights.py's
-- resolve()'s words and order (SH12, SH13). A curated list quietly
-- shrinking is the failure nobody notices, so the `warn` test on `problem`
-- names every dropped row, as export_highlights.py prints them.
--
-- Rules, in resolve()'s order (the `decided` and `leg_checks` CTEs): an id;
-- no earlier row with that id (a "duplicate id" is an editing accident that
-- would silently win in a consumer keyed by id, and the first row keeps the
-- id even if it then fails); a name; legs. All legs or none: the first
-- failing leg decides the row, because half a walk drawn is a walk that
-- ends where nothing ends. A row that is not a JSON object fails the build
-- through the error test on `problem`, as resolve() raises on it.
--
-- A leg's miles come only from the published POIs
-- (int_suggested_hikes__published_pois): the reference file holds no mile,
-- and an end that cannot be placed is refused rather than guessed. The ends
-- are ordered, so a leg never runs backwards, and cut to 2 decimals as
-- as_published()'s round(x, 2) cuts them.
--
-- SH14, nothing derived is stored: no length, ascent or Naismith time. The
-- phone derives all three from the elevation profile it holds, so a better
-- profile improves every highlight without a republish.
--
-- `club` is the maintaining club whose stretch the first leg starts in (the
-- `first_stretch` CTE), derived rather than typed in, so "about thirty, one
-- per maintaining club" is a fact this can check.
with entries as (
    select * from {{ ref('base_ourhike__highlights') }}
),

published_miles as (
    -- poi_miles(): an id that is a non-empty string, and a mile.
    select
        poi_id,
        mile
    from {{ ref('int_suggested_hikes__published_pois') }}
    where poi_id != '' and mile is not null
),

stretches as (
    select * from {{ ref('int_suggested_hikes__club_stretches') }}
),

read_entries as (
    select
        file_row,
        highlight,
        _loaded_at,
        json_type(highlight) = 'OBJECT' as is_object,
        case
            when json_type(json_extract(highlight, '$.id')) = 'VARCHAR'
                then json_extract_string(highlight, '$.id')
        end as highlight_id,
        case
            when json_type(json_extract(highlight, '$.name')) = 'VARCHAR'
                then json_extract_string(highlight, '$.name')
        end as highlight_name,
        json_type(json_extract(highlight, '$.legs')) = 'ARRAY'
        and json_array_length(json_extract(highlight, '$.legs'))
        > 0 as has_legs,
        -- note and reviewed: the file's string, or "" (as_published()).
        case
            when json_type(json_extract(highlight, '$.note')) = 'VARCHAR'
                then json_extract_string(highlight, '$.note')
            else ''
        end as note,
        case
            when json_type(json_extract(highlight, '$.reviewed')) = 'VARCHAR'
                then json_extract_string(highlight, '$.reviewed')
            else ''
        end as reviewed
    from entries
),

claimed as (
    select
        *,
        coalesce(highlight_id, '') != '' as has_id,
        -- resolve()'s `seen`: the first row with an id keeps it.
        row_number() over (
            partition by
                case when coalesce(highlight_id, '') != '' then highlight_id end
            order by file_row
        ) as id_claim
    from read_entries
),

legs as (
    select
        file_row,
        unnest(
            cast(json_extract(highlight, '$.legs') as json[])
        ) as leg,
        generate_subscripts(
            cast(json_extract(highlight, '$.legs') as json[]), 1
        ) as leg_position
    from claimed
    where has_legs
),

leg_fields as (
    select
        file_row,
        leg_position,
        json_type(leg) = 'OBJECT' as leg_is_object,
        case
            when json_type(json_extract(leg, '$.trail')) = 'VARCHAR'
                then json_extract_string(leg, '$.trail')
        end as trail,
        case
            when json_type(json_extract(leg, '$.from_poi')) = 'VARCHAR'
                then json_extract_string(leg, '$.from_poi')
        end as from_poi,
        case
            when json_type(json_extract(leg, '$.to_poi')) = 'VARCHAR'
                then json_extract_string(leg, '$.to_poi')
        end as to_poi
    from legs
),

leg_miles as (
    select
        leg_fields.*,
        from_miles.mile as from_mile,
        to_miles.mile as to_mile
    from leg_fields
    left join published_miles as from_miles
        on leg_fields.from_poi = from_miles.poi_id
    left join published_miles as to_miles
        on leg_fields.to_poi = to_miles.poi_id
),

leg_checks as (
    select
        file_row,
        leg_position,
        trail,
        least(from_mile, to_mile) as start_mile,
        greatest(from_mile, to_mile) as end_mile,
        -- _leg_from(), in its order.
        case
            when not leg_is_object then 'a leg is not an object'
            when coalesce(trail, '') = '' then 'a leg names no trail'
            when coalesce(from_poi, '') = '' then 'a leg names no from_poi'
            when from_mile is null
                then 'from_poi ' || from_poi || ' has no published mile'
            when coalesce(to_poi, '') = '' then 'a leg names no to_poi'
            when to_mile is null
                then 'to_poi ' || to_poi || ' has no published mile'
            when from_mile = to_mile then 'both ends resolve to the same mile'
        end as leg_problem
    from leg_miles
),

entry_legs as (
    select
        file_row,
        arg_min(leg_problem, leg_position) filter (
            where leg_problem is not null
        ) as first_leg_problem,
        -- The first leg's low end, which `club` is read from.
        arg_min(start_mile, leg_position) as first_start_mile,
        to_json(
            list(
                json_object(
                    'trail', trail,
                    'start_mile', cast(printf('%.2f', start_mile) as double),
                    'end_mile', cast(printf('%.2f', end_mile) as double)
                )
                order by leg_position
            )
        ) as legs_json
    from leg_checks
    group by file_row
),

decided as (
    select
        claimed.file_row,
        claimed._loaded_at,
        claimed.highlight_id,
        claimed.highlight_name,
        claimed.note,
        claimed.reviewed,
        entry_legs.legs_json,
        entry_legs.first_start_mile,
        case
            when not claimed.is_object then 'not an object'
            when not claimed.has_id then 'entry has no id'
            when claimed.id_claim > 1 then 'duplicate id'
            when coalesce(claimed.highlight_name, '') = ''
                then 'entry has no name'
            when not claimed.has_legs then 'entry has no legs'
            else entry_legs.first_leg_problem
        end as problem
    from claimed
    left join entry_legs on claimed.file_row = entry_legs.file_row
),

first_stretch as (
    -- club_for_mile(): the first stretch, by club then stretch order, whose
    -- range holds the first leg's low end, half-open (start <= mile < end,
    -- as client/src/lib/clubSections.ts reads it, so a mile two clubs share
    -- goes to the stretch that starts there). club_for_mile() stops at the
    -- first match and answers None when its acronym is not a string, so
    -- this is arg_min_null, which keeps that null, never arg_min, which
    -- would skip to the next club's.
    select
        decided.file_row,
        arg_min_null(
            stretches.acronym, [stretches.club_order, stretches.stretch_order]
        ) as acronym
    from decided
    inner join stretches
        on
            decided.first_start_mile >= stretches.start_mile
            and decided.first_start_mile < stretches.end_mile
    where decided.problem is null
    group by decided.file_row
),

resolved as (
    select
        decided.file_row,
        -- The id a dropped row is reported under: resolve()'s "<no id>" for
        -- a row with none.
        case
            when decided.problem in ('not an object', 'entry has no id')
                then '<no id>'
            else decided.highlight_id
        end as highlight_id,
        decided.highlight_name,
        decided.note,
        decided.reviewed,
        case
            when decided.problem is null then decided.legs_json
        end as legs_json,
        case
            when decided.problem is null then first_stretch.acronym
        end as club,
        decided.problem,
        decided._loaded_at
    from decided
    left join first_stretch on decided.file_row = first_stretch.file_row
)

select
    *,
    -- as_published(): the record highlights.json carries, as JSON text. It
    -- names its basis and never says "popular": `bases` is `named`, cited to
    -- OurHike with the reviewer's note and date.
    case
        when problem is null
            then
                cast(
                    json_object(
                        'id', highlight_id,
                        'name', highlight_name,
                        'bases', ['{{ var("highlights_basis") }}'],
                        'citations',
                        json_object(
                            '{{ var("highlights_basis") }}',
                            json_object(
                                'by', '{{ var("highlights_cited_by") }}',
                                'note', note,
                                'reviewed', reviewed
                            )
                        ),
                        'legs', cast(legs_json as json),
                        'club', club
                    ) as varchar
                )
    end as record_json
from resolved
