-- macros/notices.sql's notice_instant(), the one reader of a club notice
-- source's dates, run on made-up values in each shape a source states one
-- in, so a parse that drifts fails here rather than on one club's rows in an
-- hourly run. The cases that made it: IDPR's '8/13/26' (Upper Mesa Falls
-- Area & Road Closure's DateStart, read 2026-10-09), which '%Y' alone read
-- as the year 26 until 2026-10-11, a start the phone would have printed as
-- "from August 13, 26"; and IDPR's '3/26/2027 (annual renewal expected)'
-- (an area restriction's Date_Order_Expires, the same read), a day followed
-- by words, which read as no date until the same day, so its order greyed
-- months before the end it states. 14 of these 39 cases fail on the reading
-- before then, every day followed by words and every month's name (run
-- 2026-10-11 against both macros' compiled SQL, and again on 2026-10-15
-- against 245dff9b's notice_instant(), the one f911d1d7 replaced, in DuckDB
-- 1.5.5 at UTC); the last three are IDPR's own values. A day followed by
-- words is that day; words with no day, a day out of the middle of prose, a
-- range, words naming another date, a day that does not exist and a year of
-- one or three digits are none. Every dbt
-- command build_marts.py runs has TZ=UTC, the zone a value with no offset
-- is read in. Returns one row per value read otherwise than it should be.
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
        ('13/5/2026', null),
        ('9/31/2026', null),
        ('12/31/2026.', '2026-12-31 00:00:00+00'),
        ('3/26/2027(annual renewal expected)', '2027-03-26 00:00:00+00'),
        ('12/31/2026, Annual renewal anticipated', '2026-12-31 00:00:00+00'),
        ('10/15/2026 unless rescinded or extended', '2026-10-15 00:00:00+00'),
        ('8/13/26 (est.)', '2026-08-13 00:00:00+00'),
        ('2026-10-02 (approximate)', '2026-10-02 00:00:00+00'),
        ('March 26, 2027', '2027-03-26 00:00:00+00'),
        ('Sept. 30 2026', '2026-09-30 00:00:00+00'),
        ('August 24th, 2026', '2026-08-24 00:00:00+00'),
        ('26 March 2027 (renewal expected)', '2027-03-26 00:00:00+00'),
        ('March 26, 2027 (annual renewal expected)', '2027-03-26 00:00:00+00'),
        ('february 29, 2027', null),
        ('Marching 26, 2027', null),
        ('May 2027', null),
        ('Indefinite', null),
        ('Unknown', null),
        ('Year-round', null),
        ('None stated', null),
        ('Until rescinded', null),
        ('Closed until 3/26/2027', null),
        ('Order expires March 26, 2027', null),
        ('6/1/2026 - 9/30/2026', null),
        ('4/1/2026 extended to 6/30/2026', null),
        ('May 1, 2026 or June 30, 2026', null),
        ('12/31/2026 unless rescinded', '2026-12-31 00:00:00+00'),
        ('3/26/2027 (annual renewal expected)', '2027-03-26 00:00:00+00'),
        ('3/26/2027 unless recinded or renewed', '2027-03-26 00:00:00+00')
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
