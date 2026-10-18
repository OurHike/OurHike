{#-
    Fails on a row whose geometry reaches outside the box its source
    publishes in: the lon/lat swap test, which a mart's +/-180 and +/-90
    range test cannot be. `geometry` is a SQL expression for the row's
    GEOMETRY. The boxes, and the measurements each rests on, are
    macros/lands_outside_its_region.sql's, which the POI region test calls
    too.
-#}
{% test lands_in_the_region_its_source_publishes_in(
    model, geometry, source_key_column='source_key'
) %}
{{ lands_outside_its_region(model, geometry, source_key_column) }}
{% endtest %}
