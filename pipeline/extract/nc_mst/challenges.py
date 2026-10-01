"""NC Mountains-to-Sea Trail (state-published layer): challenges, published, and not landed (coverage
audit 2026-10-01, batch b7_long_trails_states).

MST completion recognition belongs to FMST (c7). The 100-Mile Challenge is distance-logged anywhere
in NC, not a list of places, so it does not fit #1780's places-based challenge model (see "Skeptic
pass").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format page: `ncparks.gov/education/passport-program`. It still exists, but "We are no longer offering prizes".',
        "Skeptic adds (Measured): the NC State Parks 100-Mile Challenge. "
        "`ncparks.gov/recreation/news/100-mile-challenge` (HTTP 200) says the programme's site is being rebuilt"
        ' ("it will be a few more months") and that badges continue through its Facebook page. The programme\'s '
        "own site `nc100miles.org` fails TLS from here today (certificate name mismatch). The sitemap does not "
        "list the page.",
    ),
    where=(
        "https://ncparks.gov/education/passport-program",
        "https://ncparks.gov/recreation/news/100-mile-challenge",
        "https://nc100miles.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
