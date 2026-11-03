{#-
    lib/spurs.py's distance_m(): the equirectangular distance in metres
    between two lon/lat points, the formula every POI site and nearby
    distance is measured and published with (export_poi.py, lib/poi_sites.py),
    with one degree of latitude at var `poi_metres_per_degree` (111,320 m) and
    the cosine at the pair's mean latitude.

    Deliberately not EPSG:5070. pipeline/ELT.md's geometry rules measure a
    new threshold in EPSG:5070, never with ST_Distance_Sphere on (lon, lat)
    points; this is neither. It is the Python's own arithmetic, kept so the
    site grouping folds the same members as lib/poi_sites.py, whose 150 m,
    60 m and 80 m were measured with it, and so the `distance_ft` a card
    prints is the number it prints today. Python's math.hypot and this
    sqrt(dx*dx + dy*dy) can differ in the last bit (Reasoned), which moves a
    published distance only where it sits within about 1e-13 ft of a
    rounding edge.
-#}
{% macro poi_distance_m(lat1, lon1, lat2, lon2) -%}
    sqrt(
        power(({{ lon2 }} - {{ lon1 }}) * {{ var('poi_metres_per_degree') }} * cos(radians(({{ lat1 }} + {{ lat2 }}) / 2)), 2)
        + power(({{ lat2 }} - {{ lat1 }}) * {{ var('poi_metres_per_degree') }}, 2)
    )
{%- endmacro %}

{#-
    lib/poi_sites.py's normalise_name(): lowercase, every run of characters
    outside a-z and 0-9 a single space, trimmed. Null for a null name, where
    the Python gives "".
-#}
{% macro poi_normalise_name(name) -%}
    trim(regexp_replace(lower({{ name }}), '[^a-z0-9]+', ' ', 'g'))
{%- endmacro %}

{#-
    lib/poi_sites.py's base_name(): the normalised name with its trailing
    TYPE_WORDS and sibling numbers stripped, repeatedly, so "Bald Mtn Brook
    Lean-to Privy 2" reduces to "bald mtn brook lean to", the shelter's own
    name. The words are the module's TYPE_WORDS, and
    tests/test_dbt_points_of_interest_parity.py holds the two lists equal.
-#}
{% macro poi_base_name(name) -%}
    trim(regexp_replace(
        ' ' || {{ poi_normalise_name(name) }},
        '( (privy|campsite|shelter|shelters|group|[0-9]+))+$',
        ''
    ))
{%- endmacro %}
