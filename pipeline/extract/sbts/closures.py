"""Sierra Buttes Trail Stewardship: closures, from Yuba Expeditions' trail-conditions page, hourly (decision 53
phase B and decision 55, 2026-10-03).

`sbts_trail_conditions` reads https://www.yubaexpeditions.com/trail-conditions (the stewardship's own
storefront, "an extension of the NON-Profit Sierra Buttes Trail Stewardship") as one PageNotice
(extract/_notices.py), read live under our agent on 2026-10-03. Squarespace's robots.txt there
disallows `?format=json` and similar query forms for every agent, so the HTML is the only allowed form
and the reader asks the URL with no query. The page lists 40 named trails, each with a status word
('CLEAR', 'CLEAR lower bridge is damaged'), in network blocks each stamped 'Updated 9/4/26'; the
newest such stamp is the row's date. Only 'CLEAR' appears that day, so the word a closed trail would
get is unseen (the coverage audit). The footer's "Copyright © 2025 Sierra Buttes Trail Stewardship.
All Rights Reserved." is a copyright line, read under decision 55: facts and a link, quoted on the
row.

The status words are closures and warnings both (a damaged bridge on a trail still reading CLEAR is a
warning, decision 7), so warnings.py shares this file.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c6_regional_3): "A page, not machine-readable. Squarespace's `robots.txt` disallows `?format=json`, so a
parser must read the HTML."
"""

from extract._kinds import page_notice

CLAIMS = ("sbts_trail_conditions",)
RESOURCES = [page_notice("sbts_trail_conditions")]
