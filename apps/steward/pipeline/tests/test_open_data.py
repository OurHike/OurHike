"""The open files: what the public can read, written as CSV and Parquet."""

from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from steward_analysis import open_data


class Answer:
    def __init__(self, status: int, body: object):
        self.status_code, self._body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise open_data.requests.HTTPError(str(self.status_code))


class Project:
    """Supabase's REST API for the three open views, from fixed rows."""

    def __init__(self, rows: dict[str, list[dict]], status: int = 200):
        self.rows, self.status, self.asked = rows, status, []

    def get(self, url, params, headers, timeout):
        view = url.rsplit("/", 1)[1]
        self.asked.append((view, params["offset"], headers["Accept-Profile"], headers["apikey"]))
        if self.status != 200:
            return Answer(self.status, {"code": "PGRST106", "message": "The schema must be one of the following: public"})
        start = params["offset"]
        return Answer(200, self.rows.get(view, [])[start : start + params["limit"]])


CLAIM = {
    "id": "c1",
    "rims_id": "4d9ce529-d198-40ee-9a11-02b0184b5270",
    "state": "verified",
    "claimer": '=HYPERLINK("https://evil.example")',
    "steps_done": ["Hide the site", "Block the way in"],
    "verified_hours": 2.5,
}
PHOTO = {"claim_id": "c1", "rims_id": CLAIM["rims_id"], "phase": "before", "point": 1, "path": "c1/p.jpg"}


def test_each_view_is_written_as_csv_and_parquet_with_a_manifest(tmp_path):
    project = Project({"open_claims": [CLAIM], "open_photos": [PHOTO], "open_weights": []})
    manifest = open_data.export("https://p.example", "anon", tmp_path, session=project)
    assert manifest["rows"] == {"claims": 1, "photos": 1, "weights": 0}
    assert {p.name for p in tmp_path.iterdir()} == {
        "claims.csv",
        "claims.parquet",
        "photos.csv",
        "photos.parquet",
        "weights.csv",
        "weights.parquet",
        "manifest.json",
    }
    photos = pd.read_csv(tmp_path / "photos.csv")
    assert photos["url"][0] == "https://p.example/storage/v1/object/public/steward-photos/c1/p.jpg"
    assert duckdb.sql(f"select steps_done from '{tmp_path / 'claims.parquet'}'").fetchone()[0] == CLAIM["steps_done"]


def test_a_name_a_spreadsheet_would_run_as_a_formula_is_written_as_text(tmp_path):
    open_data.export("https://p.example", "anon", tmp_path, session=Project({"open_claims": [CLAIM]}))
    claims = pd.read_csv(tmp_path / "claims.csv")
    assert claims["claimer"][0].startswith("'=")
    assert claims["steps_done"][0] == "Hide the site; Block the way in"


def test_it_reads_with_the_public_key_and_the_steward_schema_page_by_page(tmp_path, monkeypatch):
    monkeypatch.setattr(open_data, "PAGE", 2)
    project = Project({"open_claims": [dict(CLAIM, id=f"c{n}") for n in range(5)]})
    manifest = open_data.export("https://p.example", "the-anon-key", tmp_path, session=project)
    assert manifest["rows"]["claims"] == 5
    claim_pages = [(offset, profile, key) for view, offset, profile, key in project.asked if view == "open_claims"]
    assert claim_pages == [(0, "steward", "the-anon-key"), (2, "steward", "the-anon-key"), (4, "steward", "the-anon-key")]


def test_a_project_that_does_not_serve_the_schema_yet_writes_nothing(tmp_path):
    with pytest.raises(open_data.NotServed):
        open_data.export("https://p.example", "anon", tmp_path / "work", session=Project({}, status=406))
    assert not (tmp_path / "work").exists()


def test_with_no_project_named_it_writes_nothing_and_succeeds(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert open_data.main(["--out", str(tmp_path / "work")]) == 0
    assert "nothing written" in capsys.readouterr().out
    assert not (tmp_path / "work").exists()
