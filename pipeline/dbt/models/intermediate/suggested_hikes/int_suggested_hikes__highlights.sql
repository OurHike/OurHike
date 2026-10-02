-- The curated highlights resolved against the published POIs: one row per
-- row of reference/highlights.json, in the file's order, with the first rule
-- it breaks (`problem`, null where it publishes) in lib/highlights.py's
-- resolve()'s words and order (SH12, SH13). A row with a problem publishes
-- nothing: the mart takes only the rows with none, and a curated list
-- quietly shrinking is the failure nobody notices, so the `warn` test on
-- `problem` names every row dropped, as export_highlights.py prints them.
--
-- THE RULES, IN resolve()'S ORDER:
-- 1. an id that is a non-empty string, or "entry has no id";
-- 2. the first row to carry an id claims it, even when that row then fails a
--    later rule: a second is a "duplicate id", an editing accident that
--    would silently win a dict-keyed consumer;
-- 3. a name that is a non-empty string;
-- 4. legs that are a non-empty list;
-- 5. ALL LEGS OR NONE: the first leg that fails decides the row, because half
--    a walk drawn is a walk that ends where nothing ends. A leg is an object
--    naming a trail and two POIs, its from_poi checked before its to_poi,
--    each a published POI with a mile; both ends at one mile is no walk.
--
-- A LEG'S MILES COME FROM THE PUBLISHED POIs
-- (int_suggested_hikes__published_pois),
-- never from a figure typed into the file: the reference file holds no mile
-- at all, and an end that cannot be placed is refused rather than guessed.
-- The ends are ordered, so a leg never runs backwards, and each is cut to 2
-- decimals with printf, as as_published() rounds them with round(x, 2).
--
-- SH14, NOTHING DERIVED IS STORED: no length, no ascent, no Naismith time.
-- The phone derives all three from the elevation profile it already holds,
-- so a better profile improves every highlight without a republish.
--
-- `club` is the maintaining club whose stretch the first leg starts in,
-- derived rather than written down, so "about thirty, one per maintaining
-- club" is a fact this can check: the first stretch, in club_sections.json's
-- order, with start <= mile < end (half-open, as client/src/lib/clubSections.ts
-- reads it, so a mile two clubs share resolves northbound).
--
-- A row that is not a JSON object is "not an object", which resolve() does
-- not survive (entry.get raises): the error test on `problem` fails the
-- build on it, as the Python fails the run.
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
        -- `seen`: the id is claimed by the first row carrying it, whatever
        -- happens to that row next.
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
    -- club_for_mile(): the first stretch, by club and then by stretch, whose
    -- half-open range holds the first leg's low end. Its acronym, null where
    -- the file's is not a string: club_for_mile() answers None at the first
    -- stretch that matches and looks no further, so arg_min_null, which
    -- keeps a null, never arg_min, which would pass it for the next club's.
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
)

select
    decided.file_row,
    -- The id a dropped row is reported under: resolve()'s "<no id>" for a
    -- row with none.
    case
        when decided.problem in ('not an object', 'entry has no id')
            then '<no id>'
        else decided.highlight_id
    end as highlight_id,
    decided.highlight_name,
    decided.note,
    decided.reviewed,
    case when decided.problem is null then decided.legs_json end as legs_json,
    case when decided.problem is null then first_stretch.acronym end as club,
    decided.problem,
    decided._loaded_at
from decided
left join first_stretch on decided.file_row = first_stretch.file_row
