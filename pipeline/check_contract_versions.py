"""A pull request's contracted dbt models, version by version, against main's (decision 44).

    python check_contract_versions.py --head dbt/target/manifest.json --base <main>/pipeline/dbt/target/manifest.json
    python check_contract_versions.py --head dbt/target/manifest.json

pipeline/ELT.md, "Versions and channels (decision 44), as stage 4 builds them":
a phone file's shape is a dbt model version. v1 is today's shape. A removed,
renamed or retyped column is a breaking change, and it ships as a new version
written beside the old one until the old one's `deprecation_date`. An added
column is not breaking, because a phone ignores fields it does not know.

WHY THIS FILE EXISTS. dbt Core refuses a breaking change between states
(`ContractBreakingChangeError`); dbt 2.0.6 does not. Measured 2026-10-02 for
decision 44 in a throwaway project: under `-s state:modified --state`,
dropping a column from a contracted v1 and retyping a contracted v2 table's
key in both its SQL and its YAML each built green. So the refusal is this
script's, run by pipeline-tests.yml's `dbt` job on every pull request.

AGAINST THE BASE (`--base`), each contracted model version there is looked up
in the head by package, name and version, and the head FAILS on:

  1. a column the base has and the head does not (removed or renamed);
  2. a column whose type changed (DuckDB's own spellings of one type, such as
     `text` for `varchar`, are the same type);
  3. a version the head no longer has, unless the base gave it a
     `deprecation_date` that has passed;
  4. a contract the head no longer enforces, which would let 1 and 2 through
     unseen.

"Unless the change arrives as a new version" is how those read, not a fifth
rule: a version the base does not have is new and compared with nothing, so a
change made in a v2 beside an untouched v1 passes. A model gaining `versions:`
for the first time is the same model: its v1 is compared with the base's
unversioned one. A removed `not_null` or other constraint is reported as a
warning, never a failure: dbt Core counts it as breaking, and decision 44 did
not name it.

IN THE HEAD ALONE, every time, for the pub_ writers (materialised
`phone_file`), because "its writer names the version in the R2 key":

  5. a writer that reads a versioned model pins it, `ref('podcasts', v=1)`,
     so a new latest version can never move a published file underneath it;
  6. a writer reads one version, not two;
  7. each key it writes (keys_by_writer pairs an exposure's keys with its
     writers) carries that version's segment, and v1's keys carry none: `v2/<file>` for a release-scoped file (publish.py puts
     it under `releases/<id>/`), `conditions/v2/<file>` and
     `podcasts/v2/<file>` for the root-scoped ones.

Exit 1 on any failure, so the CI step fails on one; 2 on a manifest that
cannot be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: The root-scoped prefixes whose v2 sits one segment in (pipeline/ELT.md,
#: "Versions and channels": `conditions/v2/<file>` or `podcasts/v2/<file>`).
#: Every other key is release-scoped and its v2 is `v2/<file>`.
ROOT_SCOPED_PREFIXES = ("conditions/", "podcasts/")

PHONE_FILE_MATERIALIZATION = "phone_file"

# One DuckDB type, more than one spelling (duckdb.org, "Data Types": the
# aliases column of each type). Whole types only: a struct's field names are
# left alone, so a field that happens to be called `text` is not respelled.
_TYPE_ALIASES = {
    "text": "varchar",
    "string": "varchar",
    "char": "varchar",
    "bpchar": "varchar",
    "nvarchar": "varchar",
    "int": "integer",
    "int4": "integer",
    "signed": "integer",
    "int8": "bigint",
    "long": "bigint",
    "int2": "smallint",
    "short": "smallint",
    "int1": "tinyint",
    "float8": "double",
    "float4": "real",
    "float": "real",
    "bool": "boolean",
    "logical": "boolean",
    "timestamp with time zone": "timestamptz",
    "datetime": "timestamp",
    "timestamp without time zone": "timestamp",
    "bytea": "blob",
    "binary": "blob",
    "varbinary": "blob",
}

_VERSION_SEGMENT = re.compile(r"^v(\d+)$")


def normalize_type(raw: object) -> str | None:
    """A contract's `data_type` as one spelling per DuckDB type, or None for
    none. Case, spacing around brackets and commas, a varchar's ignored length
    and the aliases above all collapse; anything else stays as written, so an
    unfamiliar spelling can only ever fail a comparison it should have passed
    (the cheap direction), never pass one it should have failed."""
    if raw is None:
        return None
    text = " ".join(str(raw).strip().lower().split())
    if not text:
        return None
    text = re.sub(r"\s*([(),\[\]])\s*", r"\1", text)
    base, suffix = re.match(r"^(.*?)((?:\[\d*\])*)$", text).groups()
    base = re.sub(r"^(varchar|char|bpchar|nvarchar)\(\d+\)$", r"\1", base)
    return _TYPE_ALIASES.get(base, base) + suffix


def version_in_key(key: str) -> int | None:
    """The schema version a key names, or None for v1's keys, which name none.

    The version is the first segment of a release-scoped key and the second of
    a root-scoped one; a `v<n>` anywhere else is part of a file's own name."""
    segments = key.split("/")
    index = 1 if any(key.startswith(prefix) for prefix in ROOT_SCOPED_PREFIXES) else 0
    if len(segments) <= index + 1:
        return None
    match = _VERSION_SEGMENT.match(segments[index])
    return int(match.group(1)) if match else None


