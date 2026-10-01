"""The POI identity ledger: reference/poi_identity.json, one row per POI ever published, as `raw_ourhike__poi_identity`.

8,563 POIs on 2026-10-01, 5,412 of them retired, keyed by `poi_id`: "never
re-mint, never reuse, never delete" (reconcile_poi_identity.py). The ledger
decides published POI ids, which the points_of_interest mart carries, and
which ids the podcast episodes and highlights may tag (lib/podcasts.py's
`_pois`). It is a reviewed file, so its bytes are its upstream and its row
count is its own proof. A regeneration run proposes; a person reviews it in.

`first_seen` and `retired` hold a release, which reads as a date today, and
`superseded_by` is on no row yet (reconcile_poi_identity.py writes it on a
tombstone). All three are hinted as text: a date-shaped string would
otherwise be typed by its first value, and an absent field gets no column.
"""

from extract._kinds import reviewed_file

TYPE = "points_of_interest"
CLAIMS = ("reference/poi_identity.json",)
RESOURCES = [
    reviewed_file(
        "reference/poi_identity.json",
        rows_key="pois",
        map_key="poi_id",
        hints={"first_seen": "text", "retired": "text", "superseded_by": "text"},
    )
]
