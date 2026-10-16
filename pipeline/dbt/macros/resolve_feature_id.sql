{#-
    lib/feature_id.py's resolve_feature_id(), as every published line id is
    built: `<source key>:` and the first non-null of
      1. the property named exactly `GlobalID`;
      2. the feature's GeoJSON `id`, which ArcGIS sets to the layer's object
         id and lib/socrata.py to the Socrata row id;
      3. `generated-<the feature's place in its layer>`.
    Each step tests its VALUE for null, as the Python tests `is None`, so an
    explicit null GlobalID falls through and an empty string does not.

    THIS IS THE ID A PHONE JOINS ON, and it is today's exporters' id, not a
    better one. A phone finds a line's climb by joining a graph cell's edges
    to a tile's lines, `edge.trail_id === line.id`
    (client/src/lib/lineClimb.ts), and draws a tile cell it holds before
    asking the bucket (client/src/map/networkTiles.ts), so its tiles can be
    from an older release than its graph, and a line must keep its id across
    the cutover. Whether it should ever move to its stable GlobalID is the
    maintainer's question, with a plan for phones holding both
    (pipeline/ELT.md's TL05).

    THE CASE IS DECLARED, NOT READ. dlt's sql_ci_v1 naming lands `GlobalID`,
    `GLOBALID` and `globalid` as one lower-case column, so a layer's spelling
    is its sources.json row's `global_id_field`, and step 1 reads the column
    only where that is exactly `GlobalID`. On usfs_trails (`globalid`) and
    on DEC's, NJ's, NJDEP's, MassGIS's and PASDA's lines (`GLOBALID`), and on
    NYC's CSCL paths and park drives (`globalid`), the GlobalID is never the
    id, here or in today's exporter. Measured 2026-10-15 on UA's release
    2026-10-10-2, which read it in any case: none of the 51,663 USFS, 5,228
    DEC, 11,701 NJ statewide and 3,138 NJDEP ids in the graph cells phones
    read was in its trail_graph.json.

    Arguments, each a SQL expression:
    - source_key: the registry key;
    - global_id_field: the layer's spelling of its GlobalID field, from the
      registry, null where it has none;
    - global_id: the landed GlobalID column's value, as text;
    - feature_id: the GeoJSON id's value, as text: the column the
      registry's `object_id_field` names on an ArcGIS layer, `_socrata_id`
      on a Socrata one;
    - position: the feature's place in its layer, or null where its staging
      model keeps none;
    - last_resort: a step the Python does not have, for a row with none of
      the three, such as the staging key, which stays unique and
      stable where a place in a file the warehouse never saw cannot be.
-#}
{% macro resolve_feature_id(
    source_key, global_id_field, global_id, feature_id, position, last_resort=none
) -%}
    {{ source_key }} || ':' || coalesce(
        case when {{ global_id_field }} = 'GlobalID' then {{ global_id }} end,
        {{ feature_id }},
        'generated-' || {{ position }}
        {%- if last_resort is not none %},
        {{ last_resort }}
        {%- endif %}
    )
{%- endmacro %}
