"""Potomac Appalachian Trail Club: closures, from its trails page banner and the Tuscarora Trail's updates page,
hourly (decision 53 phase B, 2026-10-03).

Both read live under our agent on 2026-10-03, each as one PageNotice (extract/_notices.py) that lands a
title, a hash of the page's region and the link, and no text:

- `patc_trails_banner`: https://www.patc.net/trails (robots.txt: `User-agent: *` with a Content-Signal
  line and no Disallow). The page has no <main> or <article>, so the region is <body> (4,308
  characters); it carried the banner 'Byron Bridge Update: Final Installation & Closure Starting July
  27!', the C&O Canal towpath stairway. The banner names an ATC staff member's e-mail address, which
  never lands.
- `patc_tuscarora_updates`: https://www.hikethetuscarora.org/updates (Wix; robots.txt `User-agent: *` /
  `Allow: /`). 'Virginia Tuscarora Trail Detour': the Doll Ridge section, Three Top Mountain to
  Riverview Drive, "closed due to loss of landowner permission", detour about 7 miles. SAFETY:
  `usfs_trails` already draws that 3.7-mile line to hikers as 'TUSCARORA - DOLL RIDGE' (the coverage
  audit, Measured 2026-10-01), so this closure is the strongest case in decision 53's batch 5 for
  reaching a phone before the line does. Neither page states a date.

PATC's A.T. closures arrive through atc/ (decision 34). Its warnings channels (the Tuscarora section
guides' advisories, an anonymously editable maintenance layer) stay not_available.toml [patc.warnings]'s note.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c2_at_clubs_mid), whose `checked` named both pages and said "There is no feed for either: `/feed/rss2`
is the newsletter, and none of the 58 services is a closures layer."
"""

from extract._kinds import page_notice

CLAIMS = ("patc_trails_banner", "patc_tuscarora_updates")
RESOURCES = [page_notice(key) for key in CLAIMS]
