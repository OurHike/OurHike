"""Pinhoti Trail Alliance: warnings, drawn from usfs/closures.py's two national forests' alerts pages
(decision 53 phase B, 2026-10-03).

The prescribed-fire, food-storage, bear and flood alerts the coverage audit listed are cards on the
National Forests in Alabama's and the Chattahoochee-Oconee's alerts pages, which land once in
usfs/closures.py as `usfs_r08_alabama_alerts` and `usfs_r08_chattahoochee_oconee_alerts` (decision 34);
the warnings staging model reads them too.

THE CLUB'S OWN DOMAIN IS HIJACKED. https://pinhotitrailalliance.org/ answered 200 on 2026-10-03 with an
Indonesian online-lottery spam page (title 'GACOR188: Platform Terbaru Situs Toto Online Pasaran Macau
...'), its robots.txt the same HTML (decision 53's inventory, batch 3). Nothing is read from it, and
trail_orgs.json's `website` for this club and anything else that links a hiker there should stop
(a safety item for the maintainer; not changed here, being outside this file's scope). The PTA's
Facebook group sits behind a login.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p02_persist), whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/closures.py `usfs_r08_alabama_alerts` (29 alert cards) and `usfs_r08_chattahoochee_oconee_alerts` (30) (decision 53 phase B, 2026-10-03).",
        "`…/r08/alabama/alerts/alabamas-national-forests-begin-prescribed-fires` and "
        "`…/food-storage-forest-order`. `…/r08/chattahoochee-oconee/alerts/be-bear-aware`, "
        "`…/chattahoochee-oconee-national-forest-begins-prescribed-fires`, `…/flash-flood-awareness`, "
        "`…/caution-waterfall-dangers` and `…/spring-2026-forest-wide-fire-restrictions`. ADCNR publishes "
        "`State_Park_Burn_Units_UTM_06_26_2023/MapServer`, burn-unit polygons and not a burn schedule (not "
        "counted). Tried: (1), (2), (4), (5) as for closures. (7) Alerts pages; no feed. The PTA group (the "
        "audit's prescribed-burn channel) stays behind its …",
    ),
    where=(
        "https://www.fs.usda.gov/r08/alabama/alerts",
        "https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts",
        "https://conservationgis.alabama.gov/adcnrweb/rest/services/State_Park_Burn_Units_UTM_06_26_2023/MapServer",
        "https://pinhotitrailalliance.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the pages this org's warnings arrive in",
)
