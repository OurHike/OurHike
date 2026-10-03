"""Pinhoti Trail Alliance: warnings, published, and not landed (coverage audit 2026-10-01, batch
p02_persist).

Licence: open_licence, public domain, a federal work. Folder: `usfs`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fs.usda.gov/r08/alabama/alerts (html_page);
https://www.fs.usda.gov/r08/chattahoochee-oconee/alerts (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/r08/alabama/alerts/alabamas-national-forests-begin-prescribed-fires` and "
        "`…/food-storage-forest-order`. `…/r08/chattahoochee-oconee/alerts/be-bear-aware`, "
        "`…/chattahoochee-oconee-national-forest-begins-prescribed-fires`, `…/flash-flood-awareness`, "
        "`…/caution-waterfall-dangers` and `…/spring-2026-forest-wide-fire-restrictions`. ADCNR publishes "
        "`State_Park_Burn_Units_UTM_06_26_2023/MapServer`, burn-unit polygons and not a burn schedule (not "
        "counted). Tried: (1), (2), (4), (5) as for closures. (7) Alerts pages; no feed. The PTA group (the "
        "audit's prescribed-burn channel) stays behind its …",
    ),
    where=(
        "https://conservationgis.alabama.gov/adcnrweb/rest/services/State_Park_Burn_Units_UTM_06_26_2023/MapServer",
        "https://pinhotitrailalliance.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
