"""Nantahala Hiking Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Prose; most items are club news. ATC LOADED already carries Muskrat Creek bear activity, so this is
a cross-check plus the bear-box fact. The feed also carries volunteer-hour reminders, so filter by
title ("Nantahala Hiking Club Newsletter").

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://us7.campaign-archive.com/feed?u=925ff9fcd932406a399b6bcf3&id=e76f54b460 (rss - robots.txt
disallows it, so not to be fetched); https://nantahalahikingclub.org/newsletters/ (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/newsletters/` (page, modified 2026-07-21) links bimonthly Mailchimp issues (2025–2026) and quarterly"
        " PDFs (2023–2024). The Mailchimp archive has an RSS feed, "
        "`https://us7.campaign-archive.com/feed?u=925ff9fcd932406a399b6bcf3&id=e76f54b460` (machine-readable; "
        '10 items, newest 2026-09-29; full HTML bodies). The September 2026 issue (2026-09-01): "a bear has '
        'been causing problems near Muskrat Creek Shelter this season", and a Forest Service bear box was '
        '"wheeled … into place near Muskrat Creek Shelter on August 26". Each issue has a "Recent Trail '
        'Maintenance" log by date and section …',
    ),
    where=(
        "https://us7.campaign-archive.com/feed?u=925ff9fcd932406a399b6bcf3&id=e76f54b460",
        "https://nantahalahikingclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
