"""DCNR's trail descriptions arrive in the trail layer, so this type shares trail_lines.py's resource.

`DESCRIPTIO` is non-empty on 681 of 684 rows and `DIFFICULTY` is coded 0-3
(coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa). They are trail
descriptions ("Most hikers will need 5 to 6 days…"), not routed itineraries,
and nothing reads them today. The per-forest hiking pages and
trails.dcnr.pa.gov's trail views are not landed.
"""

SHARES = "trail_lines"
