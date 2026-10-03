"""NC Division of Parks & Recreation — NC Trails: challenges, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

The stamp-location list was not found as data. The 100-Mile Challenge counts miles anywhere and is
not place-based, so its state is UNKNOWN. While its site is down, its only live channel is Facebook,
which a pipeline cannot use (maintainer decision).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Passport Program, `https://www.ncparks.gov/education/passport-program`: free paper booklet with stamps"
        " at 34 parks, 4 recreation areas, 3 natural areas and 9 state trails with designated stamp locations. "
        "Prizes discontinued. The NC 100-Mile Challenge (`nc100miles.org`) failed TLS today: the certificate "
        "does not match the host.",
        'Skeptic adds (Measured 2026-10-01): `nc100miles.org` still fails TLS ("no alternative certificate '
        "subject name matches\"), and plain HTTP answers 530. DPR's own notice, "
        '`https://www.ncparks.gov/recreation/news/100-mile-challenge`, says the site is being rebuilt "from …',
    ),
    where=(
        "https://www.ncparks.gov/education/passport-program",
        "https://www.ncparks.gov/recreation/news/100-mile-challenge",
        "https://nc100miles.org",
        "https://www.ncparks.gov/education/junior-ranger-program",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
