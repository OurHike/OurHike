{#-
    A string with Python's str.strip() applied: the whitespace a Python gate
    ignores, ignored the same way when its rule moves to SQL.

    DuckDB's trim() strips spaces only. This class is every character
    Python's str.isspace() is true for: RE2's \s (tab, newline, form feed,
    carriage return, space), plus vertical tab, the four separators 0x1c-0x1f,
    NEL (0x85), and \p{Z}. Measured 2026-10-01 on DuckDB 1.5.5 against
    Python 3.13: all 29 of Python's whitespace characters are stripped, and
    none of the 63,458 other characters of the Basic Multilingual Plane
    (surrogates and NUL left out) is.
-#}
{% macro python_strip(text) -%}
    regexp_replace(
        {{ text }},
        '^[\s\x{0b}\x{1c}-\x{1f}\x{85}\p{Z}]+|[\s\x{0b}\x{1c}-\x{1f}\x{85}\p{Z}]+$',
        '',
        'g'
    )
{%- endmacro %}
