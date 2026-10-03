"""gate_report: one answer for every R2 key today's pipeline publishes, from the shadow run's parity results.

    python gate_report.py --parity-dir <dir> --out <dir> [--dbt-manifest dbt/target/manifest.json] [--strict]

Exits 0 once both files are written, whatever they say; 1 with --strict when
any key blocks go (KeyRow.blocks_go); 2 when there are no parity results or
no dbt manifest to read.

Decision 30's go/no-go gate (pipeline/ELT.md, "The go/no-go gate") needs
"every existing R2 key comes out byte-equal, or is listed with a reviewed
reason". This is that list, built from the `<family>.json` files that
`parity.py <family> --new <file> --json-dir <dir>` writes, one per line of
CI's "Parity with today's exporters" step. It writes `gate_report.md` for a
maintainer reading a pull request and `gate_report.json`, the same rows for a
program, and runs no pipeline, reads no bucket and needs no credential.

EVERY KEY comes from publish.py's own code (today_keys()), never a list kept
here: publish.collect_artifacts() run over one stub of every manifest it
reads, plus the keys published outside it (export_podcasts.PODCASTS_KEY,
archive_nynjtc_sheet_extents.ARCHIVE_KEY, publish.SIDECARS, the photo store
and its recovered-photo park, publish.MANIFEST_KEY and
lib/releases.RELEASE_INDEX_KEY). Which manifests it reads is read out of
publish.py's source (manifests_publish_reads()), and a manifest with no stub
here, or a stub for one it no longer reads, stops the report. A key that
exists once per cell or per hike is listed once, with a `{placeholder}`.
Where publish() puts each key (the environment's root, a release folder) is
the same for either pipeline: publish.with_dbt_phone_files() swaps only the
entries.

WHICH KEYS DBT WRITES comes from the dbt manifest: each exposure's
`meta.r2_keys`, paired with its phone_file writer by
check_contract_versions.keys_by_writer(), as publish.collect_dbt_phone_files()
pairs them. A parity result reaches a key through the file it compared
(`--new`), which is that writer's `location`.

THE ANSWERS, worst first:
- `differs`: differences nothing explains, or one side wrote no file. A
  difference touching a SAFETY_FIELDS field ranks first: ELT.md's "How a rule
  moves" approves safety fields "one row at a time, never in bulk", and a
  safety field that differs is a defect unless a decision names it.
- `not_compared`: a parity result compared no record, because neither side
  wrote a file on this input, today's builder refused it, or both files held
  no record and the family is not in MAY_COMPARE_NO_RECORDS.
- `not_ported`: no parity result covers the key, either because none names
  its dbt writer's file or because no dbt writer owns it (so today's exporter
  writes it whatever OURHIKE_PHONE_FILES says). A key no family covers is
  never counted as passing.
- `equal_apart_from_listed`: no unexplained difference, and everything not
  held equal is listed with its reason: a difference the family's `explained`
  names, a field held to its form only (`stamps`), record order for an
  unordered family.
- `equal`: every record and top-level field equal, in order where order is
  published.

WHY NOT "BYTE-EQUAL". parity.py compares canonical JSON (keys sorted,
whitespace gone) and never holds the old file's bytes, because most old sides
are built in memory from the exporter's own builder. So `equal` means
record-for-record content, and the bytes differ wherever the writers format
differently: podcasts/episodes.json is compact from dbt and indented from
export_podcasts.py (measured 2026-10-01: 33,234 B → 25,457 B, no content
difference; ELT.md's known-differences table). That formatting is the
reviewed reason every `equal` key carries, stated once.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lib.poi_schema import ALLOWED_EMPTY_POI_TYPES
from parity import RESULT_FORMAT as PARITY_RESULT_FORMAT

PIPELINE_DIR = Path(__file__).resolve().parent
DBT_MANIFEST_DEFAULT = PIPELINE_DIR / "dbt" / "target" / "manifest.json"
REPORT_FORMAT = "ourhike-gate-report/1"

#: The phone-file field names a hiker's safety turns on, by the group ELT.md's
#: "How a rule moves" names: "water distance, capacity, `confidence`, `mile`,
#: `trail_status`, the closure fields and elevation". Matched against the last
#: segment of each changed field path, in any family, so a match can only
#: rank a difference higher (`status` is a closure's and a report's both).
#: The names are each file's own, read off the fixture writers' output
#: 2026-10-02 (poi_<type>.geojson, nearby_trails.geojson, the conditions
#: files, elevation_profile.json, trail_miles.json, spurs.json,
#: club_sections.json). A safety field a file names otherwise is missed
#: here: @unvalidated as complete, settled by reading every v1 writer's
#: contract against ELT.md's safety-field table.
SAFETY_FIELDS: dict[str, str] = {
    "water_distance_ft": "water distance",
    "water_distance_source": "water distance",
    "capacity": "capacity",
    "confidence": "confidence",
    "mile": "mile",
    "miles": "mile",  # trail_miles.json's per-vertex miles; club_sections.json's stretches
    "junction_mile": "mile",  # spurs.json
    "distance_mi": "elevation",  # elevation_profile.json's mile axis
    "elevation_ft": "elevation",
    "part_start": "elevation",
    "climb_gain_ft": "elevation",
    "climb_loss_ft": "elevation",
    "trail_status": "trail_status",
    "closure_kind": "closure fields",
    "closure_reason": "closure fields",
    "closure_source": "closure fields",
    "trails_closed_within_m": "closure fields",
    "obstructs_trail": "closure fields",
    "review_state": "closure fields",
    "start_mile_marker": "closure fields",
    "end_mile_marker": "closure fields",
    "start_lat": "closure fields",
    "start_lon": "closure fields",
    "end_lat": "closure fields",
    "end_lon": "closure fields",
    "closed_since": "closure fields",
    "expected_reopen": "closure fields",
    "reroute_url": "closure fields",
    "reason_type": "closure fields",
    "moderation_status": "closure fields",
    "status": "closure fields",
    "severity": "closure fields",  # a report's, which decides whether it is a serious one
}

#: Where a thing is, and how far: not in the decision's list, so ranked after
#: it and before everything else. A water source that moves is a hiker sent
#: to the wrong place, which is CLAUDE.md's "lost" and "out of water" both;
#: whether these join SAFETY_FIELDS is a question for the maintainer.
LOCATION_FIELDS = frozenset(
    {"geometry", "coordinates", "lat", "lon", "bbox", "length_ft", "length_miles", "destination_distance_m", "trailMiles"}
)

#: The parity families allowed to compare no record on either side and still
#: pass, each with why its input is empty rather than broken. Any other family
#: whose two files hold no record reads `not_compared` and blocks go: an empty
#: file equal to an empty file says nothing about the writer's records.
#: The POI types are lib/poi_schema.ALLOWED_EMPTY_POI_TYPES, the list
#: export_poi.py's own completeness gate reads, so the two cannot drift.
MAY_COMPARE_NO_RECORDS: dict[str, str] = {
    f"poi_{poi_type}{version}": (
        f"`{poi_type}` is in lib/poi_schema.ALLOWED_EMPTY_POI_TYPES: ATC publishes no trailhead layer "
        "(#1197 — Tier 1 of the map's label ladder is trailheads, parking and roads, and trailheads are not a thing "
        "the pipeline publishes), so the A.T. family's file is empty on real data too (0 features on the 2026-09-04 "
        "production release, export_poi.write_poi_type()'s docstring); the trailheads that ship are OPRHP's, in "
        "nearby_poi.geojson"
    )
    for poi_type in ALLOWED_EMPTY_POI_TYPES
    for version in ("", "_v2")
}

VERDICT_ORDER = ("differs", "not_compared", "not_ported", "equal_apart_from_listed", "equal")
VERDICT_TITLES = {
    "differs": "Differs",
    "not_compared": "Not compared: nothing to compare on this input",
    "not_ported": "Not yet ported: no parity result covers the key",
    "equal_apart_from_listed": "Equal apart from the listed differences",
    "equal": "Equal record for record",
}

#: The three ways a key is not ported, the one that blocks go first: a dbt
#: writer owns the key and nothing compared its file.
NOT_PORTED_ORDER = ("writer_without_result", "exposure_without_writer", "no_exposure")
NOT_PORTED_TITLES = {
    "writer_without_result": "A dbt writer owns it, and no parity result compared its file: this blocks go",
    "exposure_without_writer": "An exposure documents it, and today's code still writes it",
    "no_exposure": "No dbt exposure names it: today's code writes it, and the dbt path does not touch it",
}
KIND_ORDER = ("artifact", "live", "archive", "sidecar", "photo", "bookkeeping")

_PLACEHOLDER = re.compile(r"\{[^}]*\}|<[^>]*>")


def key_pattern(key: str) -> str:
    """A key with every `{placeholder}` or `<placeholder>` written `{}`, so two spellings of one pattern match."""
    return _PLACEHOLDER.sub("{}", key)


def field_name(path: str) -> str:
    """The last segment of a changed field path: `properties.capacity` -> `capacity`, `miles[]` -> `miles`."""
    return path.replace("[]", "").rsplit(".", 1)[-1]


#: SAFETY_FIELDS names too common to mean a closure outside the conditions
#: files: a challenge's `status` is draft or published, a highlight's review
#: state is editorial. Under `conditions/` they are a closure's and a report's.
CONDITIONS_ONLY = frozenset({"status", "severity", "review_state"})


def safety_groups(fields: list[str], key: str | None = None) -> list[str]:
    """The SAFETY_FIELDS groups `fields` touch, in the file at `key` (None: every name counts)."""
    names = {field_name(path) for path in fields}
    if key is not None and not key.startswith("conditions/"):
        names -= CONDITIONS_ONLY
    return sorted({SAFETY_FIELDS[name] for name in names if name in SAFETY_FIELDS})


def touches_location(fields: list[str]) -> bool:
    return any(field_name(path) in LOCATION_FIELDS or "coordinates" in path for path in fields)


# --- every key today's pipeline publishes ------------------------------------


@dataclass(frozen=True)
class TodayKey:
    key: str
    kind: str  # artifact, live, archive, sidecar, photo, bookkeeping
    found_in: str  # the manifest, constant or function that names it
    written_by: str | None = None


def manifests_publish_reads(publish_module) -> set[str]:
    """Every manifest publish.collect_artifacts() reads, out of publish.py's source.

    A quoted `<name>_manifest.json`, `poi/manifest.json` (written `"poi" /
    "manifest.json"`), and `<family>_cells_manifest.json` for every family in
    ALL_CELL_FAMILIES (written as an f-string in _collect_cells)."""
    source = Path(publish_module.__file__).read_text(encoding="utf-8")
    names = set(re.findall(r'"([a-z0-9_]+_manifest\.json)"', source))
    if '"poi" / "manifest.json"' in source:
        names.add("poi/manifest.json")
    if 'f"{family}_cells_manifest.json"' in source:
        names |= {f"{family}_cells_manifest.json" for family in publish_module.ALL_CELL_FAMILIES}
    return names


def _exporter_naming(manifest: str) -> list[Path]:
    """The pipeline scripts that spell `manifest` as a quoted literal, publish.py and this file aside."""
    skip = {"publish.py", Path(__file__).name}
    return [
        script
        for script in sorted(PIPELINE_DIR.glob("*.py"))
        if script.name not in skip and f'"{manifest}"' in script.read_text(encoding="utf-8")
    ]


def conditions_payloads(manifest: str) -> list[str]:
    """The `conditions/<payload>.json` names one conditions manifest carries, from the exporter that writes it.

    The exporter is the one export_*.py naming the manifest (as
    tests/test_publish.py finds them). Its payloads are its own constants:
    PAYLOAD, written `PAYLOAD/{cell}` when the module bakes a file per cell
    (CELL_DIR, export_weather.py), and INDEX_PAYLOAD; or, for
    export_conditions.py, which has no PAYLOAD, the stem of every *_OUT_PATH
    in its OUT_DIR. Anything else refuses, so a new shape stops the report
    rather than leaving a key out of it."""
    writers = [script for script in _exporter_naming(manifest) if script.name.startswith("export_")]
    if len(writers) != 1:
        raise RuntimeError(f"{manifest}: expected one export_*.py to name it, found {[w.name for w in writers]}")
    module = importlib.import_module(writers[0].stem)
    if hasattr(module, "PAYLOAD"):
        payloads = [module.PAYLOAD + ("/{cell}" if hasattr(module, "CELL_DIR") else "")]
        if hasattr(module, "INDEX_PAYLOAD"):
            payloads.append(module.INDEX_PAYLOAD)
        return payloads
    out_dir = getattr(module, "OUT_DIR", None)
    payloads = sorted(
        value.stem
        for name, value in vars(module).items()
        if name.endswith("_OUT_PATH") and isinstance(value, Path) and out_dir is not None and value.parent == out_dir
    )
    if not payloads:
        raise RuntimeError(f"{manifest}: {writers[0].name} has neither a PAYLOAD nor *_OUT_PATH files in its OUT_DIR")
    return payloads


def _stub_manifests(root: Path, publish_module) -> tuple[dict[str, str], dict[str, str]]:
    """One of every manifest publish.collect_artifacts() reads, written under `root`.

    Returns ({stub path: manifest}, {manifest: what names its inner keys}),
    so each key collect_artifacts() returns can be traced to the manifest
    that produced it. Every gated manifest is stubbed with its sources
    shipping (`reaches_hikers: true`), as tests/test_published_key_contract.py's
    `published` fixture stubs them: the question is which names a run can
    upload, and a closed gate would hide a name for a reason that is not about
    it."""
    import cut_trail_graph
    import export_suggested_hikes
    from lib.poi_schema import POI_TYPES

    stubs = root / "stub_files"
    stubs.mkdir(parents=True, exist_ok=True)
    origin: dict[str, str] = {}
    naming: dict[str, str] = {}

    def entry(manifest: str, name: str) -> dict:
        path = (stubs / f"{len(origin):04d}").resolve()
        path.write_text(f"stub of {name}, from {manifest}", encoding="utf-8")
        origin[str(path)] = manifest
        return {"path": str(path), "sha256": "stub"}

    def write(manifest: str, document: dict, named_by: str) -> None:
        path = root / manifest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        naming[manifest] = named_by

    shipping = {"sources": {"stub": {"reaches_hikers": True}}}
    write(
        "trails_manifest.json",
        {kind: entry("trails_manifest.json", kind) for kind in ("geojson", "fgb", "overview", "miles")},
        "publish.collect_artifacts()'s trails block",
    )
    write(
        "nearby_trails_manifest.json",
        {
            **entry("nearby_trails_manifest.json", "nearby_trails"),
            **shipping,
            "overview": entry("nearby_trails_manifest.json", "overview"),
            "tiles": entry("nearby_trails_manifest.json", "tiles"),
        },
        "publish.NEARBY_TRAILS_KEY, NETWORK_OVERVIEW_KEY, NEARBY_TRAILS_TILES_KEY",
    )
    write("nearby_poi_manifest.json", {**entry("nearby_poi_manifest.json", "nearby_poi"), **shipping}, "publish.NEARBY_POI_KEY")
    graph = {**entry("trail_graph_manifest.json", "graph"), **shipping}
    geometry = entry("trail_graph_manifest.json", "geometry")
    write(
        "trail_graph_manifest.json",
        {**graph, "geometry_path": geometry["path"], "geometry_sha256": "stub"},
        "publish.collect_artifacts()'s graph block",
    )
    for name in ("trail_graph_elevation_manifest.json", "trail_graph_profile_manifest.json"):
        write(name, {**entry(name, name), **shipping}, "publish.collect_artifacts()'s graph blocks")
    write(
        "poi/manifest.json",
        {
            poi_type: {kind: entry("poi/manifest.json", f"{poi_type}.{kind}") for kind in ("geojson", "fgb")}
            for poi_type in POI_TYPES
        },
        "lib/poi_schema.POI_TYPES",
    )
    for name in (
        "elevation_manifest.json",
        "spurs_manifest.json",
        "club_sections_manifest.json",
        "stewards_manifest.json",
        "registry_manifest.json",
        "highlights_manifest.json",
        "challenges_manifest.json",
        "suggested_hikes_manifest.json",
        "places_manifest.json",
        "retired_poi_manifest.json",
    ):
        write(name, entry(name, name), "publish.collect_artifacts()")
    detail = export_suggested_hikes.DETAIL_KEY.format(id="{id}")
    write(
        "suggested_hikes_detail_manifest.json",
        {"artifacts": {detail: entry("suggested_hikes_detail_manifest.json", detail)}},
        "export_suggested_hikes.DETAIL_KEY",
    )
    for name in publish_module.CONDITIONS_MANIFESTS:
        payloads = conditions_payloads(name)
        write(name, {"artifacts": {payload: entry(name, payload) for payload in payloads}}, "the exporter's PAYLOAD")
    # cut_cells.py spells a sheet family's file names inline (context_name,
    # cell_key, index_name), so they are spelled here the same way, and
    # tests/test_gate_report.py holds the three f-strings to that file.
    # cut_trail_graph.py exports its own.
    for family in publish_module.ALL_CELL_FAMILIES:
        name = f"{family}_cells_manifest.json"
        if family == cut_trail_graph.FAMILY:
            names = [cut_trail_graph.INDEX_NAME, *(cut_trail_graph.cell_key("{cell}", half) for half in cut_trail_graph.HALVES)]
            named_by = "cut_trail_graph.INDEX_NAME and cell_key()"
        else:
            names = [f"{family}_cells.json", f"{family}_context.pmtiles", f"{family}_cell_{{cell}}.pmtiles"]
            named_by = "cut_cells.py's index, context and cell names"
        write(name, {"artifacts": {inner: entry(name, inner) for inner in names}}, named_by)
    for name in (*publish_module.BACKGROUND_ARCHIVES.values(), *publish_module.OFFLINE_SHEET_ARCHIVES.values()):
        (root / name).write_text(f"stub of {name}", encoding="utf-8")
        origin[str((root / name).resolve())] = name
        naming[name] = "publish.BACKGROUND_ARCHIVES / OFFLINE_SHEET_ARCHIVES"
    return origin, naming


def today_keys() -> list[TodayKey]:
    """Every R2 key today's pipeline can publish, from publish.py's code (the module docstring says how)."""
    import archive_nynjtc_sheet_extents
    import export_podcasts
    import publish
    from lib import releases
    from lib.photo_store import PHOTO_EXTENSION, PHOTO_PREFIX

    keys: list[TodayKey] = []
    with tempfile.TemporaryDirectory(prefix="gate-report-") as scratch:
        root = Path(scratch)
        origin, naming = _stub_manifests(root, publish)
        reads = manifests_publish_reads(publish)
        stubbed = {name for name in naming if name.endswith("manifest.json")}
        if reads != stubbed:
            raise RuntimeError(
                "gate_report.py's stubs and the manifests publish.py reads disagree: "
                f"read and not stubbed {sorted(reads - stubbed)}, stubbed and not read {sorted(stubbed - reads)}. "
                "A key a manifest names would be missing from the report, so it refuses."
            )
        saved = publish.PROCESSED_DIR
        try:
            publish.PROCESSED_DIR = root
            with contextlib.redirect_stdout(io.StringIO()):
                artifacts = publish.collect_artifacts()
        finally:
            publish.PROCESSED_DIR = saved
    # found_in names the manifest, not the script that wrote it: a grep for the
    # manifest's name finds its writer and its readers.
    for key, entry in sorted(artifacts.items()):
        manifest = origin.get(str(Path(entry["path"]).resolve()), "?")
        keys.append(TodayKey(key, "artifact", f"publish.collect_artifacts(), from {manifest} ({naming.get(manifest, '?')})"))
    keys += [
        TodayKey(
            export_podcasts.PODCASTS_KEY,
            "live",
            "export_podcasts.PODCASTS_KEY (a root key no manifest names; publish.LIVE_ROOT_PREFIXES)",
            "export_podcasts.py",
        ),
        TodayKey(
            archive_nynjtc_sheet_extents.ARCHIVE_KEY,
            "archive",
            "archive_nynjtc_sheet_extents.ARCHIVE_KEY (a one-off snapshot, written on a person's dispatch)",
            "archive_nynjtc_sheet_extents.py",
        ),
        *(TodayKey(name, "sidecar", "publish.SIDECARS", "publish.py") for name in sorted(publish.SIDECARS)),
        TodayKey(f"{PHOTO_PREFIX}/{{sha256}}.{PHOTO_EXTENSION}", "photo", "lib/photo_store.photo_key()", "publish.py"),
        TodayKey(
            f"{publish.ARCHIVE_PARK_PREFIX}/{{sha256}}.{PHOTO_EXTENSION}",
            "photo",
            "publish.archive_park_objects()",
            "publish.py",
        ),
        TodayKey(publish.MANIFEST_KEY, "bookkeeping", "publish.MANIFEST_KEY", "publish.py"),
        TodayKey(releases.RELEASE_INDEX_KEY, "bookkeeping", "lib/releases.RELEASE_INDEX_KEY", "publish.py"),
    ]
    return keys


# --- which keys dbt writes, and the parity results ---------------------------


@dataclass(frozen=True)
class DbtKey:
    key: str
    exposure: str
    writer: str | None  # the phone_file model's unique_id, or None for an exposure documenting a Python file
    location: str | None  # the file the writer writes under processed_dir


def dbt_keys(manifest: dict) -> list[DbtKey]:
    """Every key a dbt exposure names, with its writer where one writes it (check_contract_versions.keys_by_writer)."""
    import check_contract_versions

    nodes = manifest.get("nodes") or {}
    found: list[DbtKey] = []
    for exposure_id, exposure in sorted((manifest.get("exposures") or {}).items()):
        meta = (exposure.get("config") or {}).get("meta") or exposure.get("meta") or {}
        named = list(meta.get("r2_keys") or [])
        paired = check_contract_versions.keys_by_writer(exposure, nodes)
        written = {key: writer for writer, keys in paired.items() for key in keys}
        for key in named:
            writer = written.get(key)
            location = ((nodes.get(writer) or {}).get("config") or {}).get("location") if writer else None
            found.append(DbtKey(key, exposure.get("name") or exposure_id, writer, location))
    return found


def load_results(parity_dir: Path) -> dict[str, dict]:
    """Every parity result in `parity_dir`, by family; a JSON file in another format is refused by name."""
    results: dict[str, dict] = {}
    for path in sorted(parity_dir.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("format") != PARITY_RESULT_FORMAT:
            raise ValueError(f"{path} is not a parity result ({PARITY_RESULT_FORMAT}); only parity.py's go in --parity-dir")
        results[document["family"]] = document
    return results


# --- the answer per key -------------------------------------------------------


@dataclass
class Listed:
    """One thing the comparison did not hold equal, and its reason."""

    what: str
    reason: str
    fields: list[str] = field(default_factory=list)
    safety: list[str] = field(default_factory=list)
    old: str | None = None
    new: str | None = None
    # Set when parity.py ran with --keys-only: the sides that hold it, whose records were not written.
    held_by: list[str] | None = None


@dataclass
class KeyRow:
    key: str
    kind: str
    found_in: str
    written_by: str | None
    verdict: str
    detail: str
    why: str | None = None  # not_ported only: one of NOT_PORTED_ORDER
    family: str | None = None
    exposure: str | None = None
    writer: str | None = None
    new_file: str | None = None
    old_records: int | None = None
    new_records: int | None = None
    differences: list[Listed] = field(default_factory=list)
    listed: list[Listed] = field(default_factory=list)

    @property
    def safety(self) -> list[str]:
        return sorted({group for item in [*self.differences, *self.listed] for group in item.safety})

    @property
    def blocks_go(self) -> bool:
        """This report's reading of decision 30 item 2, for the maintainer to confirm: a key blocks go when it
        differs, when nothing was compared, or when a dbt writer owns it and no result compared its file. A key the
        dbt path does not write is listed with its reason and does not block."""
        return self.verdict in ("differs", "not_compared") or self.why == "writer_without_result"

    @property
    def rank(self) -> tuple:
        differing_safety = any(item.safety for item in self.differences)
        differing_location = any(touches_location(item.fields) for item in self.differences)
        explained_safety = any(item.safety for item in self.listed)
        return (
            VERDICT_ORDER.index(self.verdict),
            NOT_PORTED_ORDER.index(self.why) if self.why in NOT_PORTED_ORDER else 0,
            KIND_ORDER.index(self.kind) if self.kind in KIND_ORDER else len(KIND_ORDER),
            not differing_safety,
            not differing_location,
            not explained_safety,
            self.key,
        )


def _difference(item: dict, reason: str | None = None) -> Listed:
    fields = list(item.get("fields") or [])
    return Listed(
        what=item["what"],
        reason=reason or item.get("reason") or "",
        fields=fields,
        safety=safety_groups(fields),
        old=item.get("old"),
        new=item.get("new"),
        held_by=item.get("held_by"),
    )


def judge(result: dict, pattern_note: str | None = None) -> tuple[str, str, list[Listed], list[Listed]]:
    """(verdict, detail, differences, listed) for one parity result."""
    outcome = result["outcome"]
    differences = [
        _difference(item, "not explained: a defect in the new path until it is classified") for item in result["differences"]
    ]
    if outcome in ("differences", "one_side_writes"):
        detail = result.get("message") or f"{len(differences)} difference(s) nothing explains"
        return "differs", detail, differences, [_difference(item) for item in result["explained"]]
    if outcome == "neither_writes":
        return (
            "not_compared",
            "neither today's exporter nor the writer wrote a file on this input, so no record was compared",
            [],
            [],
        )
    if outcome == "old_side_refused":
        return "not_compared", f"today's builder refused this input, so nothing was compared: {result.get('message')}", [], []
    if outcome != "no_differences":
        raise ValueError(f"{result['family']}: unknown parity outcome {outcome!r}")
    empty = not result.get("old_records") and not result.get("new_records")
    if empty and result["family"] not in MAY_COMPARE_NO_RECORDS:
        return (
            "not_compared",
            f"both files hold no {result.get('records')} on this input, so no record was compared, and "
            "gate_report.MAY_COMPARE_NO_RECORDS does not say this family may be empty",
            [],
            [],
        )
    listed = [_difference(item) for item in result["explained"]]
    listed += [
        Listed(
            f"field {name}",
            "held to its form (a UTC stamp, parity.STAMP) on both sides, never to its value: it is the moment the run happened",
        )
        for name in result.get("compared_by_form_only") or []
    ]
    if not result.get("ordered"):
        listed.append(
            Listed("order", "record order is not compared: parity.py's family declares it unordered, with its reason there")
        )
    if pattern_note:
        listed.append(Listed("key pattern", pattern_note))
    if empty:
        listed.append(
            Listed(
                "records",
                f"no {result.get('records')} on either side on this input, so only the file's top-level fields were "
                f"compared; the family may be empty because {MAY_COMPARE_NO_RECORDS[result['family']]}",
            )
        )
    records = f"{result.get('new_records')} {result.get('records')}"
    if listed:
        return "equal_apart_from_listed", f"no unexplained difference across {records}; {len(listed)} listed", [], listed
    return "equal", f"no difference across {records}, keyed by {result.get('key')}", [], []


def key_rows(today: list[TodayKey], dbt: list[DbtKey], results: dict[str, dict]) -> tuple[list[KeyRow], list[dict], list[DbtKey]]:
    """Every today key's answer, the parity results that reach no today key, and the dbt keys today does not publish."""
    by_pattern = {key_pattern(entry.key): entry for entry in dbt}
    by_location: dict[str, list[dict]] = {}
    for result in results.values():
        by_location.setdefault(result["new_file_name"], []).append(result)

    rows: list[KeyRow] = []
    used: set[str] = set()
    for entry in today:
        owned = by_pattern.get(key_pattern(entry.key))
        row = KeyRow(entry.key, entry.kind, entry.found_in, entry.written_by, "not_ported", "")
        if owned is None:
            row.why = "no_exposure"
            row.detail = (
                "no dbt exposure names it: today's code writes it under either setting of OURHIKE_PHONE_FILES, "
                "and nothing in this pull request compares it"
            )
        elif owned.writer is None:
            row.exposure, row.why = owned.exposure, "exposure_without_writer"
            row.detail = (
                f"exposure {owned.exposure} documents it with no phone_file writer, so today's code still writes it "
                "(publish.collect_dbt_phone_files skips an exposure with no writer)"
            )
        else:
            row.exposure, row.writer = owned.exposure, owned.writer
            matched = by_location.get(owned.location or "", [])
            if not matched:
                row.why = "writer_without_result"
                row.detail = (
                    f"{owned.writer} writes it as {owned.location}, and no parity result in --parity-dir compared that file"
                )
            else:
                if len(matched) > 1:
                    raise ValueError(f"{owned.location} is compared by more than one family: {[r['family'] for r in matched]}")
                result = matched[0]
                used.add(result["family"])
                note = None
                if key_pattern(entry.key) != entry.key:
                    note = (
                        f"one key per {{placeholder}}: {owned.writer} writes them as one file, {owned.location}, which is "
                        "what was compared; the cut into one object each is not"
                    )
                row.verdict, row.detail, row.differences, row.listed = judge(result, note)
                for item in [*row.differences, *row.listed]:
                    item.safety = safety_groups(item.fields, entry.key)
                row.family, row.new_file = result["family"], result["new_file"]
                row.old_records, row.new_records = result.get("old_records"), result.get("new_records")
        rows.append(row)
    today_patterns = {key_pattern(entry.key) for entry in today}
    unmatched = [result for family, result in sorted(results.items()) if family not in used]
    new_keys = [entry for entry in dbt if key_pattern(entry.key) not in today_patterns]
    return sorted(rows, key=lambda row: row.rank), unmatched, new_keys


