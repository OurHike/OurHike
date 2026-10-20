{#-
    The A.T. mile at `along_mi` miles along one piece of
    int_trail_lines__mile_axis, from that piece's anchor lists: the SQL form
    of export_elevation.py's CalibratedPart.mile_at, which every published
    A.T. mile comes off (#652, #753).

    Branch for branch, and operation for operation, so the double it returns
    is the one numpy returns:
    - one anchor, or before the first: unit slope from the first anchor,
      `miles[0] + (along_mi - alongs_mi[0])`;
    - at or past the last: unit slope from the last, `miles[-1] + (along_mi -
      hi)`. At exactly the last anchor that adds 0.0, which is np.interp's
      own answer there;
    - between: np.interp's `slope*(x - xp[j]) + fp[j]` on the interval whose
      left end is the LAST anchor at or before along_mi. With two anchors at
      one along, that is where np.interp's search lands too, and it keeps the
      division away from a zero-length interval.

    Measured 2026-10-02 against the Python on ATC's live centerline and its
    4,395 half-mile markers: every piece's start and end mile identical to
    the bit, and the held-out gate this expression scores gave the same
    median and maximum, with a p95 one unit apart in the 17th significant
    digit (int_trail_lines__mile_axis_calibration and
    int_trail_lines__mile_axis_holdout have the run). Pass a column, not an
    expression: `along_mi` is repeated.
-#}
{% macro mile_at_along(along_mi, anchor_along_mi, anchor_mile) -%}
    (
        case
            when
                len({{ anchor_along_mi }}) = 1
                or {{ along_mi }} < list_extract({{ anchor_along_mi }}, 1)
                then
                    list_extract({{ anchor_mile }}, 1)
                    + ({{ along_mi }} - list_extract({{ anchor_along_mi }}, 1))
            when {{ along_mi }} >= list_extract({{ anchor_along_mi }}, -1)
                then
                    list_extract({{ anchor_mile }}, -1)
                    + ({{ along_mi }} - list_extract({{ anchor_along_mi }}, -1))
            else
                (
                    list_extract(
                        {{ anchor_mile }},
                        len(list_filter({{ anchor_along_mi }}, lambda anchor: anchor <= {{ along_mi }})) + 1
                    )
                    - list_extract(
                        {{ anchor_mile }},
                        len(list_filter({{ anchor_along_mi }}, lambda anchor: anchor <= {{ along_mi }}))
                    )
                )
                / (
                    list_extract(
                        {{ anchor_along_mi }},
                        len(list_filter({{ anchor_along_mi }}, lambda anchor: anchor <= {{ along_mi }})) + 1
                    )
                    - list_extract(
                        {{ anchor_along_mi }},
                        len(list_filter({{ anchor_along_mi }}, lambda anchor: anchor <= {{ along_mi }}))
                    )
                )
                * (
                    {{ along_mi }}
                    - list_extract(
                        {{ anchor_along_mi }},
                        len(list_filter({{ anchor_along_mi }}, lambda anchor: anchor <= {{ along_mi }}))
                    )
                )
                + list_extract(
                    {{ anchor_mile }},
                    len(list_filter({{ anchor_along_mi }}, lambda anchor: anchor <= {{ along_mi }}))
                )
        end
    )
{%- endmacro %}
