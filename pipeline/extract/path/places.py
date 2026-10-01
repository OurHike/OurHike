"""Piedmont Appalachian Trail Hikers: places, drawn from another folder's resource (coverage audit
2026-10-01, batch p05_persist).

ATC: `maintainer_authorisation`. USFS: public domain. VA DCR, item
`aae5e3fc5e9848d8b551ce353f78e445`, is explicit_restriction: "Virginia Conservation Lands data are
freely accessible to the public. The re-distribution of this dataset for profit is prohibited."
copyrightText "Virginia Department of …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Loaded: ATC `AT_Communities` has "Marion/Smyth County" and "Bland County", both "Approved & '
        'Designated". `export_places.py` publishes them as `kind: town`. ATC parking under PATH: 12 (audit). '
        "Not loaded:",
        "The GWJ boundary: `EDW_ForestSystemBoundaries_01`, forestorgcode 0808.",
        "`EDW_Wilderness_02`: PATH's A.T. half-mile points fall inside Garden Mountain Wilderness and Hunting "
        "Camp Creek Wilderness (multipoint intersect).",
        "No EDW layer I found holds the Mount Rogers NRA polygon (SpecialInterestManagementArea and "
        "SpecialStatusArea return 0 for '%Rogers%').",
        "VA DCR …",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://path-at.org/",
        "https://services1.arcgis.com/PxUNqSbaWFvFgHnJ/arcgis/rest/services/VAConservationLands/FeatureServer/0",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
