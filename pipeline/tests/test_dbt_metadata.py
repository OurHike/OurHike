"""Every dbt model says what its data is, and every table a phone reads keeps its shape.

Read from the YAML and SQL on disk, generated models included (tests/conftest.py
writes them before the suite starts), so no warehouse is needed:

- every model and snapshot has a description;
- every column of every mart and every `pub_` writer has a description and a
  `data_type`;
- every mart and every `pub_` writer enforces its contract, so a build fails
  when its SQL stops matching the declared columns;
- every mart is versioned (`latest_version` and a `versions:` list whose v1 is
  the mart's own file), so a removed, renamed or retyped column ships as a new
  version beside the old one. check_contract_versions.py compares each
  version with the base branch's manifest in CI; this file only holds that
  every mart is in a shape that check can hold;
- no description and no comment in the project's SQL or YAML cites a numbered
  decision, ledger row or poll question. A note says what the code does and
  why; the decision log is git history.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

DBT = Path(__file__).resolve().parent.parent / "dbt"
MODELS = DBT / "models"
MARTS = MODELS / "marts"

#: A numbered decision, a porting-ledger row (TL05, PO38 ...), a poll question (Q25) or a work wave. SQLFluff's rule
#: codes (AL01, LT05, RF04, AM07, ST06, CP01) are not among the ledger prefixes, so a lint note keeps its code. A date
#: ("decision 2026-09-09"), a data id ("HS84-1") and a quartile ("Q3 + 1.5 IQR") are not references.
NUMBERED_REFERENCE = re.compile(
    r"\bdecisions?\s+\d+(?![\d-])|\bQ\d{2,}\b|\banswer to Q\d+|\bwave\s+\d+"
    r"|\b(?:CH|CL|EL|HS|PC|PL|PO|SH|SR|TL|TN|WN)\d{2}\b(?!-\d)",
    re.IGNORECASE,
)
#: Text that is a pattern the SQL runs, not prose: the publication rule matches a registry row's licence text against
#: the rulings it names, so its seeds and their unit-test rows carry those names as data.
DATA_PATTERN = re.compile(r"named_by|answered_by|covers_own_words|\\b|\\s")


def _yaml_files() -> list[Path]:
    return sorted(
        path for folder in ("models", "seeds", "snapshots", "macros", "tests") for path in (DBT / folder).rglob("*.yml")
    )


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _docs_blocks() -> dict[str, str]:
    blocks = {}
    for path in DBT.rglob("*.md"):
        if "dbt_packages" in path.parts or "target" in path.parts:
            continue
        for name, body in re.findall(r"\{%\s*docs\s+(\w+)\s*%\}(.*?)\{%\s*enddocs\s*%\}", path.read_text(encoding="utf-8"), re.S):
            blocks[name] = body
    return blocks


DOCS = _docs_blocks()


def _text(description: object) -> str:
    """A description with its doc() blocks read in, so `{{ doc('row_changed_at') }}` counts as that block's words."""
    text = str(description or "")
    return re.sub(r"\{\{\s*doc\(\s*['\"](\w+)['\"]\s*\)\s*\}\}", lambda match: DOCS.get(match.group(1), ""), text).strip()


def _model_entries() -> dict[str, tuple[Path, dict]]:
    """Every model entry in the project's YAML, by the SQL file it describes (a version's `defined_in` included)."""
    entries: dict[str, tuple[Path, dict]] = {}
    for path in _yaml_files():
        for model in _load(path).get("models") or []:
            entries[model["name"]] = (path, model)
            for version in model.get("versions") or []:
                entries[version.get("defined_in") or f"{model['name']}_v{version['v']}"] = (path, model)
    return entries


ENTRIES = _model_entries()
MODEL_FILES = {path.stem: path for path in MODELS.rglob("*.sql")}


def _columns(entry: dict) -> list[dict]:
    return [column for column in entry.get("columns") or [] if isinstance(column, dict) and "name" in column]


def _config(entry: dict) -> dict:
    return entry.get("config") or {}


def _phone_models() -> dict[str, dict]:
    """Every mart and every pub_ writer, by name, with its YAML entry."""
    found = {}
    for name, path in MODEL_FILES.items():
        is_mart = MARTS in path.parents
        if not (is_mart or name.startswith("pub_")):
            continue
        assert name in ENTRIES, f"{path.relative_to(DBT)} has no YAML entry"
        found[ENTRIES[name][1]["name"]] = ENTRIES[name][1]
    return found


PHONE_MODELS = _phone_models()
MART_NAMES = sorted({ENTRIES[path.stem][1]["name"] for path in MODEL_FILES.values() if MARTS in path.parents})


