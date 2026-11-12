"""The structure inventory's CSV and GeoJSON exports.

#1993 — The inventory exports as CSV and GeoJSON for the club's GIS,
admin-only, with every estimate labelled as one.

Who may download is test_org_permission_matrix.py's job. This file holds
what is in the files: one row per reviewed structure carrying its latest
accepted observation, and rule 3 - a size recorded as a bucket never appears
as a number in either export.

Rows are written straight to the tables because the review queue that sets
`accepted` (#1989 — The club's chain reviews: accept, send back, merge, not
ours) is not built yet.
"""

import csv
import io
import json
import uuid
from datetime import datetime

import pytest

from app.models.club import OrgState
from app.models.inventory import (
    Condition,
    InventoryObservation,
    InventoryStructure,
    Repair,
    ReviewState,
    SizeMethod,
    StructureKind,
    StructureStatus,
)
from tests.factories import make_admin, make_org, make_profile
from tests.tokens import auth_headers


@pytest.fixture
def club(db_session):
    org = make_org(db_session, state=OrgState.claimed)
    admin = make_profile(db_session)
    make_admin(db_session, org, admin)
    db_session.commit()
    return {"org": org, "admin": admin, "volunteer": make_profile(db_session)}


def _structure(db_session, club, **fields):
    row = InventoryStructure(
        id=str(uuid.uuid4()),
        club_id=club["org"].id,
        kind=fields.pop("kind", StructureKind.bridge),
        lat=fields.pop("lat", 41.4321),
        lon=fields.pop("lon", -73.8765),
        created_by=club["volunteer"].id,
        **fields,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _observation(db_session, club, structure, **fields):
    row = InventoryObservation(
        id=str(uuid.uuid4()),
        structure_id=structure.id,
        club_id=club["org"].id,
        volunteer_id=club["volunteer"].id,
        captured_at=fields.pop("captured_at", datetime(2026, 11, 2, 15, 14)),
        lat=structure.lat,
        lon=structure.lon,
        accuracy_m=4.3,
        readings_count=1,
        readings_seconds=1,
        readings=[{"lat": structure.lat, "lon": structure.lon, "acc": 4.3, "t": 0}],
        condition=fields.pop("condition", Condition.poor),
        repair=fields.pop("repair", Repair.major),
        review_state=fields.pop("review_state", ReviewState.accepted),
        **fields,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _csv_rows(client, club):
    response = client.get(f"/clubs/{club['org'].slug}/inventory/export.csv", headers=auth_headers(club["admin"].id))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("﻿")
    return list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))


def _features(client, club):
    response = client.get(f"/clubs/{club['org'].slug}/inventory/export.geojson", headers=auth_headers(club["admin"].id))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/geo+json")
    body = json.loads(response.text)
    assert body["type"] == "FeatureCollection"
    return body["features"]


def test_a_bucket_size_is_never_a_number_in_either_export(client, db_session, club):
    """Rule 3. The row is built with a number beside its bucket - something
    `ObservationCreate` refuses at upload - so the test proves the export does
    not lean on that refusal."""
    structure = _structure(db_session, club)
    _observation(
        db_session,
        club,
        structure,
        size_method=SizeMethod.bucket,
        size_bucket="10_to_25_ft",
        size_measured=18.5,
        size_unit="ft",
    )

    [row] = _csv_rows(client, club)
    assert row["size_method"] == "bucket"
    assert row["size_bucket"] == "10_to_25_ft"
    assert row["size_measured"] == ""
    assert row["size_unit"] == ""
    assert "18.5" not in ",".join(row.values())

    [feature] = _features(client, club)
    props = feature["properties"]
    assert props["size_method"] == "bucket"
    assert props["size_bucket"] == "10_to_25_ft"
    assert props["size_measured"] is None
    assert props["size_unit"] is None


