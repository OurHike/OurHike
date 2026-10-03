"""US Fish & Wildlife Service: challenges, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

FWS publishes no stamp-location list. Third-party lists (Waymarking) are somebody else's data.
Page-level only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Blue Goose Passport, mentioned on refuge pages such as `fws.gov/refuge/turnbull/visit-us/activities`. "
        "Booklet about $6–8 from Friends-group bookstores. Skeptic spot check: the Turnbull page carries a "
        '"Blue Goose Passport Stamp" heading and the text "Visitors to Turnbull NWR can collect their free Blue'
        ' Goose Passpor[t stamp]".',
    ),
    where=("https://fws.gov/refuge/turnbull/visit-us/activities",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
