"""NC Mountains-to-Sea State Trail: challenges, the State Parks' passport and 100-Mile Challenge, and not
landed (decision 54 wave 5, section K, 2026-10-04).

Both are the Division of Parks and Recreation's (nc_dpr/challenges.py notes them): the Passport is a stamp booklet
kept at park offices, the 100-Mile Challenge's site is being rebuilt.

The note this replaces read, whole:

NC Mountains-to-Sea Trail (state-published layer): challenges, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

MST completion recognition belongs to FMST (c7). The 100-Mile Challenge is distance-logged anywhere in
NC, not a list of places, so it does not fit #1780's places-based challenge model (see "Skeptic pass").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: `ncparks.gov/education/passport-program`. It still
exists, but "We are no longer offering prizes". Skeptic adds (Measured): the NC State Parks 100-Mile
Challenge. `ncparks.gov/recreation/news/100-mile-challenge` (HTTP 200) says the programme's site is
being rebuilt ("it will be a few more months") and that badges continue through its Facebook page. The
programme's own site `nc100miles.org` fails TLS from here today (certificate name mismatch). The sitemap
does not list the page.

Its `where`: https://ncparks.gov/education/passport-program
https://ncparks.gov/recreation/news/100-mile-challenge https://nc100miles.org

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("nc_dpr/challenges.py's note reads https://www.ncparks.gov/education/passport-program, 2026-10-04",),
    where=("https://www.ncparks.gov/education/passport-program",),
    reason="not this type: the parks' stamp passport (nc_dpr/'s note)",
)
