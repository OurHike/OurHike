{#-
    `value`, one half of the coordinate pair (`lat`, `lon`), while that pair
    is a point on Earth, and null when it is not: #1763 — Every request
    schema but DefaultPlace accepts any finite latitude and longitude, so a
    report at (1000, −5000) is stored, moderated and baked into the artifact
    hikers download. export_conditions.py's _null_off_globe() is the same
    rule in Python, and tests/test_dbt_conditions_parity.py runs it over the
    unit-test rows of every model that calls this, so the two writers of
    conditions/reports.json and conditions/closures.json cannot drift apart.

    - Both halves present, the latitude -90 to 90 and the longitude -180 to
      180, ends included (DefaultPlace's bounds, backend/app/schemas/
      preferences.py): kept.
    - Either half NaN or infinite: kept as it is. That is not this rule's to
      hide. int_closures__ourhike_checked's `problems` and int_closures__gate's
      `rows_not_finite` read the raw value and hold the source's whole file,
      as write_document()'s allow_nan=False does in Python (#658), and a hold
      gets the row looked at where a quiet null would not.
    - Anything else, a finite half out of range or one half missing: both
      halves null, so the row publishes with no location. One good half of a
      bad pair places nothing. What MapLibre draws at an off-globe point is
      @unvalidated (#1763 reasons a wrapped longitude and a clamped latitude,
      a confident dot in the wrong place; nobody has tried it on a device);
      null is a shape the wire already carries (ReportOut's `lat: float |
      None`; a closure endpoint filed before #674 has none).

    Only the location goes; the row, its mile and its text stay.
-#}
{% macro null_off_globe(value, lat, lon) -%}
    case
        when
            not (
                coalesce(isfinite({{ lat }}), true)
                and coalesce(isfinite({{ lon }}), true)
            )
            then {{ value }}
        when
            {{ lat }} between -90 and 90
            and {{ lon }} between -180 and 180
            then {{ value }}
    end
{%- endmacro %}
