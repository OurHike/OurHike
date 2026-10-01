"""Florida Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

If it is wanted at all, it is `_shared/` material, not FTA's. Skeptic, kept NOT_PUBLISHED: iTunes
lists Orange Blaze under artist "a named individual" (98 episodes, last 2023-12-22). A search also
surfaced On the Trail with Dale (`onthetrailwithdale.podbean.com`), described as FNST talks with FTA
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Orange Blaze: A Florida Trail Podcast" is Misti "Ridley" Little\'s independent show (her about page). '
        "It ran 2018–2023, with a pause announced 2023-12-22. FTA's media room links one episode. FTA produces "
        "none.",
    ),
    where=(
        "https://onthetrailwithdale.podbean.com",
        "https://floridatrail.org/",
    ),
)
