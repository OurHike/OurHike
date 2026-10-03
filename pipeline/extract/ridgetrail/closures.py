"""Bay Area Ridge Trail Council: closures, drawn from nps/warnings.py's NPS alerts resource and three
_shared/ ArcGIS layers (decision 53, phase B, 2026-10-03).

NPS's alerts for park code `goga` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's `Park Closure` category is
the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a road
rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

This club's closures also arrive through _shared/ca_state_parks/ `cdpr_park_unit_status`;
_shared/midpen/ `midpen_preserve_access`; _shared/scc_parks/ `scc_parks_closed_areas`, each
extracted once in its steward's folder (decision 34). Its portion is assigned in dbt.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.ebparks.org/alerts-closures (html_page).

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Licence classes: Midpen is none_stated, a disclaimer whose one "may not be used" clause is about
liability, not reuse (quoted in the list at the end). SCC Parks is none_stated (empty licenseInfo;
access "Santa Clara County Parks and Recreation"). The EBRPD page is not GIS, so decision 21(a) does
…
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=goga` (the decision 53 inventory, batch 3, 2026-10-03): 6 (Park Closure 2, "
            "Caution 2, Information 2; e.g. 'Spare the Air Alert: Fire Restrictions in Effect October 3 - 4'). "
            "31.2 Ridge Trail miles are NPS's. Landed by nps/warnings.py as nps_alerts."
        ),
        (
            "via _shared/ca_state_parks/ `cdpr_park_unit_status`; _shared/midpen/ `midpen_preserve_access`; "
            "_shared/scc_parks/ `scc_parks_closed_areas` (decision 53 phase B, 2026-10-03): "
            "`cdpr_park_unit_status` reads `CSPParkUnit_Status_DOC/FeatureServer/0`; `midpen_preserve_access` "
            "reads `Preserve_Access_(public)/FeatureServer/0`; `scc_parks_closed_areas` reads "
            "`Santa_Clara_County_Parks_Closed_Areas_view/FeatureServer/1`"
        ),
        (
            "(coverage audit, 2026-10-01) `Park_Managers` takes 46 values. The largest by miles: Santa Clara "
            "County Parks 55.0, EBRPD 52.1, MROSD 50.2, NPS 31.2, Napa County Regional Parks 22.1, CDPR 21.0. "
            "Midpen `services2.arcgis.com/qmhndvC947rDNl6t/…/Preserve_Access_(public)/FeatureServer/0`: 195 "
            "polygons. `ACCESS='Closed'` 133 (Regular 122, Conservation Management Unit 8, Sensitive 2, Hazardous "
            "1), Open 60, Permit Only 2; edited 2026-07-21. `Trail_(public)/0`: `SEASCLOSE` Yes 31, Unknown 108, "
            "No 927; `TRLACCESS` Permit 10; edited 2026-09-17. Santa Clara County Parks …"
        ),
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=goga",
        "https://services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/CSPParkUnit_Status_DOC/FeatureServer/0",
        "https://services2.arcgis.com/qmhndvC947rDNl6t/arcgis/rest/services/Preserve_Access_(public)/FeatureServer/0",
        "https://services1.arcgis.com/4QPaqCJqF1UIaPbN/arcgis/rest/services/Santa_Clara_County_Parks_Closed_Areas_view/FeatureServer/1",
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
        "https://ridgetrail.org/{arcgis,server,gis}/rest/services",
    ),
    reason=(
        "drawn from nps/'s and _shared/ca_state_parks/'s and _shared/midpen/'s and _shared/scc_parks/'s "
        "resources, extracted once there (decision 34); checked names the layers this org's data arrives in; "
        "the org's own non-ArcGIS sources are listed in the docstring, still to wire"
    ),
)
