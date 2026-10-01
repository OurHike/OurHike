{#-
    A geometry as a key input: md5 of its text at full precision.

    For the raw tables whose rows no attribute tells apart (pipeline/ELT.md,
    "One key per table"): DEC reuses an ASSET_UID for two campsites in
    different places, and the other rows of a few layers differ only by
    shape. Any vertex that moves changes the key, which is the meaning of
    "based on current values" (the maintainer, decision 40): the key names the
    row as it is now, and a moved feature is a new key.
-#}
{% macro geometry_key(column) -%}
    md5(st_astext({{ column }}))
{%- endmacro %}
