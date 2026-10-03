"""Natural Bridge Appalachian Trail Club: closures, from the club's announcements fragment, hourly (decision 53
phase B, 2026-10-03).

`nbatc_announcements` reads the HTML fragment the club's home page loads,
`home.nbatc.org/cgi-bin/nbatcNews.cgi?ACTION=getPosts&OFFSET=0&TYPE=updates&ROLES=`, as one PageNotice
(extract/_notices.py). home.nbatc.org serves no robots.txt (404, read 2026-10-03 under our agent), which
RFC 9309 reads as no rules. The fragment's 5 newest items are each `<h3>YYYY-MM-DD Title</h3><p>body</p>`;
it has no title of its own, so the row carries the registry's (`registry_title`), and its date is the
newest of the items' own ISO dates (the `date_pattern` below), 2025-09-03 on 2026-10-03. Nothing of the
items' text lands, only a hash of it. Club news is mixed in ('Awards Presentation', 2025-02-14), and
the closures and warnings are split in dbt (decision 7), which is why warnings.py shares this file.

NOT READ: `home.nbatc.org/cgi-bin/getNotice.cgi`, the second channel the coverage audit named, answered
500 without parameters and nobody knows its parameters (decision 53's inventory, batch 5).

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c2_at_clubs_mid): "Semi-structured (date + title + body). Neither the burn closure nor the Parkway
closure is in `atc_updates.json`." Its `checked` listed the 5 newest items: 2025-09-03 Blue Ridge
Parkway James River bridge, a year-long detour; 2025-04-28 prescribed burn, "The Appalachian National
Scenic Trail and Old Hotel Trail #515 will be closed throughout the day"; 2024-10-01 Blue Ridge Parkway
closed.
"""

from extract._kinds import page_notice

# The fragment's items open with their own date in ISO form; a page date read from them is the newest.
ISO_ITEM_DATE = r"(?P<date>(?P<iso>\d{4}-\d{2}-\d{2}))"

CLAIMS = ("nbatc_announcements",)
RESOURCES = [page_notice("nbatc_announcements", registry_title=True, date_pattern=ISO_ITEM_DATE)]
