"""NYC Parks' properties, Socrata `enfh-gkve`: the park boundaries.

2,061 rows on 2026-10-01, newest `:updated_at` 2026-09-16. Not landed: `NYC
Parks Forever Wild` (`48va-85tp`, 139 natural-area polygons), the named areas
a hiker searches for ("Staten Island Greenbelt"), coverage audit batch
b5_nyc_nj_ct_ma_pa.
"""

from extract._kinds import socrata_dataset

CLAIMS = ("nyc_park_polygons",)
RESOURCES = [socrata_dataset(key) for key in CLAIMS]
