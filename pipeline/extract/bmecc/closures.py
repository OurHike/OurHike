"""Blue Mountain Eagle Climbing Club: closures, drawn from another folder's resource (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Eckville is only proposed for closure and is not in `atc_updates.json`. If NPS acts, the club page
will probably say so before ATC's feed does (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'via atc `atc_trail_updates` ("Pennsylvania: 501 Shelter Closed", 1196.7). Club pages: the shelters '
        'page ("retired… NO Camping… in or around") and `/appalachian-trail/shelters/sos-save-our-shelters` '
        '("501 Shelter Currently Closed by the National Parks Service", "Eckville Shelter Proposed Closure")',
    ),
    where=("https://bmecc.org/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
