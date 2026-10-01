"""NYC Parks' trails across the five boroughs, Socrata `vjbm-hsyr`.

7,059 rows on 2026-10-01, newest `:updated_at` 2026-09-16. The coverage audit
read all 198 NYC Parks catalogue entries and found no other line dataset
(batch b5_nyc_nj_ct_ma_pa); `Parks Trails Map` (`iidj-gxys`) is a map view of
this one. NYC DOT's greenways and Centerline paths draw some of the same tread,
measured at 23.6% overlap within 25 m (#1459 — Two New York City agencies draw
the same tread and the map draws both lines, because nothing dedupes geometry
across sources); that is dbt's to reconcile, after both have landed.
"""

from extract._kinds import socrata_dataset

CLAIMS = ("nyc_parks_trails",)
RESOURCES = [socrata_dataset(key) for key in CLAIMS]