def keys_by_writer(exposure: dict, nodes: dict) -> dict[str, list[str]]:
    """Which of an exposure's R2 keys each of its phone_file writers writes.

    One writer writes every key its exposure names. Several writers each write
    the key whose last segment is their `location`, the bare file name
    phone_file writes: the eight poi_<type>.geojson files share one exposure,
    poi_by_type_geojson, and pub_poi_shelter's location is
    poi_shelter.geojson. An exposure where that pairing does not give every
    key one writer and every writer a key is refused (ValueError), because a
    key nobody can be shown to write would publish nothing or the wrong file.
    An exposure with no writer, documenting a file Python writes, gives {}."""
    meta = (exposure.get("config") or {}).get("meta") or exposure.get("meta") or {}
    keys = list(meta.get("r2_keys") or [])
    writers = [
        node_id
        for node_id in (exposure.get("depends_on") or {}).get("nodes") or []
        if ((nodes.get(node_id) or {}).get("config") or {}).get("materialized") == PHONE_FILE_MATERIALIZATION
    ]
    if not keys or not writers:
        return {}
    if len(writers) == 1:
        return {writers[0]: keys}
    by_location: dict[str, str] = {}
    for writer in writers:
        location = (nodes[writer].get("config") or {}).get("location")
        if location in by_location:
            raise ValueError(f"{by_location[location]} and {writer} both write {location}")
        by_location[location] = writer
    paired: dict[str, list[str]] = {writer: [] for writer in writers}
    for key in keys:
        writer = by_location.get(key.rsplit("/", 1)[-1])
        if writer is None:
            raise ValueError(f"{key} is not the file of any of its exposure's {len(writers)} writers")
        paired[writer].append(key)
    unpaired = sorted(writer for writer, named in paired.items() if not named)
    if unpaired:
        raise ValueError(f"{', '.join(unpaired)} write no key their exposure names")
    return paired


def key_for_version(v1_key: str, version: int) -> str:
    """Where version `version` of the file at `v1_key` is published."""
    if version <= 1:
        return v1_key
    for prefix in ROOT_SCOPED_PREFIXES:
        if v1_key.startswith(prefix):
            return f"{prefix}v{version}/{v1_key[len(prefix) :]}"
    return f"v{version}/{v1_key}"


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    compared: int = 0
    new: int = 0

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def _enforced(node: dict) -> bool:
    contract = (node.get("config") or {}).get("contract") or node.get("contract") or {}
    return bool(contract.get("enforced"))


def _version(node: dict) -> str | None:
    version = node.get("version")
    return None if version is None else str(version)


def _label(identity: tuple[str, str, str | None]) -> str:
    package, name, version = identity
    return f"{package}.{name}" + (f" v{version}" if version is not None else "")


def contracted_versions(manifest: dict) -> dict[tuple[str, str, str | None], dict]:
    """Every model with an enforced contract, by (package, name, version)."""
    return {
        (node.get("package_name"), node.get("name"), _version(node)): node
        for node in (manifest.get("nodes") or {}).values()
        if node.get("resource_type") == "model" and _enforced(node)
    }


def _models(manifest: dict) -> dict[tuple[str, str, str | None], dict]:
    return {
        (node.get("package_name"), node.get("name"), _version(node)): node
        for node in (manifest.get("nodes") or {}).values()
        if node.get("resource_type") == "model"
    }


def _deprecation(node: dict) -> datetime | None:
    raw = node.get("deprecation_date")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _counterpart(identity, head_models: dict) -> dict | None:
    """The head's model for a base model, by name and version.

    A model that gained `versions:` keeps its consumers through v1, the
    version decision 44 makes today's shape, so the base's unversioned model
    is the head's v1; and back again, for a model whose versions were folded
    away."""
    if identity in head_models:
        return head_models[identity]
    package, name, version = identity
    if version is None:
        return head_models.get((package, name, "1"))
    if version == "1":
        return head_models.get((package, name, None))
    return None


