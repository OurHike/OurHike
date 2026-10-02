{#-
    Confirmed ascent over a list of elevations, as lib/elevation_gain.py's
    cumulative_gain_over_gaps counts it (EL10 of pipeline/ELT.md's ledger):
    the dead band `threshold`, in the elevations' own unit, and a null as a
    break, so each unbroken run is measured on its own and a gap adds
    nothing. `values` is a DOUBLE[] expression in walk order; the answer is a
    DOUBLE in the same unit. Loss is this on the negated elevations, as
    loss_over_gaps takes it.

    THE SAME ARITHMETIC IN THE SAME ORDER. One left fold over the list,
    holding what cumulative_gain holds as it walks a run: the running low and
    high since the last confirmed turning point, which way the ground is
    going (unknown until it has moved by `threshold`), and the climb banked so
    far, plus the total of the runs already closed. A climb is banked whole,
    peak minus trough, once the ground has come back down by `threshold`; a
    climb still rising when its run ends is banked too. A null closes the
    run, adding its climb to the total as `total += cumulative_gain(run)`
    does, and one null appended to the list closes the last run, as the
    Python's closing `total + cumulative_gain(run)` does. Every comparison and
    every addition is the Python's, on the same doubles in the same order,
    so the answer is the same double: tests/test_dbt_elevation_parity.py
    holds it to the library's own cases and to reference/gain_vectors.json,
    which the TypeScript copy (client/src/lib/elevationGain.ts) reads too.

    THE STATE is a DOUBLE[] of six: the total of closed runs, the count in
    the open run, its low, its high, which way it is going (1 up, 0 down,
    null unknown) and the climb it has banked. DuckDB's list_reduce folds a
    list into a value of the list's own element type, so each elevation is
    first wrapped in a list of one. A list rather than a struct, because
    SQLFluff 4.3.0 cannot parse struct access inside a lambda, and
    list_value() rather than a bracket literal for the same caution. The
    two-parameter lambda uses DuckDB's arrow, deprecated since 1.3 and still
    accepted by 1.5.4 and 1.5.5 (int_elevation__sample_points says so too).

    `threshold` MUST BE A CONSTANT, never a column. DuckDB 1.5.5's
    list_reduce reads a column the lambda captures from the wrong row once
    lists of different lengths share a vector: a fold adding each row's own
    value was wrong on 3,861 of 5,000 rows with lists of 0 to 9 elements,
    and right on every row with equal lengths, one row at a time, or a
    constant captured (measured 2026-10-02). Every caller passes one built
    from vars.

    The `set`s below name the state's six places and the elevation, and
    nothing else in this file is Jinja but the two arguments.
-#}
{%- macro dead_band_gain(values, threshold) -%}
{%- set value = "list_extract(item, 1)" -%}
{%- set total = "list_extract(state, 1)" -%}
{%- set count = "list_extract(state, 2)" -%}
{%- set low = "list_extract(state, 3)" -%}
{%- set high = "list_extract(state, 4)" -%}
{%- set rising = "list_extract(state, 5)" -%}
{%- set climb = "list_extract(state, 6)" -%}
{%- set new_low = "(case when " ~ value ~ " < " ~ low ~ " then " ~ value ~ " else " ~ low ~ " end)" -%}
{%- set new_high = "(case when " ~ value ~ " > " ~ high ~ " then " ~ value ~ " else " ~ high ~ " end)" -%}
list_extract(
    list_reduce(
        list_transform(
            list_append({{ values }}, cast(null as double)),
            lambda elevation: list_value(elevation)
        ),
        (state, item) -> case
            -- A break: bank the open run's climb, a climb still rising
            -- included, and start the next run empty.
            when {{ value }} is null
                then list_value(
                    {{ total }} + case
                        when {{ rising }} = 1
                            then {{ climb }} + ({{ high }} - {{ low }})
                        else {{ climb }}
                    end,
                    cast(0 as double),
                    cast(null as double),
                    cast(null as double),
                    cast(null as double),
                    cast(0 as double)
                )
            -- The first sample of a run is its low and its high.
            when {{ count }} = 0
                then list_value(
                    {{ total }},
                    cast(1 as double),
                    {{ value }},
                    {{ value }},
                    cast(null as double),
                    cast(0 as double)
                )
            -- Rising: a new high, or a fall of the dead band that confirms
            -- the peak and banks the climb whole.
            when {{ rising }} = 1
                then case
                    when {{ value }} > {{ high }}
                        then list_value(
                            {{ total }}, {{ count }} + 1, {{ low }}, {{ value }},
                            cast(1 as double), {{ climb }}
                        )
                    when {{ value }} <= {{ high }} - ({{ threshold }})
                        then list_value(
                            {{ total }}, {{ count }} + 1, {{ value }}, {{ high }},
                            cast(0 as double), {{ climb }} + ({{ high }} - {{ low }})
                        )
                    else list_value(
                        {{ total }}, {{ count }} + 1, {{ low }}, {{ high }},
                        cast(1 as double), {{ climb }}
                    )
                end
            -- Falling: a new low, or a rise of the dead band that turns it.
            when {{ rising }} = 0
                then case
                    when {{ value }} < {{ low }}
                        then list_value(
                            {{ total }}, {{ count }} + 1, {{ value }}, {{ high }},
                            cast(0 as double), {{ climb }}
                        )
                    when {{ value }} >= {{ low }} + ({{ threshold }})
                        then list_value(
                            {{ total }}, {{ count }} + 1, {{ low }}, {{ value }},
                            cast(1 as double), {{ climb }}
                        )
                    else list_value(
                        {{ total }}, {{ count }} + 1, {{ low }}, {{ high }},
                        cast(0 as double), {{ climb }}
                    )
                end
            -- No direction yet: widen the low and the high, and take a
            -- direction once they are the dead band apart, up if this
            -- sample is the high.
            else list_value(
                {{ total }},
                {{ count }} + 1,
                {{ new_low }},
                {{ new_high }},
                case
                    when {{ new_high }} - {{ new_low }} >= ({{ threshold }})
                        then case
                            when {{ value }} >= {{ new_high }} then cast(1 as double)
                            else cast(0 as double)
                        end
                end,
                {{ climb }}
            )
        end,
        list_value(
            cast(0 as double),
            cast(0 as double),
            cast(null as double),
            cast(null as double),
            cast(null as double),
            cast(0 as double)
        )
    ),
    1
)
{%- endmacro -%}

{#-
    The dead band in feet, as lib/elevation_gain.py's DEFAULT_THRESHOLD_FT
    is: DEFAULT_THRESHOLD_M over METERS_PER_FOOT, both from vars, as one
    double division, so a constant for dead_band_gain's `threshold`.
-#}
{%- macro elevation_gain_threshold_ft() -%}
(
    cast('{{ var("elevation_gain_threshold_m") }}' as double)
    / cast('{{ var("elevation_metres_per_foot") }}' as double)
)
{%- endmacro -%}
