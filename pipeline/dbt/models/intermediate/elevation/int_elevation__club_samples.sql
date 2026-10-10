{{ config(materialized='table') }}
-- Every elevation the clubs' registered elevation layers publish, one row per
-- sample, in metres and in feet: decision 54's wave 1 elevation layers
-- (int_elevation__unioned), read the way each layer's sources.json row says.
-- No mart reads this yet; every layer here is held back by its row
-- (`reaches_hikers: false`).
--
-- WHAT A SAMPLE IS, by the row's `elevation_source`:
-- - `geometry Z`: one sample per vertex, its Z (ATC's ATX centerline). A
--   feature with no geometry has no sample (18 of ATX's 697 rows have none);
--   a vertex with no Z has a sample with no elevation.
-- - `field <name>`: one sample per feature, the field staging carried as
--   `published_elevation`. A number is an elevation. PCTA's two band layers
--   publish a label instead ('0 - 1000 ft', '13000 ft +', twelve of the
--   fourteen with a minus sign, U+2212, not a hyphen): the label's bounds
--   are band_low_ft and band_high_ft, the top band open, and the sample has
--   no single elevation. A value that is neither is kept, with no elevation.
--
-- THE RULES (pipeline/ELT.md, "What wave 1's live reads found that phase C
-- must honour"), each a unit test in _elevation__club_samples_unit_tests.yml:
-- - UNITS PER ROW. Each sample carries its own layer's `elevation_unit` and
--   is converted by it: ATC's ATX Z is metres, NCTA's, NJDEP's, PASDA's and
--   PCTA's are feet (each row's elevation_unit_comment has the 3DEP check
--   that settled it). A layer whose row names no unit has no elevation_m and
--   no elevation_ft: absent is unknown, never a guessed unit. Both are text,
--   cut at 2 decimals with printf (the dbt skill: a unit test compares a
--   DOUBLE only to one decimal, and printf matches Python's rounding); the
--   foot is 0.3048 m exactly.
-- - TWO DIMENSIONS. geom_wkt is ST_Force2D of the sample's point or feature,
--   so a Z-enabled line's heights never ride into a network built from it.
-- - NO CALIBRATION FROM AN UNCHECKED Z. checked_against_dem is false on
--   every row, because no step in this build compares these samples with
--   3DEP: the registry's elevation_unit_comment records a check of a few
--   vertices that settled each layer's unit, not a check of each vertex. ATX
--   is editable by anyone (its notes: anonymous update and delete allowed),
--   so its Z can change without ATC changing it. usable_for_calibration is
--   true only on a checked sample with an elevation, so it is false on every
--   row until such a step exists.
with unioned as (
    select * from {{ ref('int_elevation__unioned') }}
),

registry as (
    select
        source_key,
        json_extract_string(entry, '$.elevation_source') as elevation_source,
        json_extract_string(entry, '$.elevation_unit') as elevation_unit
    from {{ ref('stg_registry__sources') }}
),

layers as (
    select
        unioned.source_key,
        unioned.club,
        unioned.elevation_feature_key,
        unioned.published_elevation,
        unioned.geom,
        unioned._loaded_at,
        registry.elevation_source,
        registry.elevation_unit
    from unioned
    left join registry on unioned.source_key = registry.source_key
),

-- One row per vertex of a layer whose elevation is its geometry's Z.
vertices as (
    select
        source_key,
        club,
        elevation_feature_key,
        elevation_source,
        elevation_unit,
        _loaded_at,
        unnest(st_dump(st_points(geom))) as vertex
    from layers
    where elevation_source = 'geometry Z' and geom is not null
),

z_samples as (
    select
        source_key,
        club,
        elevation_feature_key,
        elevation_source,
        elevation_unit,
        _loaded_at,
        struct_extract(vertex, 'path')[1] as sample_seq,
        st_force2d(struct_extract(vertex, 'geom')) as geom_2d,
        cast(st_z(struct_extract(vertex, 'geom')) as varchar)
            as elevation_as_published,
        st_z(struct_extract(vertex, 'geom')) as elevation_value,
        cast(null as integer) as band_low_ft,
        cast(null as integer) as band_high_ft
    from vertices
),

-- One row per feature of a layer whose elevation is one of its fields.
field_samples as (
    select
        source_key,
        club,
        elevation_feature_key,
        elevation_source,
        elevation_unit,
        _loaded_at,
        1 as sample_seq,
        st_force2d(geom) as geom_2d,
        published_elevation as elevation_as_published,
        try_cast(published_elevation as double) as elevation_value,
        coalesce(
            try_cast(regexp_extract(
                published_elevation,
                '^\s*([0-9]+)\s*[-−–]\s*[0-9]+\s*ft\s*$', 1
            ) as integer),
            try_cast(regexp_extract(
                published_elevation, '^\s*([0-9]+)\s*ft\s*\+\s*$', 1
            ) as integer)
        ) as band_low_ft,
        try_cast(regexp_extract(
            published_elevation, '^\s*[0-9]+\s*[-−–]\s*([0-9]+)\s*ft\s*$', 1
        ) as integer) as band_high_ft
    from layers
    where starts_with(elevation_source, 'field ')
),

samples as (
    select * from z_samples
    union all by name
    select * from field_samples
),

converted as (
    select
        *,
        -- No step compares a sample with 3DEP yet (the header's third rule).
        false as checked_against_dem,
        case elevation_unit
            when 'metres' then elevation_value
            when 'feet' then elevation_value * 0.3048
        end as elevation_m_value,
        case elevation_unit
            when 'metres' then elevation_value / 0.3048
            when 'feet' then elevation_value
        end as elevation_ft_value
    from samples
)

select
    {{ dbt_utils.generate_surrogate_key([
        'elevation_feature_key', 'sample_seq'
    ]) }} as elevation_sample_key,
    source_key,
    club,
    elevation_feature_key,
    sample_seq,
    st_astext(geom_2d) as geom_wkt,
    elevation_source,
    elevation_unit,
    elevation_as_published,
    case
        when elevation_m_value is not null
            then printf('%.2f', elevation_m_value)
    end as elevation_m,
    case
        when elevation_ft_value is not null
            then printf('%.2f', elevation_ft_value)
    end as elevation_ft,
    band_low_ft,
    band_high_ft,
    checked_against_dem,
    checked_against_dem and elevation_m_value is not null
        as usable_for_calibration,
    _loaded_at
from converted