# --- writing it ---------------------------------------------------------------


def _clip(text: str | None, limit: int = 400) -> str:
    if text is None:
        return "(absent)"
    return text if len(text) <= limit else f"{text[:limit]}… ({len(text):,} characters; the whole text is in gate_report.json)"


def _side(item: Listed, side: str) -> str:
    if item.held_by is None:
        return _clip(getattr(item, side))
    return "(withheld: parity.py --keys-only)" if side in item.held_by else "(absent)"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _table(rows: list[KeyRow]) -> list[str]:
    return [
        "| Key | Kind | Why | Found in |",
        "|---|---|---|---|",
        *(f"| `{row.key}` | {row.kind} | {_cell(row.detail)} | {_cell(row.found_in)} |" for row in rows),
        "",
    ]


def _listed(items: list[Listed]) -> list[str]:
    """The listed differences, one bullet per (reason, safety groups, changed fields), safety first."""
    groups: dict[tuple, list[str]] = {}
    for item in items:
        groups.setdefault((not item.safety, item.reason, tuple(item.safety), tuple(item.fields)), []).append(item.what)
    lines = []
    for (_, reason, safety, fields), named in sorted(groups.items()):
        flag = f" (**safety: {', '.join(safety)}**, approve each row on its own)" if safety else ""
        changed = f" Changed: {', '.join(f'`{name}`' for name in fields)}." if fields else ""
        shown = ", ".join(f"`{_cell(what)}`" for what in named[:12]) + (f" and {len(named) - 12} more" if len(named) > 12 else "")
        lines.append(f"- listed, {len(named)}: {shown}{flag}. {reason}.{changed}")
    return lines


