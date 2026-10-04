"""Friends of the Mountains-to-Sea Trail: places, behind a wall (decision 54, wave 5, read 2026-10-04).

mountainstoseatrail.org answered SiteGround's captcha (HTTP 202, `SG-Captcha: challenge`, a meta refresh to
/.well-known/sgcaptcha/) on three of the four requests made for its robots.txt on 2026-10-04, so no page was
asked: a wall is UNKNOWN and stops there, and is never worked round. The one robots.txt answer that came back
(Yoast's: `User-agent: *` disallows /wp-json/ and search) is recorded below.

What the coverage audit found behind it: 18 segment pages and the shuttle-services, trail-angels and
trailhead-kiosks pages. A trail angel is a private person offering help, and a shuttle listing is a name and a
telephone number, neither of which ever loads (ELT.md, "Who may publish", rule 8), whatever the wall does. The
trailheads themselves are fmst_primary_trailheads (fmst/points_of_interest.py), the club's own sheet.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "mountainstoseatrail.org/robots.txt under lib/user_agent.py's agent, 2026-10-04T18:19:53Z to 18:20:27Z: "
        "three answers of 202 with SiteGround's challenge (179 bytes, `SG-Captcha: challenge`) and one 200, "
        "Yoast's `User-agent: *` / `Disallow: /?s=`, `/page/*/?s=`, `/search/`, `/wp-json/`, `/?rest_route=`; no "
        "page was asked.",
        "the coverage audit (2026-10-01, batch c7_regional_4): 18 segment pages, `/segment/1/` … `/segment/18/`, "
        "plus `/the-trail/shuttle-services/`, `/the-trail/trail-angels/` and `/the-trail/trailhead-kiosks/`.",
    ),
    where=("https://mountainstoseatrail.org/robots.txt", "https://mountainstoseatrail.org/"),
    reason="walled: SiteGround's captcha answers robots.txt most of the time; not solved, not worked round",
)
