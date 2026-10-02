{#-
    Python's repr() of a str, or `None` for a null, as a Python message
    prints a value with `!r`: single quotes, or double quotes when the text
    holds a single quote and no double one, with the backslash, tab, newline,
    carriage return and the chosen quote escaped (#1793, stage 3, for
    lib/atc_updates.py's auto_publish_refusal() messages).

    NOT NAMED python_repr, which macros/challenges/python_repr.sql defines
    for a JSON value. With both named python_repr, dbt 2.0.6 parsed without
    a word and the challenges models called this one, so
    int_challenges__publishers printed `'"nobody"'` for `'nobody'`
    (measured 2026-10-02, merging the PR branch at 904f2de1).

    Every backslash is chr(92) and every single quote chr(39), never a
    literal: dbt 2.0.6's `dbt lint` reads a backslash before a quote in a
    string literal as an escape, so `'\'` never closes there (measured
    2026-10-02, SyntaxInvalid dbt0101), while DuckDB reads the same text as
    one backslash.

    Other control characters and the characters str.isprintable() refuses are
    left as they are, where repr() escapes them. Reasoned that no ATC text
    reaches here with one: lib/atc_scrape.py's strip_html() turns every run of
    whitespace into one space before the chip or the mile pattern reads the
    page, and neither pattern matches anything but letters, digits, spaces,
    commas, periods and dashes. No quote or backslash was in any of the 35
    mile references the 86 live pages carried on 2026-10-02.
-#}
{% macro python_text_repr(text) -%}
    case
        when {{ text }} is null then 'None'
        when contains({{ text }}, chr(39)) and not contains({{ text }}, '"')
            then '"' || {{ _python_text_repr_escapes(text) }} || '"'
        else
            chr(39)
            || replace({{ _python_text_repr_escapes(text) }}, chr(39), chr(92) || chr(39))
            || chr(39)
    end
{%- endmacro %}

{#- The escapes both quotings share, the backslash first, so the ones after
    it are not doubled. -#}
{% macro _python_text_repr_escapes(text) -%}
    replace(replace(replace(replace(
        {{ text }},
        chr(92), chr(92) || chr(92)),
        chr(9), chr(92) || 't'),
        chr(10), chr(92) || 'n'),
        chr(13), chr(92) || 'r')
{%- endmacro %}
