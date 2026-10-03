{#-
    The rows of `relation` whose geometry reaches outside the box its source
    publishes in: the lon/lat swap test. A swapped point in the eastern
    United States (lon -74, lat 41 read as lon 41, lat -74) is still inside
    +/-180 and +/-90, so the range tests every geometry mart carries pass it
    (assert_pois_land_in_the_region_this_build_covers.sql's header has the
    green build that let one through). The generic test
    lands_in_the_region_its_source_publishes_in and that POI test both call
    this, so the boxes have one home.

    `geometry` is a SQL expression for the row's GEOMETRY. Its bounding box
    must sit inside the box `regions` gives its `source_key_column`, and a
    key it does not list gets `eastern`.

    THE BOXES, and what each rests on (extents measured 2026-10-03 from each
    live ArcGIS layer's returnExtentOnly, in lon/lat):
    - eastern, lat 30 to 50 and lon -90 to -66: the A.T. from Georgia to
      Maine and the New York, New Jersey, Pennsylvania, Connecticut,
      Massachusetts and North Carolina layers. Every ATC, OPRHP, NYNJTC,
      Mohonk, DEC, NJDEP, PASDA, CT DEEP, NC MST and MassGIS layer measured
      inside it, the widest lat 34.53 to 45.93 and lon -84.48 to -68.71.
    - national, lat 18 to 72 and lon -180 to -64: the fifty states, with no
      room for a swapped U.S. point (its latitude would be -64 or less).
      The western and nationwide trail layers listed measured inside it.
    - us_and_territories, lat -20 to 72 at any longitude: for a layer that
      reaches American Samoa or Guam. NPS's trails measured lat -14.37 to
      65.85 and lon -170.77 to 145.73. A swap is still caught: a point that
      survives the +/-180 test transposed had a longitude of -90 to -64, so
      its latitude now reads -64 or less. NWS's alerts get it because they
      follow the weather squares onto every published trail, Puerto Rico's
      (USFS, lat 18.27) among them, and an alert there reaches the south
      coast below lat 18.

    @unvalidated Every margin is picked, not measured. What would settle it
    is the per-club box from trail_orgs.json's `states` that pipeline/ELT.md
    plans. A source loading outside the eastern box without a row in
    `regions` fails here: that is the design, since widening a safety bound
    is part of registering a source.
-#}
{% macro lands_outside_its_region(
    relation, geometry, source_key_column='source_key'
) %}

{%- set boxes = {
    'eastern': (30.0, 50.0, -90.0, -66.0),
    'national': (18.0, 72.0, -180.0, -64.0),
    'us_and_territories': (-20.0, 72.0, -180.0, 180.0),
} -%}
{%- set regions = {
    'usfs_trails': 'national',
    'usfs_rec_sites': 'national',
    'blm_trails': 'national',
    'cotrex_trails': 'national',
    'wa_rco_trails': 'national',
    'utah_sgid_trails': 'national',
    'ncta_trail': 'national',
    'alaska_trails': 'national',
    'azgeo_arizona_trail': 'national',
    'tahoe_rim_trail': 'national',
    'duluth_superior_hiking_trail': 'national',
    'pcta_centerline': 'national',
    'cdtc_centerline': 'national',
    'wi_ice_age_trail': 'national',
    'nps_trails': 'us_and_territories',
    'nws_alerts': 'us_and_territories',
} -%}

with placed as (
    select
        {{ source_key_column }} as source_key,
        {{ geometry }} as geom
    from {{ relation }}
),

boxed as (
    select
        source_key,
        st_xmin(geom) as xmin,
        st_xmax(geom) as xmax,
        st_ymin(geom) as ymin,
        st_ymax(geom) as ymax,
        case
            {% for key, region in regions.items() -%}
            when source_key = '{{ key }}' then '{{ region }}'
            {% endfor -%}
            else 'eastern'
        end as region
    from placed
    where geom is not null
)

select *
from boxed
where
    case region
        {% for region, box in boxes.items() -%}
        when '{{ region }}'
            then
                ymin < {{ box[0] }} or ymax > {{ box[1] }}
                or xmin < {{ box[2] }} or xmax > {{ box[3] }}
        {% endfor -%}
    end

{% endmacro %}
