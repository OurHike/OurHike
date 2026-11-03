"""Where a waypoint sits on the A.T., as the published waypoint export says.

`GET /disputes` gives one note from a covering maintainer the weight of the
count, and "covering" has to be about where the waypoint IS. It used to be
about the mile written on the note, which is whatever the author's client
sent, so a maintainer of three miles could settle a dispute a thousand miles
away (#1917 - A maintainer's note settles a water dispute anywhere on the
trail, because the covering check reads the mile the note's author typed, not
where the waypoint is).

Nothing writes this over HTTP. `load_waypoint_miles.py` loads it from the
published GeoJSON, the same reviewed-file posture as `load_assignments.py`.
A waypoint with no row is unplaced: a covering maintainer's `not_found`
still marks it from the mile they typed, and no one maintainer's confirmation
clears a dispute on it (app/routers/field_notes.py says why each way).
"""

from sqlalchemy import Column, DateTime, Float, String

from app.db.base import Base


class WaypointMile(Base):
    __tablename__ = "waypoint_miles"

    # The published id, `<source>:<feature id>`, the same string a field note
    # carries as its `poi_id`.
    poi_id = Column(String, primary_key=True)

    # NOBO miles from Springer, as pipeline/export_poi.py's `attach_miles`
    # projects it. The export withholds a mile from a waypoint on another
    # organization's trail (`mark_off_trail_records`), and such a waypoint
    # gets no row here.
    mile = Column(Float, nullable=False)

    # When the loader last ran over this row. Every run stamps every row it
    # keeps, so `max(loaded_at)` is when the table last matched a release.
    loaded_at = Column(DateTime, nullable=False)
