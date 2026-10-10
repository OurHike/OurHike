"""Indiana DNR: the Knobstone Trail's conditions page, hourly, extracted here once for every club that draws on
it (decision 53 phase B, 2026-10-03). Indiana DNR has no club folder (decision 18), so it lives in
_shared/, and hoosier/ carries the `via` note naming it (decision 34).

- `in_dnr_knobstone_conditions`:
  https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/, one PageNotice
  (extract/_notices.py).

Read live under our agent on 2026-10-03 after www.in.gov's robots.txt (`User-agent: *` with only a
Sitemap line). The page states 'Knobstone Trail conditions Update: July 21, 2026', which lands as the
row's date, and 'TRAIL CONDITION: GOOD' with an advisories list; its two closure and reroute PDF links
sit inside HTML comments and are not read.

IN.GOV'S TERMS, two sentences, both quoted on the row. One restricts reuse ("No part of any content ...
may be reproduced ... other than for your personal use"), which is decision 55's case: facts and a
link. The other lists "bots" among "disruptive activities" a user may not engage in. Decision 75 (the
maintainer's poll, 2026-10-04, card Q6) reads it as not a refusal: it sits in a list of malicious
activity, and one request an hour under a named agent is neither, so this resource keeps to that rate.
"""

from extract._kinds import page_notice

TYPE = "closures"
CLAIMS = ("in_dnr_knobstone_conditions",)
RESOURCES = [page_notice("in_dnr_knobstone_conditions")]
