"""Tests for app.core.hike_direction.derive_direction - the pure function
behind ../../../features/HIKER_SAFETY.md section 5's wrong-way alert, and a
model-level check that direction is never itself persisted.
"""

from app.core.hike_direction import derive_direction
from app.models.hike import Hike


def test_hike_direction_is_nobo_when_start_mile_marker_is_less_than_end():
    assert derive_direction(0.0, 2189.0) == "NOBO"


def test_hike_direction_is_sobo_when_start_mile_marker_is_greater_than_end():
    assert derive_direction(2189.0, 0.0) == "SOBO"


def test_hike_direction_is_derived_not_stored():
    """HIKER_SAFETY.md: "no new state needed... just reading what Segments
    already has" - direction must be computed from overall_start_reference/
    overall_end_reference, never its own column on the Hike model/table.
    """
    column_names = {column.name for column in Hike.__table__.columns}

    assert "direction" not in column_names
