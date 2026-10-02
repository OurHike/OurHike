-- Everything the challenges port refused, one row per refusal, in the order
-- export_challenges.main() prints its report (CH08: "A list quietly
-- shrinking is the failure nobody notices, so a refusal is never just an
-- absence from the output"):
--   1. every publishers.json row or trail refused, in the file's order;
--   2. every challenge that did not publish: the misplaced files first, then
--      the files the resolver dropped, in path order (build_output()'s
--      `dropped[:0] = misplaced`);
--   3. every item that did not publish, challenge by challenge, item by item,
--      for each file that reached its items.
-- `report_line` is the line as the exporter prints it to stderr. The warn
-- test on `problem` is the exporter's closing ::warning::; to see the lines,
-- from pipeline/dbt:
--   dbt show --profiles-dir . --inline "select report_line
--     from intermediate.int_challenges__refusals order by refusal_order"
with publishers as (
    select * from {{ ref('int_challenges__publishers') }}
),

publisher_trails as (
    select * from {{ ref('int_challenges__publisher_trails') }}
),

resolved as (
    select * from {{ ref('int_challenges__resolved') }}
),

items as (
    select * from {{ ref('int_challenges__items') }}
),

refusals as (
    select
        1 as part,
        publisher_position as first_position,
        0 as second_position,
        'publishers.json' as refused,
        cast(null as varchar) as report_label,
        cast(null as varchar) as item_report_label,
        problem,
        problem as report_line
    from publishers
    where problem is not null
    union all
    select
        1 as part,
        publisher_position as first_position,
        trail_position as second_position,
        'publishers.json trail' as refused,
        cast(null as varchar) as report_label,
        cast(null as varchar) as item_report_label,
        problem,
        problem as report_line
    from publisher_trails
    where problem is not null
    union all
    select
        2 as part,
        -- Misplaced files are reported first, then the resolver's drops,
        -- then build_output()'s, each group in path order.
        drop_step as first_position,
        list_position as second_position,
        'challenge' as refused,
        report_label,
        cast(null as varchar) as item_report_label,
        problem,
        report_label || ': ' || problem as report_line
    from resolved
    where problem is not null
    union all
    select
        3 as part,
        resolved.list_position as first_position,
        items.item_position as second_position,
        'item' as refused,
        resolved.report_label,
        items.report_label as item_report_label,
        items.problem,
        resolved.report_label || ' / ' || items.report_label || ': '
        || items.problem as report_line
    from items
    inner join resolved
        on items.challenge_file_key = resolved.challenge_file_key
    where items.problem is not null and resolved.reached_items
)

select
    row_number() over (
        order by part, first_position, second_position
    ) as refusal_order,
    refused,
    report_label,
    item_report_label,
    problem,
    report_line
from refusals
