{{ config(format='json_document', location='spurs.json') }}
-- spurs.json, what each spur leads to (#134 — The line-detail sheet that
-- shows a spur's destination) and where it joins the A.T. (#136 — Publish
-- the mile at which each spur joins the AT), from the trail_lines
-- mart's spurs, in the shape export_spurs.py writes: one object keyed by the
-- side trail's id in trails.geojson, each value `destination_distance_m`,
-- `destination_poi_id`, `junction_mile`, `length_ft` and `name`, and both
-- levels' keys sorted, as json.dumps(sort_keys=True) sorts them (ids in
-- code-point order, which DuckDB's byte order of UTF-8 text is). The client
-- reads `spurs[line.id]` for a line it drew (client/src/lib/lineDetail.ts).
--
-- Written verbatim by phone_file's json_document format, because a file
-- whose top-level keys are data has no column list (that format's header).
-- DuckDB writes a non-ASCII character as itself, in UTF-8, where
-- json.dumps escapes it as \uXXXX: the same JSON once parsed, which is what
-- the phone and parity.py compare, and different bytes.
--
-- Only the spurs trails.geojson draws: int_trail_lines__at_side_trails says
-- what export_spurs.py also writes, which no phone can reach.
with spurs as (
    select * from {{ ref('trail_lines', v=1) }}
    where line_kind = 'spur'
)

select
    coalesce(
        to_json(
            map_from_entries(
                list(
                    {
                        'k': trail_line_id,
                        'v': json_object(
                            'destination_distance_m',
                            spur_destination_distance_m,
                            'destination_poi_id', spur_destination_poi_id,
                            'junction_mile', spur_junction_mile,
                            'length_ft', spur_length_ft,
                            'name', name
                        )
                    }
                    order by trail_line_id
                )
            )
        ),
        json('{}')
    -- phone_file's json_document format reads the column by this name.
    ) as document  -- noqa: RF04
from spurs