def _shown(path: Path) -> str:
    """`path` relative to pipeline/ where it is under it, so the report reads the same on any machine."""
    try:
        return path.resolve().relative_to(PIPELINE_DIR).as_posix()
    except ValueError:
        return str(path)


def render_markdown(rows: list[KeyRow], unmatched: list[dict], new_keys: list[DbtKey], inputs: dict) -> str:
    counts = {verdict: sum(row.verdict == verdict for row in rows) for verdict in VERDICT_ORDER}
    safety_rows = [row for row in rows if row.verdict == "differs" and any(item.safety for item in row.differences)]
    explained_safety = [row for row in rows if row.verdict != "differs" and any(item.safety for item in row.listed)]
    lines = [
        "# Go/no-go gate: every R2 key today's pipeline publishes",
        "",
        f'Decision 30, item 2 (pipeline/ELT.md, "The go/no-go gate"). {len(rows)} keys, from parity results in '
        f"`{inputs['parity_dir']}` ({inputs['results']} families) and the dbt manifest `{inputs['dbt_manifest']}`.",
        "",
        "| Answer | Keys |",
        "|---|---|",
        *(f"| {VERDICT_TITLES[verdict]} | {counts[verdict]} |" for verdict in VERDICT_ORDER),
        "",
        f"**{len(safety_rows)} key(s) differ on a safety field**, and {len(explained_safety)} more carry an explained "
        "difference that touches one. ELT.md: safety fields are approved one row at a time, never in bulk.",
        "",
        f"**{sum(row.blocks_go for row in rows)} key(s) block go** on this report's reading of decision 30 (for the "
        "maintainer to confirm): a key that differs, that nothing was compared for, or that a dbt writer owns with no "
        "parity result. A key the dbt path does not write is listed with its reason and does not block.",
        "",
        '"Equal" is record for record, as parity.py compares: canonical JSON, keys sorted and whitespace gone. No key '
        "is claimed byte-equal: the old side is built in memory, so its bytes are never held, and the writers format "
        "differently (podcasts/episodes.json: compact against indented, 33,234 B → 25,457 B, measured 2026-10-01). "
        "That formatting is the reviewed reason every equal key carries.",
        "",
    ]
    for verdict in VERDICT_ORDER:
        section = [row for row in rows if row.verdict == verdict]
        if not section:
            continue
        lines += [f"## {VERDICT_TITLES[verdict]} ({len(section)})", ""]
        if verdict in ("differs", "equal_apart_from_listed"):
            for row in section:
                flag = f" — **safety: {', '.join(row.safety)}**" if row.safety else ""
                lines += [
                    f"### `{row.key}`{flag}",
                    "",
                    f"{row.detail}. Family `{row.family}`, writer `{row.writer}`, file `{row.new_file}`; "
                    f"{row.old_records} records today, {row.new_records} from dbt.",
                    "",
                ]
                for item in sorted(row.differences, key=lambda item: (not item.safety, item.what)):
                    groups = f" (safety: {', '.join(item.safety)})" if item.safety else ""
                    lines += [
                        f"- **{_cell(item.what)}**{groups}: {item.reason}. Changed: {', '.join(f'`{f}`' for f in item.fields) or '—'}",
                        *(f"  - {side}: `{_cell(_side(item, side))}`" for side in ("old", "new")),
                    ]
                lines += [*_listed(row.listed), ""]
        elif verdict == "not_ported":
            for why in NOT_PORTED_ORDER:
                group = [row for row in section if row.why == why]
                if group:
                    lines += [f"### {NOT_PORTED_TITLES[why]} ({len(group)})", "", *_table(group)]
        else:
            lines += _table(section)
    if new_keys:
        lines += [
            f"## Keys a dbt exposure names that today's pipeline does not publish ({len(new_keys)})",
            "",
            "Parity cannot check a key that did not exist before (decision 31): these are new_data_report.py's to review.",
            "",
            *(f"- `{entry.key}` (exposure {entry.exposure}, writer {entry.writer or 'none'})" for entry in new_keys),
            "",
        ]
    if unmatched:
        lines += [
            f"## Parity results that reach no published key ({len(unmatched)})",
            "",
            *(f"- family `{r['family']}`, file `{r['new_file']}`, outcome {r['outcome']}" for r in unmatched),
            "",
        ]
    lines += [
        "## How the key list was found",
        "",
        "From publish.py's code, not from memory: `publish.collect_artifacts()`, the function `publish()` uploads from, "
        "run over one stub of every manifest it reads (the manifest names read from publish.py's own source; the "
        "report refuses to run when one has no stub), plus the keys published outside it: the podcast list, the "
        "map-sheet archive, `publish.SIDECARS`, the photo store and its recovered-photo park, `latest.json` and "
        "`releases/index.json`. A `{placeholder}` stands for one key per cell, per hike or per photo. Which keys dbt "
        "writes is each exposure's `meta.r2_keys`, paired with its writer the way `publish.collect_dbt_phone_files()` "
        "pairs them. gate_report.py's docstring has the rest.",
        "",
    ]
    return "\n".join(lines)


