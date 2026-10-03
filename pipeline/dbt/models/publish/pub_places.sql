{{ config(format='json_document', location='places.json') }}
-- places.json, the places a hiker can name before anything is downloaded, in
-- the shape export_places.py's build_output() writes (decision 44's v1):
-- `generated_at`, `trailRadiusMiles`, `trailMilesMeasured`, then `places`,
-- one record per row of the places mart in its `place_order`.
--
-- A RECORD CARRIES ONLY THE FIELDS WITH A VALUE, in _record()'s fixed order:
-- id, poiId, name, kind, category, state, within, lon, lat, bbox, trailMiles,
-- source. An absent field is the file's way of saying "unknown", which is why
-- this is `json_document`: COPY's JSON format would write each null.
--
-- `trailMilesMeasured` is whether any line was measured
-- (int_places__lines), not whether a row carries miles, so a build with
-- lines and no place still says true. `trailRadiusMiles` is the radius the
-- waypoints' figures were measured within (places_trail_radius_miles,
-- @unvalidated), printed beside them so a screen says what was measured.
-- `generated_at` is dbt's run_started_at, to the second, as lib/stamps.py's
-- utc_stamp() writes it.
-- python_run_stamp() is the conditions files' run_started_at, which
-- python_utc_seconds() cuts to the second.
{%- set run_stamp = "cast(" ~ python_run_stamp() ~ " as timestamptz)" %}
{%- set stamp = python_utc_seconds(run_stamp) %}
with places as (
    select * from {{ ref('places') }}
),

records as (
    select
        place_order,
        '{'
        || array_to_string(
            list_filter(
                [
                    '"id":' || cast(to_json(place_id) as varchar),
                    '"poiId":' || cast(to_json(poi_id) as varchar),
                    '"name":' || cast(to_json(name) as varchar),
                    '"kind":' || cast(to_json(kind) as varchar),
                    '"category":' || cast(to_json(category) as varchar),
                    '"state":' || cast(to_json(state) as varchar),
                    '"within":' || cast(to_json(within_park) as varchar),
                    '"lon":' || cast(to_json(lon) as varchar),
                    '"lat":' || cast(to_json(lat) as varchar),
                    '"bbox":' || cast(to_json(bbox) as varchar),
                    '"trailMiles":' || cast(to_json(trail_miles) as varchar),
                    '"source":' || cast(to_json(source) as varchar)
                ],
                lambda member: member is not null
            ),
            ','
        )
        || '}' as place_record
    from places
)

select
    cast(
        json_object(
            'generated_at', {{ stamp }},
            'trailRadiusMiles',
            cast({{ var('places_trail_radius_miles') }} as double),
            'trailMilesMeasured',
            (select count(*) > 0 from {{ ref('int_places__lines') }}),
            'places',
            coalesce(list(cast(place_record as json) order by place_order), [])
        ) as varchar
    ) as places_document
from records
