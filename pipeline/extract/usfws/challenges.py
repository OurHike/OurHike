"""U.S. Fish & Wildlife Service: challenges, the Blue Goose Passport, a booklet, and not landed (decision 54
wave 5, section K, 2026-10-04).

The Blue Goose Passport is a booklet (about $6 to $8 from Friends groups' bookstores) stamped at refuges, mentioned
refuge by refuge ('Visitors to Turnbull NWR can collect their free Blue Goose Passport stamp'); no page lists its
stamp places. No request sent today.

The note this replaces read, whole:

US Fish & Wildlife Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

FWS publishes no stamp-location list. Third-party lists (Waymarking) are somebody else's data.
Page-level only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Blue Goose Passport, mentioned on refuge pages such as
`fws.gov/refuge/turnbull/visit-us/activities`. Booklet about $6–8 from Friends-group bookstores. Skeptic
spot check: the Turnbull page carries a "Blue Goose Passport Stamp" heading and the text "Visitors to
Turnbull NWR can collect their free Blue Goose Passpor[t stamp]".

Its `where`: https://fws.gov/refuge/turnbull/visit-us/activities

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) fws.gov/refuge/turnbull/visit-us/activities: 'Blue Goose Passport Stamp'",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://fws.gov/refuge/turnbull/visit-us/activities",),
    reason="not this type: a stamp booklet kept at refuge offices, with no published list",
)
