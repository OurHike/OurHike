"""Upper Valley Trails Alliance: places, refused by Trail Finder's terms (decision 54, wave 5). The 'Trailside
Services' map (businesses near trailheads) is Trail Finder's, whose terms forbid systematic extraction and
redistribution, quoted as uvta/closures.py records them (decision 53's inventory, 2026-10-03). Not fetched;
held until Trail Finder permits in writing.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "uvta/closures.py's refusal, read 2026-10-03 at https://www.trailfinder.info/terms; nothing was requested for this note.",
        "the coverage audit (2026-10-01, batch c4_regional_1): /services, a page and map; 'Consent needed.'",
    ),
    where=(
        "https://www.trailfinder.info/terms",
        "https://uvtrails.org/",
    ),
    terms=(
        '"Furthermore, you agree that you shall not: ... Collect information about other visitors to our website '
        "without their consent or otherwise systematically extract data or data fields, including without "
        'limitation any financial data or email addresses;" and "Redistribute any content, including data, provided'
        " by us in any manner whatsoever including by means of printed publication, fax broadcast, web pages, "
        'e-mail, web newsgroups or forums, or any other electronic or paper-based service or method;" '
        "(https://www.trailfinder.info/terms, read 2026-10-03)"
    ),
    reason="refused: Trail Finder's terms forbid systematic extraction and redistribution; held until Trail Finder permits in writing",
)
