{#-
    The club notice sources' shared pieces (phase C): what every
    generated base and staging model calls (pipeline/generate_notice_models.py
    writes them), and int_closures__club_notices reads.
-#}

{#- A notice source's raw table, or no rows where it does not exist in this
    warehouse: raw_or_empty() (macros/raw_or_empty.sql), which every
    generated base model reads its raw table through.

    A conditions leg withdraws a table whose reader could not be read
    (extract/_warehouse.py's committed_tables(), an `unavailable` outcome),
    takes on a bounded number of tables it has never loaded per run
    (extract/_run.py's NEW_TABLES_PER_LEG_RUN), and leaves out a table whose
    read failed before its hints. The gate then holds that source back for
    having no rows that a count of zero proves (int_closures__gate), so
    absent still means unknown, never "nothing closed". -#}
{% macro notice_raw_table(relation, columns) -%}
    {{ raw_or_empty(relation, columns) }}
{%- endmacro %}

{#- A source field's text, by its raw column's name, out of a staging model's
    `fields.row_json` (the base row as JSON): null where the column is absent,
    null or blank, so a field the source drops or renames reads as unknown
    rather than failing the build. `path` reads a value inside a JSON column
    (a WordPress title's `$.rendered`); `as_list` joins a JSON list of text
    with ', ' (a feed item's categories). -#}
{% macro notice_field(column, path=none, as_list=false) -%}
    {%- set value = "json_extract_string(fields.row_json, '$.\"" ~ column ~ "\"')" -%}
    {%- if path is not none -%}
        {%- set value = "json_extract_string(" ~ value ~ ", '" ~ path ~ "')" -%}
    {%- endif -%}
    {%- if as_list -%}
        {%- set value = "array_to_string(try_cast(json(" ~ value ~ ") as varchar[]), ', ')" -%}
    {%- endif -%}
    nullif(trim({{ value }}), '')
{%- endmacro %}

{#- A source's date or time, as the source states it, as TIMESTAMPTZ, or
    null where it is none of these. Read in this order, the first that
    parses:
    - epoch milliseconds, eleven digits or more: ArcGIS's
      esriFieldTypeDate, which extract/_kinds.py's ESRI_TYPES lands as bigint;
    - anything DuckDB casts to a timestamp with time zone: ISO 8601 with or
      without an offset (Atom, WordPress's modified_gmt, ArcGIS's DateOnly
      'YYYY-MM-DD', NPS's '2026-10-02 00:00:00.0'). Without an offset the
      session's zone applies, which build_marts.py sets to UTC;
    - RFC 822, an RSS pubDate, with its zone named or numbered: a name
      RFC 822 section 5.1 gives (UT, GMT, Z and the eight North American
      ones) is read as the offset it stands for (notice_rfc822_offset()
      below), so Maricopa County Parks' 'Tue, 2 Sep 2025 13:30:00 MST' is
      20:30 UTC. Until the review of PR #1805 of 2026-10-15 (thread
      4279226770) only ' GMT' was, and all 104 of Maricopa's items read
      2026-10-15 had no date;
    - a day, alone or followed by words, which notice_stated_day() below
      reads: month/day/year, ISO, or a month's name on either side of the
      day.
    Never filled in: a date the source states in words ('Until further
    notice') is null here, and stays in the source's own fields.
    tests/singular/assert_notice_instant_reads_each_shape_a_source_states_a_date_in.sql
    holds each of these shapes. -#}
{% macro notice_instant(text) -%}
    coalesce(
        case
            when regexp_full_match({{ text }}, '-?[0-9]{11,}')
                then to_timestamp(cast({{ text }} as bigint) / 1000.0)
        end,
        try_cast({{ text }} as timestamptz),
        try_strptime(
            {{ notice_rfc822_offset(text) }}, '%a, %d %b %Y %H:%M:%S %z'
        ),
        cast({{ notice_stated_day(text) }} as timestamptz)
    )
{%- endmacro %}

{#- A text value with an RFC 822 zone name at its end replaced by the offset
    the name stands for (RFC 822, section 5.1), or the value as it was: the
    numbered form strptime's %z reads. The military letters but Z are left
    out, because RFC 1123 (section 5.2.14) says RFC 822 gave their signs the
    wrong way round, and a zone RFC 822 does not name ('HST') is no instant
    here, never a guess. Words that end in a zone name ('Closed until 5:00 PM
    MST') still read as no instant: with the offset they are no RFC 822
    date, and they state no day first. -#}
{% macro notice_rfc822_offset(text) -%}
    {%- set zones = {
        'UT': '+0000', 'GMT': '+0000', 'Z': '+0000',
        'EST': '-0500', 'EDT': '-0400', 'CST': '-0600', 'CDT': '-0500',
        'MST': '-0700', 'MDT': '-0600', 'PST': '-0800', 'PDT': '-0700'
    } -%}
    case regexp_extract({{ text }}, ' ([A-Z]{1,3})$', 1)
        {%- for name, offset in zones.items() %}
        when '{{ name }}'
            then regexp_replace({{ text }}, ' [A-Z]{1,3}$', ' {{ offset }}')
        {%- endfor %}
        else {{ text }}
    end
{%- endmacro %}

{#- The day a source's text value starts with, as TIMESTAMP at midnight, or
    null: notice_instant()'s last reading. The maintainer (poll of
    2026-10-11): "Fix the dates! the reader should be able
    to handle different format".

    THE DAY COMES FIRST, in one of four shapes, case and space aside:
    - month/day/year, with a year of four digits or of two, the Ouachita
      condition report's and IDPR's. A two-digit year is read as DuckDB's
      '%y' reads it, 00 to 68 as 2000 to 2068 and 69 to 99 as 1969 to 1999,
      so IDPR's '8/13/26' is 2026-08-13 (Upper Mesa Falls Area & Road
      Closure's DateStart, 1 of the 51 rows read 2026-10-09). Before
      2026-10-11 '%Y' read it as the year 26, which the phone would have
      printed as "from August 13, 26". A year of one or three digits is no
      date anyone states, and is null; so is a first part over 12, which
      would be day first, a guess no source here has asked for;
    - ISO, 'YYYY-MM-DD', where words follow it (a bare one is the cast
      above);
    - a month's name, full or cut short, before the day or after it, with a
      four-digit year: 'March 26, 2027', 'Sept. 30 2026', 'August 24th,
      2026', '26 March 2027', as extract/_notices.py's page reader reads
      them. A word no month's name starts with is no month.
    A day that does not exist ('9/31/2026', 'February 29, 2027') is null,
    never moved to the nearest one.

    THEN NOTHING, OR WORDS: the end of the value (a full stop or a comma
    allowed), a parenthesis, or a space and a letter, so a stated end
    followed by its caveat reads as that end. IDPR's area restrictions state
    Grimes Cr-Clear Cr Area Closure's Date_Order_Expires as '3/26/2027
    (annual renewal expected)' (1 of the 20 rows in the saved read of
    2026-10-09), which read as no date until 2026-10-11, so the notice
    greyed 90 days after its EditDate (2026-03-30), on 2026-06-28, though
    its order states that it runs to 2027-03-26. Measured on that read's
    staged start and end fields, the old reading and this one differ on
    that value alone: 0 of 16, 1 of 11, 0 of 35 and 0 of 26 distinct
    values. The two layers' Date_End and DateEnd, which
    seeds/notice_source_fields.csv does not stage, write most ends that way
    ('12/31/2026 unless rescinded'): 32 of their 43 distinct values read as
    a day now and as none before.
    NEVER A DATE OUT OF THE MIDDLE OF PROSE, and never a day whose words
    name another: a value that does not start with the day ('Closed until
    3/26/2027'), a range ('6/1/2026 - 9/30/2026', whose second day is not
    words) and a day followed by words holding a numeric date or a
    four-digit year ('4/1/2026 extended to 6/30/2026', which day ends it is
    the words' to say) are null. Words with no day ('Indefinite', 'Unknown',
    'Year-round', 'None stated') are null too. A null end is unknown: the
    notice greys by its own edit date instead (macros/notice_current_until.sql),
    never shown as current on a date nobody stated. -#}
{% macro notice_stated_day(text) -%}
    {#- Each pattern is a set block, so its backslashes reach RE2 as written
        and no Jinja string escaping stands between them. Group 4 of each is
        the words after the day. -#}
    {%- set words_after -%}
        ([.,;:]?\s*|[,;:]?\s*\(.*|[,;:]?\s+[a-z].*)$
    {%- endset -%}
    {%- set numeric -%}
        (?is)^\s*([0-9]{1,2})/([0-9]{1,2})/([0-9]{4}|[0-9]{2}){{ words_after }}
    {%- endset -%}
    {%- set iso -%}
        (?is)^\s*([0-9]{4})-([0-9]{2})-([0-9]{2}){{ words_after }}
    {%- endset -%}
    {%- set month_first -%}
        (?is)^\s*([a-z]{3,9})\.?\s+([0-9]{1,2})(?:st|nd|rd|th)?(?:\s*,\s*|\s+)([0-9]{4}){{ words_after }}
    {%- endset -%}
    {%- set day_first -%}
        (?is)^\s*([0-9]{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?(?:\s*,\s*|\s+)([0-9]{4}){{ words_after }}
    {%- endset -%}
    {%- set another_date -%}
        [0-9]\s*[/-]\s*[0-9]|[0-9]{4}
    {%- endset -%}
    {%- set months -%}
        ['january', 'february', 'march', 'april', 'may', 'june', 'july',
        'august', 'september', 'october', 'november', 'december']
    {%- endset -%}
    {#- strptime takes its format as a constant, so a four-digit year and a
        two-digit one are two branches. -#}
    case
        when
            regexp_full_match({{ text }}, '{{ numeric }}')
            and not regexp_matches(
                regexp_extract({{ text }}, '{{ numeric }}', 4),
                '{{ another_date }}'
            )
            and length(regexp_extract({{ text }}, '{{ numeric }}', 3)) = 4
            then try_strptime(
                regexp_extract({{ text }}, '{{ numeric }}', 1)
                || '/'
                || regexp_extract({{ text }}, '{{ numeric }}', 2)
                || '/'
                || regexp_extract({{ text }}, '{{ numeric }}', 3),
                '%m/%d/%Y'
            )
        when
            regexp_full_match({{ text }}, '{{ numeric }}')
            and not regexp_matches(
                regexp_extract({{ text }}, '{{ numeric }}', 4),
                '{{ another_date }}'
            )
            then try_strptime(
                regexp_extract({{ text }}, '{{ numeric }}', 1)
                || '/'
                || regexp_extract({{ text }}, '{{ numeric }}', 2)
                || '/'
                || regexp_extract({{ text }}, '{{ numeric }}', 3),
                '%m/%d/%y'
            )
        when
            regexp_full_match({{ text }}, '{{ iso }}')
            and not regexp_matches(
                regexp_extract({{ text }}, '{{ iso }}', 4),
                '{{ another_date }}'
            )
            then try_strptime(
                regexp_extract({{ text }}, '{{ iso }}', 1)
                || '-'
                || regexp_extract({{ text }}, '{{ iso }}', 2)
                || '-'
                || regexp_extract({{ text }}, '{{ iso }}', 3),
                '%Y-%m-%d'
            )
        when
            regexp_full_match({{ text }}, '{{ month_first }}')
            and not regexp_matches(
                regexp_extract({{ text }}, '{{ month_first }}', 4),
                '{{ another_date }}'
            )
            then try_strptime(
                regexp_extract({{ text }}, '{{ month_first }}', 3)
                || '-'
                || list_position(
                    list_transform(
                        {{ months }},
                        lambda month: starts_with(
                            month,
                            lower(
                                regexp_extract(
                                    {{ text }}, '{{ month_first }}', 1
                                )
                            )
                        )
                    ),
                    true
                )
                || '-'
                || regexp_extract({{ text }}, '{{ month_first }}', 2),
                '%Y-%m-%d'
            )
        when
            regexp_full_match({{ text }}, '{{ day_first }}')
            and not regexp_matches(
                regexp_extract({{ text }}, '{{ day_first }}', 4),
                '{{ another_date }}'
            )
            then try_strptime(
                regexp_extract({{ text }}, '{{ day_first }}', 3)
                || '-'
                || list_position(
                    list_transform(
                        {{ months }},
                        lambda month: starts_with(
                            month,
                            lower(
                                regexp_extract(
                                    {{ text }}, '{{ day_first }}', 2
                                )
                            )
                        )
                    ),
                    true
                )
                || '-'
                || regexp_extract({{ text }}, '{{ day_first }}', 1),
                '%Y-%m-%d'
            )
    end
{%- endmacro %}

{#- A source's text as words: a WordPress-shaped JSON value's `rendered`
    member where it is one (a post's `content` lands as that JSON), HTML tags
    cut out, and runs of whitespace made one space, so that a paragraph is
    compared as a reader would see it. -#}
{% macro notice_wording_text(text) -%}
    trim(
        regexp_replace(
            regexp_replace(
                coalesce(
                    json_extract_string(try_cast({{ text }} as json), '$.rendered'),
                    {{ text }}
                ),
                '<[^>]*>', ' ', 'g'
            ),
            '\s+', ' ', 'g'
        )
    )
{%- endmacro %}

{#- Whether a text value is a source's own wording rather than a short fact:
    at least `min_chars` characters with a space in it.
    int_warnings__notice_wording_unioned keeps only such values, so that a
    short value a mart may carry for its own reasons ('Closed', 'Yes', a
    road name) is never read as a source's paragraph, and the leak check
    cannot fail a build on a coincidence. @unvalidated: 30 is a guess at the
    shortest sentence-like wording, not a measurement; a leak shorter than it
    goes unseen. What would settle it is the length of the shortest
    description, note or comment value across the live notice layers. -#}
{% macro notice_is_wording(text, min_chars=30) -%}
    (
        length({{ text }}) >= {{ min_chars }}
        and contains({{ text }}, ' ')
    )
{%- endmacro %}

{#- One hash of a raw row's content, exactly as duplicates_are_exact compares
    two rows on a key: macros/row_hash.sql's row_hash() over every column of
    the raw table but the server's own row ids (row_hash_row_ids()). A club
    notice source's base model counts the different hashes on each key
    (`key_versions`), and int_closures__gate holds a source with any key over
    one, so a conflict holds that source's notices rather than publishing one
    copy chosen by load order. The column list is read from the warehouse,
    so a table that does not exist yet hashes as one row(null): no conflict,
    and no rows to have one. -#}
{% macro notice_row_version(relation) -%}
    {{ row_hash(relation, row_hash_row_ids()) }}
{%- endmacro %}
