"""National Washington-Rochambeau Revolutionary Route Association: places, behind a wall (decision 54, wave 5,
read 2026-10-04). The association's robots.txt and its state pages both answered SiteGround's captcha (202,
`SG-Captcha: challenge`, a refresh to /.well-known/sgcaptcha/), so neither was read: a wall is UNKNOWN and
stops there. NPS's Data API had 0 places for waro in its first 500 (the coverage audit, 2026-10-01).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "w3r-us.org/robots.txt answered 202 with SiteGround's challenge, then /md/ answered the same (173 bytes, "
        "`SG-Captcha: challenge`), read 2026-10-04 under lib/user_agent.py's agent; nothing past it was asked.",
        "the coverage audit (2026-10-01, batch c11_nht): state pages w3r-us.org/md/, /ct/, /va/, /ny/ and 'Trail "
        "History: Hub' (search index; pages).",
    ),
    where=(
        "https://w3r-us.org/md/",
        "https://w3r-us.org/",
    ),
    reason="walled: SiteGround's captcha answers robots.txt and the pages; not solved, not worked round",
)
