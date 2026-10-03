"""Texas Trail Tamers: closures, drawn from _shared/tpwd/'s two state-park alert pages (decision 53 phase B,
2026-10-03).

The alerts on the club's trails are Texas Parks and Wildlife's, per park, and TPWD has no club folder, so
its pages land once in _shared/tpwd/park_alerts.py (decision 34): Davis Mountains State Park's
(`tpwd_davis_mountains_alerts`: primitive-area closures for hunts, Oct. 2-10, Nov. 6-11 and Feb. 19-24,
and a burn ban) and McKinney Falls State Park's (`tpwd_mckinney_falls_alerts`: a burn ban). TPWD's
copyright policy restricts copying, which decision 55 reads as facts and a link. Guadalupe Mountains is
NPS's and rides nps/'s alerts. The club's own site, texastrailtamers.org, could not be reached from
the session's sandbox (the proxy answered 502 to CONNECT, decision 53's inventory, batch 2), so
whether it publishes notices of its own is unknown.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p05_persist), whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via _shared/tpwd/park_alerts.py `tpwd_davis_mountains_alerts` and `tpwd_mckinney_falls_alerts` (decision "
        "53 phase B, 2026-10-03): each park's /alert page, read live as one PageNotice each.",
        "(decision 53 inventory, batch 2, 2026-10-03) https://texastrailtamers.org/: 'CONNECT tunnel failed, "
        "response 502' from the sandbox's proxy; not reached.",
        '(coverage audit, 2026-10-01) `https://tpwd.texas.gov/state-parks/davis-mountains/alert` (HTML, rendered on the server): "Primitive '
        "Area Closures. The primitive camping area will be closed on the following dates: 6 a.m. on Oct. 2 to 8"
        " a.m. on Oct. 10; 6 a.m. on Nov. 6 to 8 a.m. on Nov. 11; 6 a.m. on Feb. 19 to 8 a.m. on Feb. 24. Only "
        'permitted hunters will be allowed on these dates." `/state-parks/mckinney-falls/alert` has no closure '
        "today. Guadalupe Mountains is covered by the NPS Alerts API (b6_federal.md: 617 alerts nationwide; it "
        "needs a key, which I did not use). Tried: 1–3 no closure layer in TPWD's REST folders or …",
    ),
    where=(
        "https://tpwd.texas.gov/state-parks/davis-mountains/alert",
        "https://tpwd.texas.gov/state-parks/mckinney-falls/alert",
        "https://texastrailtamers.org/",
    ),
    reason="drawn from _shared/tpwd/'s resources, extracted once there (decision 34); checked names the pages this org's closures arrive in",
)
