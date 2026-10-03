"""Pinhoti Trail Alliance: closures, drawn from another folder's resource (decision 53 phase B,
2026-10-03).

This club's closures arrive through usfs/ `usfs_rec_opportunities_status` and the two national
forests' alerts pages, `usfs_r08_alabama_alerts` and `usfs_r08_chattahoochee_oconee_alerts`
(usfs/closures.py, decision 53 phase B), each extracted once in its steward's folder (decision 34).
Its portion is assigned in dbt.

THE CLUB'S OWN DOMAIN IS HIJACKED. https://pinhotitrailalliance.org/ answered 200 on 2026-10-03 with an
Indonesian online-lottery spam page (title 'GACOR188: Platform Terbaru Situs Toto Online Pasaran Macau
...'), its robots.txt the same HTML (decision 53's inventory, batch 3). Nothing is read from it, and
trail_orgs.json's `website` for this club and anything else that links a hiker there should stop
(a safety item for the maintainer; not changed here, being outside this file's scope). The PTA's
Facebook group sits behind a login.

Before decision 53 phase B, 2026-10-03, this note read:

Pinhoti Trail Alliance: closures, published, and not landed (coverage audit 2026-10-01, batch
p02_persist).

Licence: USFS: open_licence, public domain, a federal work. The EDW `copyrightText` is a disclaimer:
"The USDA Forest Service makes no warranty, expressed or implied…". Folder: `usfs`. The alerts are
pages, so they need the same scraper shape as the audit's Nez Perce alerts row.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via usfs/ `usfs_rec_opportunities_status` (decision 53 phase B, 2026-10-03): `usfs_rec_opportunities_status` reads `EDW/EDW_RecreationOpportunities_01/MapServer/0`",
        "via usfs/closures.py `usfs_r08_alabama_alerts` (29 alert cards) and `usfs_r08_chattahoochee_oconee_alerts` (30) (decision 53 phase B, 2026-10-03).",
        "(decision 53 inventory, batch 3, 2026-10-03) https://pinhotitrailalliance.org/ serves an online-lottery spam page (title 'GACOR188: ...'), robots.txt included: the domain is no longer the club's.",
        "National Forests in Alabama: `https://www.fs.usda.gov/r08/alabama/alerts` (HTML), 29 alert links, including `blue-horse-trail-closure`, `fsr607-closure` and `occupancy-and-use-forest-order-coleman-lake-pine-glen-warden-horse-camp-shoal`. Coleman Lake and Pine Glen are Pinhoti trailheads and camps. Chattahoochee-Oconee: `…/r08/chattahoochee-oconee/alerts`, 30 links, including `rough-ridge-trail-12-closed-cohutta-wilderness`, `windy-gap-trail-system-and-muskrat-road-temporarily-closed` and several FS-road closures. `EDW_RecreationOpportunities_01/MapServer/0` (14,211 points nationwide, field …",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0",
        "https://www.fs.usda.gov/r08/alabama/alerts",
        "https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts",
        "https://pinhotitrailalliance.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer and pages this org's closures arrive in",
)
