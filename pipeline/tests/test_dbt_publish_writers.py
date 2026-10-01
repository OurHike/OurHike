"""The pub_ writers stay what pipeline/ELT.md, "Publish (reverse ETL)", says they are.

A writer is the one kind of model that leaves the warehouse: it writes a file.
So the rules that keep that safe are held here, from the files themselves:
- every model in models/publish/ is a `pub_` model, writing one bare file name
  through the phone_file materialisation, which joins it to processed_dir
  and refuses a path (a nested name, or one that climbs out with `..`);
- nothing else in the project writes a file: no other model, macro or hook
  carries a `COPY ... TO`;
- every writer is the dependency of exactly one exposure, whose meta names the
  phone's key, the format and the cadence (decision 28), so a writer nobody
  reads cannot be added, and every file a phone reads has a page in the docs.
"""

import re
from pathlib import Path

import yaml

DBT = Path(__file__).parent.parent / "dbt"
PUBLISH = DBT / "models" / "publish"
LOCATION = re.compile(r"location\s*=\s*'([^']*)'")
COPY_TO = re.compile(r"\bcopy\b[^;]*?\)\s*to\s*'", re.IGNORECASE | re.DOTALL)


def _writers() -> dict[str, str]:
    return {path.stem: path.read_text() for path in sorted(PUBLISH.glob("*.sql"))}


def _exposures() -> list[dict]:
    found = []
    for path in sorted(PUBLISH.glob("*.yml")):
        found += yaml.safe_load(path.read_text()).get("exposures") or []
    return found


def test_the_publish_folder_holds_only_pub_writers_with_a_bare_file_name():
    writers = _writers()
    assert writers, "the podcasts writer, at least"
    for name, sql in writers.items():
        assert name.startswith("pub_"), name
        (location,) = LOCATION.findall(sql)
        assert re.fullmatch(r"[a-z0-9_]+\.(json|geojson|pmtiles)", location), f"{name}: {location!r}"


def test_the_folder_is_materialised_as_phone_file():
    project = yaml.safe_load((DBT / "dbt_project.yml").read_text())
    assert project["models"]["ourhike"]["publish"]["+materialized"] == "phone_file"
    for name, sql in _writers().items():
        assert "materialized" not in sql, f"{name} sets its own materialisation"


def test_only_phone_file_copies_to_a_file():
    writers = [
        path
        for folder in ("models", "macros", "tests")
        for path in (DBT / folder).rglob("*")
        if path.suffix in (".sql", ".yml") and COPY_TO.search(path.read_text())
    ]
    assert writers == [DBT / "macros" / "materializations" / "phone_file.sql"]


def test_every_writer_is_one_exposures_and_says_where_it_goes():
    exposures = _exposures()
    for name in _writers():
        reading = [exposure for exposure in exposures if f"ref('{name}')" in exposure["depends_on"]]
        assert len(reading) == 1, f"{name} is read by {len(reading)} exposures"
        meta = reading[0]["config"]["meta"]
        assert meta["r2_keys"] and meta["format"] and meta["cadence"] in ("hourly", "daily", "weekly", "monthly"), name