def test_a_taped_size_exports_as_its_number_and_unit(client, db_session, club):
    structure = _structure(db_session, club)
    _observation(db_session, club, structure, size_method=SizeMethod.tape, size_measured=18.5, size_unit="ft")

    [row] = _csv_rows(client, club)
    assert (row["size_method"], row["size_bucket"], row["size_measured"], row["size_unit"]) == ("tape", "", "18.5", "ft")

    [feature] = _features(client, club)
    assert feature["properties"]["size_measured"] == 18.5
    assert feature["properties"]["size_unit"] == "ft"


def test_a_record_with_no_size_says_no_method_rather_than_a_zero(client, db_session, club):
    _observation(db_session, club, _structure(db_session, club))

    [row] = _csv_rows(client, club)
    assert row["size_method"] == row["size_measured"] == ""
    [feature] = _features(client, club)
    assert "size_method" in feature["properties"]
    assert feature["properties"]["size_method"] is None


def test_each_structure_carries_its_latest_accepted_observation_and_nothing_unreviewed(client, db_session, club):
    """A newer record still waiting for review does not replace the accepted
    one, and a structure nobody has accepted yet is not in the file."""
    seen = _structure(db_session, club, code="AT-NY-BR-001")
    _observation(db_session, club, seen, captured_at=datetime(2026, 6, 1), condition=Condition.good)
    _observation(db_session, club, seen, captured_at=datetime(2026, 10, 1), condition=Condition.unsafe)
    _observation(
        db_session,
        club,
        seen,
        captured_at=datetime(2026, 11, 1),
        condition=Condition.fair,
        review_state=ReviewState.submitted,
    )
    waiting = _structure(db_session, club)
    _observation(db_session, club, waiting, review_state=ReviewState.submitted)

    rows = _csv_rows(client, club)
    assert [(row["code"], row["condition"], row["observed_at"]) for row in rows] == [
        ("AT-NY-BR-001", "unsafe", "2026-10-01T00:00:00Z")
    ]
    assert [feature["id"] for feature in _features(client, club)] == [seen.id]


def test_a_merged_structure_is_left_out_and_a_removed_one_says_so(client, db_session, club):
    kept = _structure(db_session, club, code="AT-NY-BR-001")
    _observation(db_session, club, kept)
    gone = _structure(db_session, club, code="AT-NY-BR-002", status=StructureStatus.removed)
    _observation(db_session, club, gone)
    joined = _structure(db_session, club, code="AT-NY-BR-003", status=StructureStatus.merged, merged_into_id=kept.id)
    _observation(db_session, club, joined)

    assert [(row["code"], row["status"]) for row in _csv_rows(client, club)] == [
        ("AT-NY-BR-001", "active"),
        ("AT-NY-BR-002", "removed"),
    ]


def test_another_clubs_structures_are_not_in_this_clubs_export(client, db_session, club):
    other = {**club, "org": make_org(db_session, slug="another-club", state=OrgState.claimed)}
    _observation(db_session, other, _structure(db_session, other))

    assert _csv_rows(client, club) == []
    assert _features(client, club) == []


def test_the_geojson_point_is_lon_then_lat(client, db_session, club):
    _observation(db_session, club, _structure(db_session, club, lat=41.25, lon=-74.5))

    [feature] = _features(client, club)
    assert feature["geometry"] == {"type": "Point", "coordinates": [-74.5, 41.25]}


def test_a_typed_formula_is_text_and_a_western_longitude_is_still_a_number(client, db_session, club):
    """`spreadsheet_safe` quotes a leading `-`, which is right for a note and
    wrong for -73.88: the club's GIS has to read the column as numbers."""
    structure = _structure(db_session, club, subkind='=HYPERLINK("https://example.org","x")')
    _observation(db_session, club, structure, notes="-1 board, +2 loose")

    [row] = _csv_rows(client, club)
    assert row["subkind"].startswith("'=")
    assert row["notes"] == "'-1 board, +2 loose"
    assert row["lon"] == "-73.8765"
