{#-
    The pieces lib/poi_description.py composes an A.T. POI's one sentence
    from (PO19), and lib/atc_notes.py's clean_note() (PO20), for
    int_points_of_interest__described. Each macro names the Python function
    it is, and reads the staged row's JSON (`properties`), where dlt's
    sql_ci_v1 naming has lower-cased ATC's field names: `Exterior_M` is
    `exterior_m`, `ADA_Space` is `ada_space`.
-#}

{#- _count(): an inventory count as a number, null and junk alike read as
    zero ("a missing one means nobody recorded any"), a boolean as 1 or 0 as
    float() reads it, a string as float() reads it after stripping. -#}
{% macro poi_count(properties, member) -%}
    coalesce(
        case json_type({{ properties }}, '$.{{ member }}')
            when 'BOOLEAN' then cast(cast(json_extract_string({{ properties }}, '$.{{ member }}') as boolean) as double)
            else try_cast({{ python_strip("json_extract_string(" ~ properties ~ ", '$." ~ member ~ "')") }} as double)
        end,
        0
    )
{%- endmacro %}

{#- int(_count()): Python's int() truncates toward zero. -#}
{% macro poi_whole_count(properties, member) -%}
    cast(trunc({{ poi_count(properties, member) }}) as bigint)
{%- endmacro %}

{#- _coded(): one of ATC's coded-domain values as a bare string, '' where
    the field is absent or null (no lookup matches either). -#}
{% macro poi_coded(properties, member) -%}
    coalesce({{ python_strip("json_extract_string(" ~ properties ~ ", '$." ~ member ~ "')") }}, '')
{%- endmacro %}

{#- _join(): "a", "a and b", "a, b and c", from a list with the absent
    phrases already filtered out; '' for an empty list. -#}
{% macro poi_join_phrases(phrases) -%}
    case len({{ phrases }})
        when 0 then ''
        when 1 then list_extract({{ phrases }}, 1)
        else
            array_to_string(list_slice({{ phrases }}, 1, len({{ phrases }}) - 1), ', ')
            || ' and '
            || list_extract({{ phrases }}, -1)
    end
{%- endmacro %}

{#- _plural(): "1 car", "7 cars". -#}
{% macro poi_plural(count, singular) -%}
    cast({{ count }} as varchar) || ' ' || {{ singular }} || case when {{ count }} = 1 then '' else 's' end
{%- endmacro %}

{#- _built_clause(): " Built 1915." for a year inside
    EARLIEST_PLAUSIBLE_YEAR..LATEST_PLAUSIBLE_YEAR, else nothing. -#}
{% macro poi_built_clause(properties) -%}
    case
        when {{ poi_whole_count(properties, 'year_built') }}
            between {{ var('poi_description_earliest_year') }} and {{ var('poi_description_latest_year') }}
            then ' Built ' || cast({{ poi_whole_count(properties, 'year_built') }} as varchar) || '.'
        else ''
    end
{%- endmacro %}

{#- _note_clause(): ATC's own words, attributed, with a full stop where
    the note ends without one. -#}
{% macro poi_note_clause(note) -%}
    case
        when coalesce({{ note }}, '') = '' then ''
        when regexp_matches({{ python_strip(note) }}, '[.!?]$') then ' ATC notes: ' || {{ python_strip(note) }}
        else ' ATC notes: ' || {{ python_strip(note) }} || '.'
    end
{%- endmacro %}

{#- One sentence of ATC's Comments is the survey talking to itself
    (lib/atc_notes.py's _is_internal()): blank once its stops are gone, one
    of EMPTY_VALUES, a bare number or date fragment, or a match for one of
    INTERNAL_PATTERNS, case-insensitively. -#}
{% macro poi_note_sentence_is_internal(sentence) -%}
    (
        lower({{ python_strip("rtrim(" ~ python_strip(sentence) ~ ", '.;')") }}) = ''
        or lower({{ python_strip("rtrim(" ~ python_strip(sentence) ~ ", '.;')") }})
        in ('{{ var("poi_note_empty_values") | join("', '") }}')
        or regexp_full_match(lower({{ python_strip("rtrim(" ~ python_strip(sentence) ~ ", '.;')") }}), '[\d\s/\-]+')
        or regexp_matches({{ sentence }}, '(?i){{ var("poi_note_internal_patterns") | join("|") }}')
    )
{%- endmacro %}

{#- clean_note(), up to its last test: the Comments with every internal
    sentence dropped whole (SENTENCE's pieces, the kept ones spliced back as
    ATC wrote them), the whitespace a dropped sentence left collapsed, and
    the punctuation it left stranded removed. Null where the Comments are
    blank. clean_note() then answers None where no letter or digit is left,
    which the model applies: `[\pL\pN]` is str.isalnum()'s classes. -#}
{% macro poi_note_kept_text(raw) -%}
    case
        when {{ python_strip("coalesce(" ~ raw ~ ", '')") }} != ''
            then trim(
                regexp_replace(
                    regexp_replace(
                        {{ python_strip(
                            "array_to_string(list_filter(regexp_extract_all(" ~ raw ~ ", '[^.;]+[.;]?'), "
                            ~ "lambda sentence: not " ~ poi_note_sentence_is_internal('sentence') ~ "), '')"
                        ) }},
                        '[\s\x{0b}\x{1c}-\x{1f}\x{85}\p{Z}]+', ' ', 'g'
                    ),
                    ' +([.;,])', '\1', 'g'
                ),
                ' ;,'
            )
    end
{%- endmacro %}