def build_report(parity_dir: Path, dbt_manifest: Path) -> dict:
    results = load_results(parity_dir)
    if not results:
        raise FileNotFoundError(f"{parity_dir} holds no parity results; run parity.py with --json-dir {parity_dir} first")
    if not dbt_manifest.exists():
        raise FileNotFoundError(f"{dbt_manifest} is missing; the report reads which keys dbt writes from the dbt manifest")
    manifest = json.loads(dbt_manifest.read_text(encoding="utf-8"))
    rows, unmatched, new_keys = key_rows(today_keys(), dbt_keys(manifest), results)
    inputs = {"parity_dir": _shown(parity_dir), "dbt_manifest": _shown(dbt_manifest), "results": len(results)}
    return {
        "format": REPORT_FORMAT,
        "inputs": inputs,
        "counts": {verdict: sum(row.verdict == verdict for row in rows) for verdict in VERDICT_ORDER},
        "blocking": [row.key for row in rows if row.blocks_go],
        "keys": [{**asdict(row), "safety": row.safety, "blocks_go": row.blocks_go} for row in rows],
        "unmatched_results": [{"family": r["family"], "new_file": r["new_file"], "outcome": r["outcome"]} for r in unmatched],
        "new_keys": [asdict(entry) for entry in new_keys],
        "markdown": render_markdown(rows, unmatched, new_keys, inputs),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--parity-dir", type=Path, required=True, help="where parity.py --json-dir wrote its <family>.json files")
    parser.add_argument("--out", type=Path, required=True, help="where gate_report.md and gate_report.json are written")
    parser.add_argument("--dbt-manifest", type=Path, default=DBT_MANIFEST_DEFAULT, help="the dbt manifest the writers ran from")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when any key blocks go (KeyRow.blocks_go); without it, a written report exits 0 whatever it says",
    )
    args = parser.parse_args(argv)
    try:
        report = build_report(args.parity_dir, args.dbt_manifest)
    except (FileNotFoundError, ValueError) as problem:
        print(f"gate_report: {problem}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    markdown = report.pop("markdown")
    (args.out / "gate_report.md").write_text(markdown, encoding="utf-8")
    (args.out / "gate_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = ", ".join(f"{count} {verdict}" for verdict, count in report["counts"].items())
    print(
        f"gate_report: {sum(report['counts'].values())} keys: {counts}; {len(report['blocking'])} block go; "
        f"wrote {args.out / 'gate_report.md'}"
    )
    return 1 if args.strict and report["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
