"""MassGIS (Bureau of Geographic Information): warnings, nothing published (coverage audit 2026-10-01,
batch q01_persist).

Cross-reference for a MassWildlife (DFW) folder, not this row. All are on the EEA AGOL org
`services1.arcgis.com/7iJyYTjCtKsZS1LR`: `Pheasant_Quail_Polys_Publish_2020/0` "Stocking Frequency
Per Week", 156 polygons, data edited 2026-09-22, the fall hunting-pressure map;
`MassWildlifeLands/0`, 483, edited 2026-09-09, with a `PHEASANT` field; `LimitedAccess_AGOL/0`, 35
easements "with limited access to the public", edited 2026-09-09. Licence on those items: "The
Commonwealth of Massachusetts Executive Office of Energy and Environmental Affairs (EEA) and DFW
make(s) no representations or warranties, express or implied, with respect to the reuse of the
data…" → none_stated (a disclaimer, not a restriction).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Tried: (1) the same server walk, filtered for hunt/wild/stock/pheasant/fire/hazard/bear/tick/WMA. (2) "
        'The same orgid search. (3) Hub: "fire danger" 3, wildfire 6, hunting 5, "trail status" 8, bear 5, '
        '"pheasant" 2, "Wildlife Management Zones" 1; none MassGIS\'s, none a warning. The closest is MassDOT\'s '
        "`MA_Trail_Surface_Condition___User_Experience_WFL1/0`: 1,017 segments, data edited 2023-07-25, a "
        "roughness index (`wt_seg_TRI`, `UserExpGrade`), so a survey, not a notice. (4) Not applicable (not a "
        "club). (5) data.gov, Socrata as above. (6) mass.gov 403. (7) none reachable.",
    ),
    where=(
        "https://data.gov",
        "https://mass.gov",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
    ),
)
