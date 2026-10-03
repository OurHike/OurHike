"""Piedmont Appalachian Trail Hikers: warnings, drawn from usfs/closures.py's George Washington and Jefferson
National Forests alerts page (decision 53 phase B, 2026-10-03).

PATH publishes nothing of its own: path-at.org now redirects to www.piedmontathikers.org, a Wix site of
blog, forum and schedule with no conditions page (decision 53's inventory, batch 1, 2026-10-03). That is
another host, whose robots.txt and terms nobody read for this club, so it is not followed further. The
GWJ alerts page lands once, in usfs/closures.py as `usfs_r08_gwj_alerts` (decision 34), and the
warnings staging model reads it too.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p05_persist), whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "usfs/closures.py `usfs_r08_gwj_alerts` reads https://www.fs.usda.gov/r08/gwj/alerts (decision 53 phase "
        "B, 2026-10-03): 28 alert cards, fire-restriction 1, caution 3, information 24.",
        "(decision 53 inventory, batch 1, 2026-10-03) https://path-at.org/ redirects to "
        "https://www.piedmontathikers.org/ (Wix: blog, forum, schedule, a /blog-feed.xml); no conditions page.",
        '(coverage audit, 2026-10-01) The same page. "Fire Restrictions in place for Appalachian Trail" is not PATH\'s. Its order text limits'
        ' it to "between Beech Mountain Road (AT Milepost 489.4) and Massie Gap (AT Milepost 501 .8)", which '
        "are MRATC's miles; the loaded ATC row carries 489.4–502.4. \"Food Storage and Disposal Requirements - "
        'Bear Safety" (order 08-08-00-23-2, to 2028-08-30) lists campgrounds and recreation areas, none on '
        'PATH\'s A.T. by name. "Alcohol prohibition at the Appalachian Trail Partnership Shelter" (to '
        "2027-10-27) is a rule at a PATH shelter, not a hazard. Loaded ATC rows of category Animal or Alert in "
        "…",
    ),
    where=(
        "https://www.fs.usda.gov/r08/gwj/alerts",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://path-at.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's warnings arrive in",
)
