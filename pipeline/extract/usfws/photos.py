"""U.S. Fish & Wildlife Service: photos, the image library behind a robots.txt disallow (decision 54 wave 5,
section K, 2026-10-04).

digitalmedia.fws.gov redirects to https://www.fws.gov/search/images (the coverage audit), and www.fws.gov's
robots.txt disallows /search/ for every agent ('Disallow: /search/'), so the library is not read. The refuge pages'
own photographs carry no per-photo licence field a manifest row could hold (not checked page by page).

The note this replaces read, whole:

US Fish & Wildlife Service: photos, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Federal works are generally public domain. Per-image credit was not checked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `digitalmedia.fws.gov` redirects to
`https://www.fws.gov/search/images`.

Its `where`: https://www.fws.gov/search/images https://digitalmedia.fws.gov

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.fws.gov/robots.txt (read 2026-10-04): 'Disallow: /search/'; https://www.fws.gov/search/images not fetched",
    ),
    where=("https://www.fws.gov/search/images",),
    reason="refused: robots.txt disallows /search/ (`Disallow: /search/`)",
)
