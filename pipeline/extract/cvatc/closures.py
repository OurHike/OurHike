"""Cumberland Valley Appalachian Trail Club: closures, read with warnings (decision 53 phase B,
2026-10-03). warnings.py's notice sources feed this type too: one upstream is one resource and one
raw table (decision 34), and dbt's decision 7 classifier splits each notice into closures or
warnings.

The club's news feed is read in warnings.py as `cvatc_news`; a notice-shaped post among its news
(2023-07-15's temporary bridge and reroute) is a closure only when decision 7's classifier reads it
so. The A.T. closures ATC carries stay with `atc_trail_updates`.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Cumberland Valley Appalachian Trail Club: closures, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

This is a general news feed and the yield is low. Items need classifying, and an unclassified item
goes to warnings (decision 7).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): News RSS `https://www.cvatclub.org/news/feed` (Weebly RSS 2.0,
10 items, 2020-09 → 2026-09). One reroute in it: 2023-07-15, a temporary bridge and reroute
"approximately one half mile north of the Scott Farm"

Its `where`: https://www.cvatclub.org/news/feed

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "warnings"