def compare(base: dict, head: dict, today: datetime, report: Report) -> None:
    """Rules 1-4: the head against each contracted model version in the base."""
    head_models = _models(head)
    matched = set()
    for identity, base_node in sorted(contracted_versions(base).items(), key=lambda item: _label(item[0])):
        label = _label(identity)
        head_node = _counterpart(identity, head_models)
        if head_node is None:
            deprecated = _deprecation(base_node)
            if deprecated is None:
                report.fail(f"{label}: the version is gone, and the base gave it no deprecation_date")
            elif today < deprecated:
                report.fail(f"{label}: the version is gone before its deprecation_date, {deprecated.date().isoformat()}")
            continue
        matched.add((head_node.get("package_name"), head_node.get("name"), _version(head_node)))
        report.compared += 1
        if not _enforced(head_node):
            report.fail(f"{label}: its contract is no longer enforced")
            continue
        head_columns = head_node.get("columns") or {}
        for name, column in (base_node.get("columns") or {}).items():
            if name not in head_columns:
                report.fail(f"{label}: column `{name}` is removed (or renamed); ship the change as a new version")
                continue
            before = normalize_type(column.get("data_type"))
            after = normalize_type(head_columns[name].get("data_type"))
            if before is not None and after != before:
                report.fail(f"{label}: column `{name}` changed type, {before} -> {after}; ship the change as a new version")
            kept = {(c or {}).get("type") for c in head_columns[name].get("constraints") or []}
            for constraint in column.get("constraints") or []:
                kind = (constraint or {}).get("type")
                if kind and kind not in kept:
                    report.warn(f"{label}: column `{name}` lost its {kind} constraint (dbt Core counts that as breaking)")
    report.new = sum(1 for identity in contracted_versions(head) if identity not in matched)


def check_writers(head: dict, report: Report) -> None:
    """Rules 5-7: each pub_ writer pins the version it reads, reads one, and
    names it in its keys."""
    nodes = head.get("nodes") or {}
    versioned_names = {
        node.get("name") for node in nodes.values() if node.get("resource_type") == "model" and _version(node) is not None
    }
    writer_version: dict[str, int] = {}
    for node_id, node in sorted(nodes.items()):
        if ((node.get("config") or {}).get("materialized")) != PHONE_FILE_MATERIALIZATION:
            continue
        for ref in node.get("refs") or []:
            if ref.get("name") in versioned_names and ref.get("version") is None:
                report.fail(
                    f"{node_id}: reads `{ref.get('name')}` without a version; pin it, "
                    f"ref('{ref.get('name')}', v=1), so a new latest version cannot move this file"
                )
        read = sorted(
            {_version(nodes[parent]) for parent in (node.get("depends_on") or {}).get("nodes") or [] if parent in nodes} - {None}
        )
        if len(read) > 1:
            report.fail(f"{node_id}: reads versions {', '.join(read)} at once; a phone file is one version")
            continue
        writer_version[node_id] = int(read[0]) if read else 1
    for exposure_id, exposure in sorted((head.get("exposures") or {}).items()):
        try:
            paired = keys_by_writer(exposure, nodes)
        except ValueError as exc:
            report.fail(f"{exposure_id}: {exc}")
            continue
        for writer, keys in paired.items():
            if writer not in writer_version:
                continue
            version = writer_version[writer]
            expected = None if version <= 1 else version
            for key in keys:
                named = version_in_key(key)
                if named != expected:
                    where = f"v{named}" if named else "no version"
                    rule = "carry no version segment" if expected is None else f"carry v{version} where ELT.md puts it"
                    report.fail(f"{exposure_id}: {key} names {where}, and {writer} writes v{version}, whose keys {rule}")


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"{path} cannot be read as a dbt manifest: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--head", type=Path, required=True, help="the pull request's manifest.json")
    parser.add_argument("--base", type=Path, help="main's manifest.json; without it only the head's own rules run")
    parser.add_argument("--today", help="YYYY-MM-DD to read deprecation dates against (default: now, UTC)")
    args = parser.parse_args(argv)

    today = datetime.fromisoformat(args.today).replace(tzinfo=timezone.utc) if args.today else datetime.now(timezone.utc)
    for path in (args.head, args.base):
        if path is not None and not path.exists():
            print(f"{path} does not exist.", file=sys.stderr)
            return 2
    head = _load(args.head)
    report = Report()
    if args.base is not None:
        compare(_load(args.base), head, today, report)
    check_writers(head, report)

    for line in report.warnings:
        print(f"WARNING {line}")
    for line in report.failures:
        print(f"FAIL {line}")
    against = (
        f"{report.compared} contracted model version(s) compared with the base, {report.new} new"
        if args.base is not None
        else "no base manifest, so only the writers' own rules ran"
    )
    print(f"{against}; {len(report.failures)} failure(s), {len(report.warnings)} warning(s).")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
