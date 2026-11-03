{{ config(format='json', location='club_sections.json') }}
-- club_sections.json, which club maintains which stretch of the A.T., in
-- the shape export_club_sections.build_output() writes: `sources` (which
-- layer gives the attribution, the names and the miles), `source_edited`,
-- `clubs` south to north and `unattributed`. Read by
-- client/src/lib/clubSections.ts.
--
-- IT READS AN INTERMEDIATE, NOT THE MART: a stretch is a mile range, not a
-- published line, so int_trail_lines__club_sections holds them.
--
-- `source_edited` DATES EACH LAYER `sources` NAMES, keyed by the layer's
-- sources.json key and in `sources`' order, as export_club_sections.py's
-- source_edit_dates() keys it: the UTC day YYYY-MM-DD that
-- int_sources__data_edited gives the key, from the layer's own
-- editingInfo.dataLastEditDate, which the extract logs on its run log row
-- (extract/_run.py's RUNS_COLUMNS comment) where the Python reads
-- fetch_all.py's manifest.json. A key with no usable day is absent, never
-- null, the Python's own rule for a layer whose date is unknown, and the
-- sheet then omits that edit day, as it does for a release that carries
-- none. Never editingInfo.lastEditDate, which the extract's change marker
-- on ArcGIS Online follows (its Last-Modified equals it) and which moves on
-- a schema edit too: trail_club_sections' read 2025-10-09 where its data
-- was last edited 2024-08-15 (the live metadata, read 2026-10-02), so the
-- sheet would call two-year-old names fourteen months fresher than they
-- are. The day is the layer's, whether
-- or not the layer may publish (int_sources__publication), as the
-- Python's is: it says when the layer was edited, not what it holds.
with sections as (
    select * from {{ ref('int_trail_lines__club_sections') }}
),

data_edited as (
    select * from {{ ref('int_sources__data_edited') }}
),

-- The layer of each role, by its sources.json key: `sources`, and the keys
-- `source_edited` dates.
layers as (
    select
        'centerline' as attribution_key,
        'trail_club_sections' as names_key,
        'half_mile_points_from_springer' as miles_key
),

-- One key per layer: a layer two roles named would be dated once.
edited as (
    select
        coalesce(
            to_json(
                map_from_entries(
                    list(
                        {
                            'k': data_edited.source_key,
                            'v': data_edited.data_edited_on
                        }
                        order by list_position(
                            [
                                layers.attribution_key,
                                layers.names_key,
                                layers.miles_key
                            ],
                            data_edited.source_key
                        )
                    )
                )
            ),
            json('{}')
        ) as source_edited
    from layers
    inner join data_edited
        on
            data_edited.source_key
            in (layers.attribution_key, layers.names_key, layers.miles_key)
)

select
    {
        'attribution': layers.attribution_key,
        'names': layers.names_key,
        'miles': layers.miles_key
    } as sources,
    edited.source_edited,
    coalesce(
        (
            select
                list(
                    json_object(
                        'acronym', sections.acronym,
                        'name', sections.club_name,
                        'region', sections.region,
                        'stretches', json(sections.stretches_json),
                        'miles', sections.miles
                    )
                    order by sections.club_order
                )
            from sections
            where sections.acronym is not null
        ),
        cast([] as json[])
    ) as clubs,
    (
        select json(sections.stretches_json)
        from sections
        where sections.acronym is null
    ) as unattributed
from layers
cross join edited
