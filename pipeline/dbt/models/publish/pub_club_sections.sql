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
-- `source_edited` IS EMPTY, where export_club_sections.py fills each
-- layer's last edit day from fetch_all.py's manifest.json
-- (`data_last_edit_date`, ArcGIS's editingInfo.dataLastEditDate). The
-- extract lands no such date, so no day is known here, and a key with no
-- usable day is absent, never null: the Python's own rule for a layer whose
-- date is unknown. The sheet then omits the edit day, as it does for a
-- release that carries none. It fills when the extract lands each layer's
-- editingInfo.dataLastEditDate. The extract's change marker is no stand-in:
-- its Last-Modified equals editingInfo.lastEditDate, which moves on a schema
-- edit too, and trail_club_sections' is 2025-10-09 where its data was last
-- edited 2024-08-15 (the live metadata, read 2026-10-02), so the sheet would
-- call two-year-old names fourteen months fresher than they are.
with sections as (
    select * from {{ ref('int_trail_lines__club_sections') }}
)

select
    {
        'attribution': 'centerline',
        'names': 'trail_club_sections',
        'miles': 'half_mile_points_from_springer'
    } as sources,
    json('{}') as source_edited,
    coalesce(
        (
            select
                list(
                    json_object(
                        'acronym', acronym,
                        'name', club_name,
                        'region', region,
                        'stretches', json(stretches_json),
                        'miles', miles
                    )
                    order by club_order
                )
            from sections
            where acronym is not null
        ),
        cast([] as json[])
    ) as clubs,
    (
        select json(stretches_json)
        from sections
        where acronym is null
    ) as unattributed
