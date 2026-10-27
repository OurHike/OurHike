"""Shared test setup: no network, and invented sites to score.

Every site here sits at invented coordinates near 0°N 0°E, in the Gulf of
Guinea, so no test can carry a real campsite's location into the repository.
The fixtures are built in code rather than kept as .json or .geojson files,
which test_no_committed_data.py would rightly refuse outside its allowlist.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from steward_analysis import rules, sources

#: Feet in one degree of latitude, near enough for placing invented sites.
FEET_PER_DEG = 364_000


@pytest.fixture(autouse=True)
def no_outside_network(monkeypatch):
    """Fail any test that tries to open a real connection; the fetch tests use a fake session instead."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError(f"a test tried to reach {address!r}; tests never touch the network")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


def csi_row(n: int, *, north_ft: float = 0, east_ft: float = 0, **fields) -> dict:
    """One CSI row with every field the job asks for. Indicators default to a mid-band site, and
    CSI_Score defaults to whatever the indicators add up to, so a test only names what it is about."""
    row = {
        "OBJECTID": n,
        "RIMS_ID": f"rims-{n:04d}",
        "GlobalID": f"global-{n:04d}",
        "Location": f"Invented site {n}",
        "Region": "TEST",
        "Trail_Club": "Example Trail Club",
        "Latitude": north_ft / FEET_PER_DEG,
        "Longitude": east_ft / FEET_PER_DEG,
        "AT_Mile_2026": 100.0 + n / 10,
        "Site_Type": rules.USER_CREATED,
        "Documented": " ",
        "Inventory_Status": "Established",
        "Expansion_Potential_Indicator": 2,
        "Size_ft2": 400.0,
        "Size_Indicator": 2,
        "Proximity_Other_Site_ft": 900.0,
        "Proximity_Other_Site_Indicator": 3,
        "Proximity_Water_ft": 450.0,
        "Nearest_Water_Source": "NHDP_HR_Stream",
        "Proximity_Water_Ecological_Indicator": 3,
        "Proximity_Water_Social_Indicator": 2,
        "Proximity_AT_ft": 120.0,
        "Proximity_AT_Indicator": 2,
        "Median_Percent_Slope_Footprint": 6.0,
        "Median_Percent_Slope_Buffer": 7.0,
        "Side_Hill_Footprint_Indicator": 0,
        "Side_Hill_Buffer_Indicator": 0,
    }
    row.update(fields)
    row.setdefault("CSI_Score", rules.csi_from_indicators(row))
    assert set(sources.CSI_FIELDS) <= set(row), "csi_row must carry every field the job asks for"
    return row


def square(north_ft: float, east_ft: float, half_ft: float, **props) -> dict:
    """A square PAD-US-shaped polygon feature centred on an invented point."""
    lat, lon, half = north_ft / FEET_PER_DEG, east_ft / FEET_PER_DEG, half_ft / FEET_PER_DEG
    ring = [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props}


def point(north_ft: float, east_ft: float, **props) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [east_ft / FEET_PER_DEG, north_ft / FEET_PER_DEG]},
        "properties": props,
    }


def write_raw(
    raw_dir: Path,
    rows: list[dict],
    parking: list[dict],
    padus: list[dict],
    edited_ms: int | None = 1787239681299,
    centerline: list[dict] | None = None,
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "csi.json").write_text(json.dumps({"layer": sources.CSI_LAYER, "data_last_edit_ms": edited_ms, "rows": rows}))
    (raw_dir / "parking.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": parking}))
    (raw_dir / "padus.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": padus}))
    if centerline is not None:
        (raw_dir / "centerline.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": centerline}))
