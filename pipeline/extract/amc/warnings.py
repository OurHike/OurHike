"""Appalachian Mountain Club: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

The New England Trail page closures.py reads carries the Harold Akey tent site's 'do not use the
water source' advisory, a water warning; which card it lands on is the maintainer's call (decision
2).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Appalachian Mountain Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

The Akey advisory is a water-source warning and belongs on that POI's card. That is not drought
(decision 2), but where it lands is for the maintainer to decide. The facility conditions were four
months stale on 2026-10-01. Skeptic spot-check: `/weather-trail-conditions/` returns 200.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): NET Massachusetts: "It is advised at this time to not use the
water source at the Harold Akey tent site until further notice" (Section 3, West Springfield). The
weather-trail-conditions page has dated condition text per facility, e.g. Highland Center "05/30/26
… snow, ice above 3000 ft". There are news posts such as
`.../news/bear-canisters-required-pemigewasett/`.

Its `where`: https://outdoors.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
