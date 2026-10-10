"""Texas Parks and Wildlife Department: state-park alert pages, hourly, extracted here once for every club that
draws on them (decision 53 phase B, 2026-10-03). TPWD has no club folder (decision 18), so it lives in
_shared/, and tx_tamers/ carries the `via` notes naming it (decision 34).

- `tpwd_davis_mountains_alerts`: https://tpwd.texas.gov/state-parks/davis-mountains/alert ('Park
  Alerts': a burn ban from Jan. 1, 2026, and the primitive area closed for hunts Oct. 2-10, Nov. 6-11
  and Feb. 19-24).
- `tpwd_mckinney_falls_alerts`: https://tpwd.texas.gov/state-parks/mckinney-falls/alert (a burn ban
  from Aug. 11, 2026).
- `tpwd_caprock_canyons_alerts`: https://tpwd.texas.gov/state-parks/caprock-canyons/alert, the park that
  holds the Caprock Canyons State Park Trailway (burn ban, bison safety, lake and park closures, 2026-10-09).
  Held, unlike the two above: decision 122 (the maintainer's poll, 2026-10-09) loads a candidate steward's
  layers held until its trail_orgs.json row is approved (decision 121), and this one came with that review.

Each is one PageNotice (extract/_notices.py), read live under our agent on 2026-10-03 after
tpwd.texas.gov's robots.txt (/tours/, /files/, /API/ and search paths disallowed, nothing matching
/state-parks/<park>/alert, no Crawl-delay). Neither states a page date; each item's date is in its own
heading, which the reader does not parse. Their weak ETag was identical on both parks' pages and on
TPWD's policy pages, a site stamp, so it never decides FRESH. TPWD's copyright policy forbids copying
"in any form or medium without the prior written consent" outside news releases; it names no automated
access, so this is decision 55's case (TPWD is named there): facts and a link, the policy quoted on
each row. Another park is another registry row.
"""

from extract._kinds import page_notice

TYPE = "closures"
CLAIMS = ("tpwd_davis_mountains_alerts", "tpwd_mckinney_falls_alerts", "tpwd_caprock_canyons_alerts")
RESOURCES = [page_notice(key) for key in CLAIMS]
