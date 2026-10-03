"""Upper Valley Trails Alliance: closures, refused: Trail Finder's terms forbid systematically extracting its
data (decision 53's inventory, 2026-10-03).

The alliance's alerts channel is Trail Finder (www.trailfinder.info), which UVTA administers for 973
partner managers' trails: each trail page carries an 'Alerts' tab ('Trails Flooding - Some or all of
the trails in this system are temporarily closed due to flooding.' on the sampled page, with the banner
'This trail system is currently CLOSED'), undated. Its robots.txt answered 200 with an empty body, so
robots does not refuse; its terms do, in the words `terms` quotes below, read 2026-10-03. A refusal is
a dated note, never routed round (decision 39); decision 55 lists Trail Finder among the refusals. The
route forward is Trail Finder's written consent, recorded as decision 47 records ATC's, and the
permission is Trail Finder's to give, not any one club's. uvtrails.org itself carries no closures (a
search for 'trail closure' found 6 op-eds, the coverage audit).

Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch c4_regional_1): "One
alerts channel for both closures and warnings."
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 3, 2026-10-03) https://www.trailfinder.info/terms, read whole for "
        "automated collection: its 'you agree that you shall not' list forbids systematic extraction and "
        "redistribution (quoted in `terms`). robots.txt: 200, empty. One trail page read "
        "(/trails/trail/abbey-pond), its Alerts tab and CLOSED banner; 973 trails listed.",
        '(coverage audit, 2026-10-01) Trail Finder trail pages carry an "Alerts" tab. The Monadnock example reads '
        '"Day Use Reservation Required". uvtrails.org\'s search for "trail closure": 6 hits, all op-eds.',
    ),
    where=(
        "https://www.trailfinder.info/terms",
        "https://www.trailfinder.info/trails",
        "https://uvtrails.org",
    ),
    terms=(
        '"Furthermore, you agree that you shall not: ... Collect information about other visitors to our website '
        "without their consent or otherwise systematically extract data or data fields, including without "
        'limitation any financial data or email addresses;" and "Redistribute any content, including data, '
        "provided by us in any manner whatsoever including by means of printed publication, fax broadcast, web "
        'pages, e-mail, web newsgroups or forums, or any other electronic or paper-based service or method;" '
        "(https://www.trailfinder.info/terms, read 2026-10-03)"
    ),
    reason="refused: Trail Finder's terms forbid systematic extraction and redistribution; held until Trail Finder permits in writing",
)
