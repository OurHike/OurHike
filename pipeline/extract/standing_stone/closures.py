"""Standing Stone Trail Club: closures, from the club's two closure-notice pages, hourly (decision 53 phase B,
2026-10-03). BOTH ARE EXPIRED AND STILL SERVED.

Each page is one PageNotice (extract/_notices.py), read live under our agent on 2026-10-03 after the Wix
site's robots.txt (`User-agent: *` / `Allow: /`):

- `sstc_trail_relocation_notice` (/copy-of-trail-relocation-notice): "closed between Sheepskin Hollow
  Road and Vanderbilts Folly from October 1, 2022 to January 1, 2023". Ended 2023-01-01.
- `sstc_trail_closure_notice` (/trail-closure-notice, titled 'NOTICE 2: Temporary Trail Relocation'):
  the same closure dated "October 1, 2021 to January 1, 2022" (ended 2022-01-01), and a 2017
  landowner detour at Little Aughwick Creek north of SR 522 with no end date.

They land so the snapshot sees them change or vanish, and so phase C's rule can hold them: a notice
whose stated end date has passed is held back, never published as current (ELT.md, decision 53
phase C, which names these pages). The reader parses no prose, so the end dates are recorded in each
row's notes for the reviewer, not in a column. Three of the club's pages disagree about which notice
stands; that is the club's to answer. Neither page states an update date, and the Wix weak ETags are
not trusted.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c8_regional_5): "Page. That closure expired but is still linked, so dates must be honoured or it reads
as live."
"""

from extract._kinds import page_notice

CLAIMS = ("sstc_trail_relocation_notice", "sstc_trail_closure_notice")
RESOURCES = [page_notice(key) for key in CLAIMS]
