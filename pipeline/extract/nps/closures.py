"""National Park Service: closures, from the alerts and road events nps/warnings.py lands (decision 53, phase B).

One upstream is one resource (decision 34), so the alerts land once, in
nps/warnings.py, and this file shares them. NPS's `Park Closure` category is
the closures half, and a road event whose `vehicle_impact` is
`all-lanes-closed` may be too; both are split in dbt. A Park Closure most
often closes a facility or a road rather than a trail (semo's two on
2026-10-03 closed visitor centres), and no alert carries geometry, so
`obstructs_trail` cannot come from the category alone (decision 7).

The coverage audit also counted `TRLSTATUS='Temporarily Closed'` on 60
features of nps_trails, which nps/trail_lines.py already lands (2026-10-01):
a closure status on the line itself, for dbt to read beside these alerts.

The park closure layers the coverage audit and the decision 53 inventory
read (YOSE_Closures_public/12, SEKI_Administrative_Closures_Public/1,
GRCAclosuresNPmapMay/0) are ArcGIS, decision 54 wave 1's; when they are
registered they become this file's CLAIMS, and this SHARES line moves into
that docstring as prose, since a file takes one form.
"""

SHARES = "warnings"