def test_every_model_has_a_yaml_entry_and_a_description():
    missing = sorted(name for name in MODEL_FILES if name not in ENTRIES)
    assert not missing, f"models with no YAML entry: {missing}"
    blank = sorted(name for name in MODEL_FILES if not _text(ENTRIES[name][1].get("description")))
    assert not blank, f"models with no description: {blank}"


def test_every_snapshot_and_seed_has_a_description():
    blank = []
    for path in _yaml_files():
        document = _load(path)
        for kind in ("snapshots", "seeds"):
            blank += [f"{kind[:-1]} {entry['name']}" for entry in document.get(kind) or [] if not _text(entry.get("description"))]
    assert not blank, blank


@pytest.mark.parametrize("name", sorted(PHONE_MODELS))
def test_every_column_of_a_mart_or_writer_is_described_and_typed(name):
    entry = PHONE_MODELS[name]
    columns = _columns(entry)
    assert columns, f"{name} declares no columns"
    assert not [c["name"] for c in columns if not _text(c.get("description"))], f"{name}: columns with no description"
    assert not [c["name"] for c in columns if not c.get("data_type")], f"{name}: columns with no data_type"


@pytest.mark.parametrize("name", sorted(PHONE_MODELS))
def test_every_mart_and_writer_enforces_its_contract(name):
    contract = _config(PHONE_MODELS[name]).get("contract") or PHONE_MODELS[name].get("contract") or {}
    assert contract.get("enforced") is True, f"{name}: set config: contract: {{enforced: true}}"


@pytest.mark.parametrize("name", MART_NAMES)
def test_every_mart_is_versioned_with_v1_as_its_own_file(name):
    entry = PHONE_MODELS[name]
    versions = {version["v"]: version for version in entry.get("versions") or []}
    assert 1 in versions, f"{name}: declare versions: [{{v: 1, defined_in: {name}}}]"
    assert versions[1].get("defined_in") == name, f"{name}: v1 must be built from {name}.sql, the file phones read today"
    assert entry.get("latest_version") in versions, f"{name}: latest_version must name one of its versions"


def test_the_marts_are_the_eleven():
    assert MART_NAMES == sorted(
        [
            "challenges",
            "closures",
            "elevation",
            "places",
            "podcasts",
            "points_of_interest",
            "sources",
            "suggested_hikes",
            "trail_lines",
            "trail_network",
            "warnings",
        ]
    )


def _descriptions(node: object, where: str):
    """Every `description` string anywhere in a YAML document, with where it sits."""
    if isinstance(node, dict):
        for key, value in node.items():
            label = f"{where}.{node.get('name', key)}" if key != "description" else where
            if key == "description" and isinstance(value, str):
                yield where, value
            else:
                yield from _descriptions(value, label)
    elif isinstance(node, list):
        for item in node:
            yield from _descriptions(item, where)


def test_no_description_cites_a_numbered_decision():
    found = []
    for path in _yaml_files():
        for where, text in _descriptions(_load(path), str(path.relative_to(DBT))):
            found += [f"{where}: {match.group(0)}" for match in NUMBERED_REFERENCE.finditer(text)]
    for name, body in DOCS.items():
        found += [f"docs block {name}: {match.group(0)}" for match in NUMBERED_REFERENCE.finditer(body)]
    assert not found, "\n".join(found)


def _comments(path: Path) -> list[tuple[int, str]]:
    """The comment lines of a SQL or YAML file: `--` and `{# #}` in SQL, `#` in YAML."""
    text = path.read_text(encoding="utf-8")
    found = []
    if path.suffix == ".sql":
        for match in re.finditer(r"\{#.*?#\}|/\*.*?\*/|--[^\n]*", text, re.S):
            start = text.count("\n", 0, match.start()) + 1
            found += [(start + offset, line) for offset, line in enumerate(match.group(0).split("\n"))]
    else:
        for number, line in enumerate(text.split("\n"), 1):
            hashed = re.search(r"(?:^|\s)#(?!\})(.*)$", line)
            if hashed and not re.match(r"\s*['\"]", line.split("#", 1)[0][-1:] or " "):
                found.append((number, hashed.group(1)))
    return found


def _project_files(suffix: str) -> list[Path]:
    return sorted(
        path for folder in ("models", "macros", "tests", "snapshots", "seeds") for path in (DBT / folder).rglob(f"*{suffix}")
    ) + ([DBT / "dbt_project.yml"] if suffix == ".yml" else [])


@pytest.mark.parametrize("suffix", [".sql", ".yml"])
def test_no_comment_cites_a_numbered_decision(suffix):
    found = []
    for path in _project_files(suffix):
        for number, line in _comments(path):
            if DATA_PATTERN.search(line):
                continue
            found += [f"{path.relative_to(DBT)}:{number}: {match.group(0)}" for match in NUMBERED_REFERENCE.finditer(line)]
    assert not found, "\n".join(found)
