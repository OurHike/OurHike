"""Upper Valley Trails Alliance: warnings, refused for the same reason as closures.py: Trail Finder's terms
forbid systematically extracting its data.

The same 'Alerts' tab carries both, so the same refusal holds; closures.py quotes the terms and says what
would lift it. Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch
c4_regional_1): "See closures."
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 3, 2026-10-03) the same Trail Finder 'Alerts' tab and the same terms "
        "(https://www.trailfinder.info/terms), which forbid systematic extraction.",
        '(coverage audit, 2026-10-01) The same Trail Finder "Alerts" tab.',
    ),
    where=(
        "https://www.trailfinder.info/terms",
        "https://uvtrails.org/",
    ),
    terms=(
        '"Furthermore, you agree that you shall not: ... Collect information about other visitors to our website '
        "without their consent or otherwise systematically extract data or data fields, including without "
        'limitation any financial data or email addresses;" (https://www.trailfinder.info/terms, read 2026-10-03)'
    ),
    reason="refused: Trail Finder's terms forbid systematic extraction; held until Trail Finder permits in writing",
)
