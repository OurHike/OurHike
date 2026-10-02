{#-
    A string with Python's html.unescape() applied: lib/nynjtc_alerts.py reads
    every WordPress title and place-term name through it, and the closures and
    warnings family reads them in SQL (#1793, stage 3).

    THE SAME MATCH AND THE SAME NUMERIC ANSWERS. References are found with
    Python's own `_charref` pattern, left to right, and every numeric one,
    decimal or hex, gets Python's answer: the 34 code points the HTML5 spec
    replaces (U+0000 and U+0080-U+009F read as Windows-1252, U+000D kept),
    U+FFFD for a surrogate or anything past U+10FFFF, nothing at all for a
    noncharacter or a control, and the character itself otherwise.

    A NAMED REFERENCE IS DECODED ONLY FOR THE NAMES BELOW, each spelled the
    ways html.entities.html5 holds it (with its semicolon, and without where
    the spec keeps a legacy form), and a name without its semicolon is matched
    by its longest listed prefix, as Python does. Python decodes all 2,231
    names in html.entities.html5; a name not listed here is left as written,
    so `&frac34;` would reach a phone as those eight characters, where Python
    writes the one character it names. Measured
    2026-10-02 on NYNJTC's live feed: its 18 alert titles carry `&#8211;`
    twice and `&amp;` once, and its 186 place terms carry `&amp;` once, so
    the names below cover what the source sends today.
    tests/test_dbt_conditions_parity.py holds each listed name to Python's
    table and runs html.unescape over the unit test's titles.

    Every list index is 1-based, as DuckDB's are: parts[i + 1] is the text
    after the i-th reference.
-#}
{% macro python_html_unescape(text) -%}
    {%- set pattern = "'&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\\t\\n\\f <&#;]{1,32};?)'" -%}
    case
        when strpos({{ text }}, '&') = 0 then {{ text }}
        else
            regexp_split_to_array({{ text }}, {{ pattern }})[1]
            || array_to_string(list_transform(
                range(1, len(regexp_extract_all({{ text }}, {{ pattern }})) + 1),
                lambda i: {{ _html_reference(
                    "substr(regexp_extract_all(" ~ text ~ ", " ~ pattern ~ ")[i], 2)"
                ) }}
                || regexp_split_to_array({{ text }}, {{ pattern }})[i + 1]
            ), '')
    end
{%- endmacro %}

{#- One reference's replacement, from its body (the text after `&`). -#}
{% macro _html_reference(body) -%}
    case
        when regexp_full_match({{ body }}, '#[xX][0-9a-fA-F]+;?')
            then {{ _html_code_point(
                "regexp_extract(" ~ body ~ ", '^#[xX]0*([0-9a-fA-F]*)', 1)", 16
            ) }}
        when regexp_full_match({{ body }}, '#[0-9]+;?')
            then {{ _html_code_point(
                "regexp_extract(" ~ body ~ ", '^#0*([0-9]*)', 1)", 10
            ) }}
        when {{ _html_names() }}[{{ body }}] is not null
            then chr({{ _html_names() }}[{{ body }}])
        when list_filter(
            range(length({{ body }}) - 1, 1, -1),
            lambda x: {{ _html_names() }}[left({{ body }}, x)] is not null
        )[1] is not null
            then chr({{ _html_names() }}[left({{ body }}, list_filter(
                range(length({{ body }}) - 1, 1, -1),
                lambda x: {{ _html_names() }}[left({{ body }}, x)] is not null
            )[1])])
            || substr({{ body }}, list_filter(
                range(length({{ body }}) - 1, 1, -1),
                lambda x: {{ _html_names() }}[left({{ body }}, x)] is not null
            )[1] + 1)
        else '&' || {{ body }}
    end
{%- endmacro %}

{#- A numeric reference's character, from its digits with leading zeros gone:
    more than 7 decimal or 6 hex digits is past U+10FFFF whatever they say. -#}
{% macro _html_code_point(digits, base) -%}
    {%- set too_long = 7 if base == 10 else 6 -%}
    {%- set number = "try_cast(" ~ ("'0x' || " if base == 16 else "") ~ "coalesce(nullif(" ~ digits ~ ", ''), '0') as integer)" -%}
    case
        when length({{ digits }}) > {{ too_long }} then chr(65533)
        when {{ _html_replaced() }}[{{ number }}] is not null
            then chr({{ _html_replaced() }}[{{ number }}])
        when {{ number }} between 55296 and 57343 or {{ number }} > 1114111
            then chr(65533)
        when
            {{ number }} between 1 and 8
            or {{ number }} = 11
            or {{ number }} between 14 and 31
            or {{ number }} between 127 and 159
            or {{ number }} between 64976 and 65007
            or {{ number }} % 65536 in (65534, 65535)
            then ''
        else chr({{ number }})
    end
{%- endmacro %}

{#- html._invalid_charrefs: the code points the HTML5 spec reads otherwise. -#}
{% macro _html_replaced() -%}
    map(
        [0, 13, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139,
            140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152,
            153, 154, 155, 156, 157, 158, 159],
        [65533, 13, 8364, 129, 8218, 402, 8222, 8230, 8224, 8225, 710, 8240,
            352, 8249, 338, 141, 381, 143, 144, 8216, 8217, 8220, 8221, 8226,
            8211, 8212, 732, 8482, 353, 8250, 339, 157, 382, 376]
    )
{%- endmacro %}

{#- The named references decoded, as html.entities.html5 spells them. -#}
{% macro _html_names() -%}
    map(
        ['amp;', 'amp', 'AMP;', 'AMP', 'lt;', 'lt', 'LT;', 'LT', 'gt;', 'gt',
            'GT;', 'GT', 'quot;', 'quot', 'QUOT;', 'QUOT', 'apos;', 'nbsp;',
            'nbsp', 'ndash;', 'mdash;', 'lsquo;', 'rsquo;', 'sbquo;',
            'ldquo;', 'rdquo;', 'bdquo;', 'hellip;', 'bull;', 'middot;',
            'middot', 'copy;', 'copy', 'COPY;', 'COPY', 'reg;', 'reg', 'REG;',
            'REG', 'trade;', 'deg;', 'deg'],
        [38, 38, 38, 38, 60, 60, 60, 60, 62, 62, 62, 62, 34, 34, 34, 34, 39,
            160, 160, 8211, 8212, 8216, 8217, 8218, 8220, 8221, 8222, 8230,
            8226, 183, 183, 169, 169, 169, 169, 174, 174, 174, 174, 8482, 176,
            176]
    )
{%- endmacro %}
