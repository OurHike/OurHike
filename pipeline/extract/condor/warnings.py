"""Condor Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

Same licences. The PSW model is a research product; its licenseInfo is an HTML block that was not
read in full. Do not render it as a current hazard (Reasoned). LPFA's posts remain a non-GIS lead,
already in the audit.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Same LPNF alerts page. Fire-restriction alerts: "Los Padres Fire Use and Firearm Restrictions" '
        '("Prohibits building, maintaining, attending, or using a fire, campfire, or stove fire… except in the '
        'Designated Campfire Use Sites"), "Santa Barbara Front Country Fire Use Restrictions", "West Cuesta '
        'Fire Use Restrictions", and "San Carpoforo Beach Prohibition of Overnight Camping and Campfires". '
        'There are also "Santa Lucia Ranger District Storm Damage Recovery" and "Occupancy and Use Forest '
        'Order" (stay limits). WFIGS perimeters as for closures. USFS PSW Research Station publishes …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://condortrail.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
