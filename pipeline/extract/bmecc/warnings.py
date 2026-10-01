"""Blue Mountain Eagle Climbing Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

These are evergreen pages, not dated notices. The hunting rule is a fixed-window seasonal warning,
and the authority behind it is the PA Game Commission, so `_shared` should take it from PGC itself
(Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/appalachian-trail/fluorescent-orange` (page): "unlawful to be on state game lands from November 15 '
        'through December 15 without wearing a minimum of 250 square inches of fluorescent orange". The page '
        'says the rule "applies to Everyone", and the A.T. crosses PA State Game Lands "many times". '
        "`/appalachian-trail/bear-canisters` (page): free canister loans. `/appalachian-trail` (page): parking "
        'vandalism; Hamburg Reservoir "NO overnight parking… ticketed and towed"',
    ),
    where=("https://bmecc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
