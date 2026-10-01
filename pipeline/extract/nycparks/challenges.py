"""NYC Parks: challenges, nothing published (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

The Urban Park Rangers' "Explorer" and "Weekend Adventures" are programmes, not completion
challenges. Skeptic, 2026-10-01: verdict kept, with more checks. `/programs/rangers` links 7
sub-programmes (adventure course, conservation corps, custom adventures, Hart Island, history,
natural classroom …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Checked: the DPR catalogue (198), the `bigapps` index (45 feeds) and two web searches ("hiking '
        'challenge passport patch Urban Park Rangers", and a `nycgovparks.org`-restricted "challenge OR '
        'passport OR bucket list"). Nothing was found.',
    ),
    where=(
        "https://nycgovparks.org",
        "https://nycgovparks.org/",
        "https://nycgovparks.org/search",
    ),
)
