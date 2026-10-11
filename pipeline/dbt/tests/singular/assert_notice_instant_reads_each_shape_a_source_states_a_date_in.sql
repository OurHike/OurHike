-- macros/notices.sql's notice_instant(), the one reader of a club notice
-- source's dates, run on made-up values in each shape a source states one
-- in, so a parse that drifts fails here rather than on one club's rows in an
-- hourly run. The case that made it: IDPR's '8/13/26' (Upper Mesa Falls Area
-- & Road Closure's DateStart, read 2026-10-09), which '%Y' alone read as
-- the year 26 until 2026-10-11, a start the phone would have printed as
-- "from August 13, 26". Words are never a date, and a year of one or three
-- digits is none anyone states. Every dbt command build_marts.py runs has
-- TZ=UTC, the zone a value with no offset is read in. Returns one row per
-- value read otherwise than it should be.
with cases as (
    select
        cases.stated,
        cast(cases.expected as timestamptz) as expected
    from (
        values
        ('1696118400000', '2023-10-01 00:00:00+00'),
        ('2026-10-02', '2026-10-02 00:00:00+00'),
        ('2026-10-02 00:00:00.0', '2026-10-02 00:00:00+00'),
        ('2026-10-02T12:30:00Z', '2026-10-02 12:30:00+00'),
        ('Fri, 02 Oct 2026 12:30:00 GMT', '2026-10-02 12:30:00+00'),
        ('12/31/2026', '2026-12-31 00:00:00+00'),
        ('1/5/2026', '2026-01-05 00:00:00+00'),
        ('8/13/26', '2026-08-13 00:00:00+00'),
        ('8/13/202', null),
        ('8/13/2', null),
        ('Indefinite', null),
        ('12/31/2026 unless rescinded', null)
    ) as cases (stated, expected)
),

readings as (
    select
        stated,
        expected,
        {{ notice_instant('stated') }} as instant
    from cases
)

select
    stated,
    expected,
    instant
from readings
where instant is distinct from expected
