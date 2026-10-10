"""Pacific Northwest Trail Association: closures, from the trail-alerts page, hourly (decision 53 phase B,
2026-10-03).

`pnta_trail_alerts` reads https://www.pnt.org/pnta/know-before-you-go/plan-your-trip/trail-alerts/ as one
PageNotice (extract/_notices.py), read live under our agent on 2026-10-03 after www.pnt.org's robots.txt
(nothing these URLs reach is disallowed; no Crawl-delay). The page is one table of 7 closures (State,
Area, Miles Closed, Description, Detour, More Info; 'Section 6, Pasayten Wilderness', 60 miles), dated
by its own 'Last Updated: August 27, 2026', which lands as the row's date. No cell's text lands.

A LATER PER-ROW READER, IF ANYONE WRITES ONE, must read the table the way the coverage audit warned: one
row reads '0 miles', a reopening, and one has no miles at all, which is unknown and never zero. Its
'More Info' links are the agencies' own orders (USFS Region 6, NPS North Cascades), which usfs/ and nps/
extract first-hand.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c10_nst_rest): "Page, but tabular, with a miles-closed column. One row reads '0 miles' (reopened), and
that one must be read as an opening. ... The page reads 'Last Updated: August 27, 2026', which is the
date to carry."
"""

from extract._kinds import page_notice

CLAIMS = ("pnta_trail_alerts",)
RESOURCES = [page_notice("pnta_trail_alerts")]
