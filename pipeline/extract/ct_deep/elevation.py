"""Per-trail `Gains` and `Losses` arrive in the blue-blazed trail layer, so this type shares trail_lines.py's resource.

Coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa, reasoned. Their units
and method are unstated, so they are @unvalidated until compared with USGS
3DEP (_shared/usgs/) over the same lines. Connecticut's lidar is CT ECO's
(UConn CLEAR with DEEP), not DEEP's.
"""

SHARES = "trail_lines"
