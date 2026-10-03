"""Nantahala Hiking Club: warnings, refused: the club's newsletter feed sits on a host whose robots.txt disallows
every agent but three social previewers (decision 53's inventory, 2026-10-03).

The club publishes its warnings (the Muskrat Creek Shelter bear, a Forest Service bear box wheeled into
place on August 26) inside its newsletters, which live on Mailchimp's archive. That host's robots.txt,
read for our agent on 2026-10-03, ends `User-agent: *` / `Disallow: /`, allowing only Twitterbot,
facebookexternalhit and LinkedInBot, so the feed is never fetched (decision 53: a robots.txt rule is a
refusal). The route forward is the club publishing its newsletter on its own site. The club's
https://nantahalahikingclub.org/newsletters/ page (WordPress page 1735, dateModified 2026-07-21) is an
index whose links point at that host and at PDFs, not a notice.

The land managers' warnings for the club's section arrive through usfs/closures.py's
`usfs_r08_northcarolina_alerts` (the Pisgah bear-canister requirement among them), and ATC's resources
already carry the Muskrat Creek bear activity.

Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch c3_at_clubs_south),
which read the feed (10 items, newest 2026-09-29) before its robots.txt was checked.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "https://us7.campaign-archive.com/robots.txt, read for our agent (decision 53 inventory, batch 1, "
        "2026-10-03): 'User-agent: *' followed by 'Disallow: /'; only Twitterbot, facebookexternalhit and "
        "LinkedInBot are allowed. The feed was not fetched.",
        "https://nantahalahikingclub.org/newsletters/ (200, redirecting to www.): WordPress page 1735, "
        "dateModified 2026-07-21, 'READ <MONTH> NEWSLETTER' links to the disallowed host and to PDFs.",
        "(coverage audit, 2026-10-01) the September 2026 issue: 'a bear has been causing problems near Muskrat "
        "Creek Shelter this season', and a Forest Service bear box placed there on August 26.",
    ),
    where=(
        "https://us7.campaign-archive.com/feed?u=925ff9fcd932406a399b6bcf3&id=e76f54b460",
        "https://us7.campaign-archive.com/robots.txt",
        "https://nantahalahikingclub.org/newsletters/",
    ),
    terms="https://us7.campaign-archive.com/robots.txt (read 2026-10-03): User-agent: * / Disallow: /",
    reason=(
        "refused: the host's robots.txt disallows the feed for every agent but three social previewers; held "
        "until the club publishes the newsletter where our agent may read it"
    ),
)
