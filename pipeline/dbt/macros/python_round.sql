{#-
    A double rounded to `digits` places the way Python's round(x, digits)
    rounds it: the decimal nearest the double's exact binary value, half to
    even, read back as a double.

    DuckDB's own round() is not that. Measured 2026-10-02 on 517,613 doubles
    (200,000 uniform in 0-2200 miles, 300,000 at and one or two ulps either
    side of a half-thousandth, 17,600 exact sixteenths): round(x, 3) disagreed
    with Python on 59,050 of them, among them 1.0005 (Python 1.0, DuckDB
    1.001) and 0.0625 (Python 0.062, DuckDB 0.063). printf's fixed format cast
    back to a double agreed on all 517,613, at 3 places and at 1, on Python's
    DuckDB 1.5.5 and on dbt 2.0.6's bundled 1.5.4 alike. A published `mile` is
    a hiker's position, so a third-decimal disagreement is a different answer,
    not a rounding note.
-#}
{% macro python_round(value, digits) -%}
    cast(printf('%.{{ digits }}f', {{ value }}) as double)
{%- endmacro %}
