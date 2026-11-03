"""The U.S. Census Bureau's TIGER/Line state boundaries, `raw_census__census_tiger_states`: kept, and no longer read.

The rule (pipeline/ELT.md, 2026-10-04): a state-wide agency notice, such as
BLM's Utah fire restrictions, shows to a hike planned in that state that walks
that agency's trails. The phone has to tell whether a route is in a state, and
nothing it held could, so it gets the states' shapes. A federal statistical
agency is no club, so the file sits in _shared/.

`places` is the type because a state is a named area, and the type sets the
lane; no places model reads this table. Its one reader is
int_closures__notice_state_shapes, which simplifies only the states
dbt/seeds/notice_states.csv names, for conditions/notice_states.json. The app
never draws them.

NO LANE READS IT ANY MORE. Since robots.txt is read on every run,
www2.census.gov refuses the file to us (monthly run 31, 2026-10-10): its
robots.txt opens with `User-agent: *` above `User-agent: RavenCrawler` and
`Disallow: /`, and RFC 9309, which extract/_robots.py follows, reads those as
one group. The maintainer chose by poll on 2026-10-10 to keep the last copy
(ELT.md's open question 16), so the key is KEPT rather than read: the note
below quotes the refusal and says when to look again, and every monthly build
reads the table's last committed load, one row per state or equivalent (56 when
the file was read on 2026-10-04), keyed by `stusps`. Its sources.json row holds
the counts, the validators and the terms.
"""

from datetime import date

from extract._contract import Kept, NotAvailable

TYPE = "places"
CLAIMS = ("census_tiger_states",)
RESOURCES = ()  # none: the one claim is KEPT
KEPT = (
    Kept(
        key="census_tiger_states",
        note=NotAvailable(
            confirmed=date(2026, 10, 10),
            checked=(
                "https://www2.census.gov/robots.txt, read 2026-10-10T18:33:44Z under lib/user_agent.py's USER_AGENT: "
                "200, 398 bytes, Last-Modified Tue, 14 May 2024 20:27:57 GMT. Its first four lines are `terms`. RFC 9309 "
                "starts a new group only at a user-agent line that follows a rule, so the blank line separates nothing "
                "and `*` shares RavenCrawler's `Disallow: /`. extract/_robots.py's parse() gives OurHike-pipeline the "
                "one rule `Disallow: /`, and Robots.allows() refuses tl_2025_us_state.zip. Monthly run 31 "
                "(2026-10-10 00:49 UTC) was refused the same way (pipeline/ELT.md, Phase E).",
                "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html, read "
                "2026-10-10T18:38Z under USER_AGENT after www.census.gov's robots.txt, which disallows only "
                '/search-results.html to us: the newest vintage it lists is 2025, of which it says "All legal '
                "boundaries and names are as of January 1, 2025. The 2025 TIGER/Line Shapefiles were released on "
                'September 23, 2025." So the table kept is the newest vintage published (Measured that day).',
                "Not asked: the file itself, or any other www2.census.gov URL, which its robots.txt refuses.",
            ),
            where=(
                "https://www2.census.gov/robots.txt",
                "https://www2.census.gov/geo/tiger/TIGER2025/STATE/tl_2025_us_state.zip",
                "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
            ),
            # 180, the default, @unvalidated like it. By 2027-04-08 the 2026 vintage should be out (2025's came on
            # 2025-09-23), and a newer vintage is the first thing that could make the kept copy wrong.
            recheck_after_days=180,
            terms="User-agent: *\n\nUser-agent: RavenCrawler\nDisallow: /",
            reason=(
                "Kept, not read: the maintainer's poll of 2026-10-10 on pipeline/ELT.md's open question 16, \"Keep "
                "the last copy\". No lane asks www2.census.gov anything, and every monthly build reads the table's "
                "last committed load. State lines do not move within a TIGER vintage (Reasoned: the Bureau states "
                "each vintage's legal boundaries as of one date, January 1, 2025 for this one). Reading the file "
                "again waits on that robots.txt letting our agent in; asking the Bureau is the maintainer's to do "
                "(the dlt skill, 'Terms are never routed around')."
            ),
        ),
    ),
)
