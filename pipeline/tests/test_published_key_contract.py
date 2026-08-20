"""Every key the app fetches, against the keys publish.py actually writes.

WHY THIS IS THE ONE CONTRACT WORTH A TEST OF ITS OWN

A key in this bucket is not a filename, it is a URL a deployed phone already
requests. `lib/r2_keys.py` says why that cannot be undone - `publish()`'s
manifest merge is additive-only and app-store builds cannot be forced
forward - and `lib/config.ts` states the same rule from the other end:
"Keys are flat at the bucket root and must match publish.py's artifact names
exactly - a mismatch here is a 404 on a mountain."

Both ends say it. Nothing checked it. And the failure is silent by design at
every layer between them: a missing artifact is a legal partial export, an
absent `spurs.json` is "no spur detail" rather than a failed download, and an
absent POI file is an empty FeatureCollection. So a name that drifts does not
raise anywhere - it produces an app with one layer quietly missing, which is
indistinguishable from a stretch of trail that has no shelters on it.

That is not hypothetical. `lib/poi_schema.py`'s `poi_output_name` docstring
records the same bug inside the pipeline alone: export wrote
`shelter.geojson`, spurs read `poi_shelter.geojson`, "both spellings are
correct in their own place, which is exactly why neither end looked wrong",
and 784 spurs published with a null destination while the run went green
(#469). That fix gave the two Python callers one home. This is the same fix
across the language boundary, where an import cannot be the mechanism.

HOW IT CHECKS

By running `publish.collect_artifacts()` against a processed directory
holding one of everything, and asking whether each key the client builds is
in the result. Not by restating the names here: a third copy of the list is
the thing being guarded against (the same reasoning
`backend/tests/test_preferences_contract.py` sets out for reading the
TypeScript as text).

WHAT IS DELIBERATELY NOT CHECKED

`latest.json` and the `releases/` and `photos/` prefixes. Those are read
through `lib/dataManifest.ts` and the manifest's own contents rather than
built from a constant, and `lib/r2_keys.RESERVED_KEYS` already holds their
spelling on this side.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import publish
from lib.poi_schema import POI_TYPES
from lib.r2_keys import validate_key

CLIENT_SRC = Path(__file__).resolve().parents[2] / "client" / "src"
CONFIG = CLIENT_SRC / "lib" / "config.ts"
PUBLISHED_CONDITIONS = CLIENT_SRC / "lib" / "publishedConditions.ts"
HIKING_DETAIL = CLIENT_SRC / "lib" / "hikingDetail.ts"
PACKAGES = CLIENT_SRC / "lib" / "packages.ts"

# Named as a set rather than left implicit in the calls below, because
# tests/test_ci_scope.py reads it: the pipeline workflow lists these files
# individually so that ordinary client work does not run the whole pipeline
# suite, and a narrow list is only honest while it is complete. Add a client
# file to this module and it belongs here in the same edit - the scope test is
# what makes forgetting a failure rather than a silent hole.
CLIENT_FILES_READ = (CONFIG, PUBLISHED_CONDITIONS, HIKING_DETAIL, PACKAGES)


def _read(path: Path) -> str:
    """The client module, or a failure naming it.

    Fails rather than skips. A guard that quietly stops looking is worse than
    no guard, because the suite still reports green - and this one is the
    only thing standing between a renamed artifact and a 404 in a place with
    no signal to report it from.
    """
    assert path.exists(), (
        f"{path} is missing, so this test cannot compare anything. If the "
        "module moved, fix the path here rather than deleting the test."
    )
    return path.read_text()


def _string_const(source: str, name: str) -> str:
    match = re.search(rf"export const {name} = '([^']+)'", source)
    assert match is not None, f"Could not find `export const {name} = '...'`"
    return match.group(1)


def _string_array(source: str, name: str) -> list[str]:
    match = re.search(rf"export const {name} = \[(.*?)\]", source, re.DOTALL)
    assert match is not None, f"Could not find `export const {name} = [...]`"
    return re.findall(r"'([^']+)'", match.group(1))


def client_poi_types() -> list[str]:
    return _string_array(_read(CONFIG), "POI_TYPES")


def client_poi_key_format() -> str:
    """The template `poiKey` builds, as a Python format string.

    Read out of the client's own template literal rather than written here,
    so the `poi_` prefix and the extension are the client's spelling and not
    this test's memory of it.
    """
    source = _read(CONFIG)
    match = re.search(r"return `([a-z_]*)\$\{type\}(\.[a-z0-9]+)`", source)
    assert match is not None, (
        "Could not find poiKey's template literal in config.ts. If it was "
        "rewritten, fix the pattern here - the prefix and extension it "
        "builds are the contract this file exists to check."
    )
    return match.group(1) + "{type}" + match.group(2)


def client_background_archives() -> dict[str, str]:
    """config.ts's tier -> filename map. Not exported, so matched by name."""
    body = re.search(r"BACKGROUND_ARCHIVES[^=]*= \{(.*?)\n\}", _read(CONFIG), re.DOTALL)
    assert body is not None, "Could not find BACKGROUND_ARCHIVES in config.ts"
    return dict(re.findall(r"(\w+): '([^']+)'", body.group(1)))


def client_keys() -> dict[str, str]:
    """Every published key this build of the app can request, and what asks
    for it - the label is what turns a failure into a place to go."""
    config = _read(CONFIG)
    conditions = _read(PUBLISHED_CONDITIONS)
    poi_format = client_poi_key_format()

    keys = {
        _string_const(config, "TRAILS_KEY"): "config.ts TRAILS_KEY",
        _string_const(config, "TRAILS_OVERVIEW_KEY"): "config.ts TRAILS_OVERVIEW_KEY",
        _string_const(config, "SPURS_KEY"): "config.ts SPURS_KEY",
        _string_const(config, "ELEVATION_KEY"): "config.ts ELEVATION_KEY",
        _string_const(conditions, "PUBLISHED_CLOSURES_KEY"): "publishedConditions.ts",
        _string_const(conditions, "PUBLISHED_REPORTS_KEY"): "publishedConditions.ts",
        _string_const(conditions, "PUBLISHED_ATC_UPDATES_KEY"): "publishedConditions.ts",
    }

    for poi_type in client_poi_types():
        keys[poi_format.format(type=poi_type)] = f"config.ts poiKey('{poi_type}')"

    for tier, name in client_background_archives().items():
        keys[name] = f"config.ts BACKGROUND_ARCHIVES.{tier}"

    for artifact in re.findall(r"artifact: '([^']+)'", _read(HIKING_DETAIL)):
        keys[artifact] = "hikingDetail.ts"

    for artifact in re.findall(r"artifact: '([^']+)'", _read(PACKAGES)):
        keys[artifact] = "packages.ts"

    return keys


@pytest.fixture
def published(tmp_path, monkeypatch) -> set[str]:
    """The keys a fully-populated pipeline run would upload.

    One of every artifact, because the question is about NAMES: a run that
    happened to skip an export would answer "that key is not published" for a
    reason that has nothing to do with whether the two ends agree.
    """
    monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)

    def manifest_entry(name: str) -> dict:
        path = tmp_path / name
        path.write_text(f"contents of {name}")
        return {"path": str(path), "sha256": f"sha-{name}"}

    trails_manifest = {kind: manifest_entry(f"trails.{kind}") for kind in ("geojson", "fgb")}
    # Its own key in the manifest and its own flat name in the bucket - see
    # publish.collect_artifacts, and export_trails.write_overview for what it
    # is (#869).
    trails_manifest["overview"] = manifest_entry("trails_overview.geojson")
    (tmp_path / "trails_manifest.json").write_text(json.dumps(trails_manifest))

    poi_dir = tmp_path / "poi"
    poi_dir.mkdir()
    (poi_dir / "manifest.json").write_text(
        json.dumps(
            {poi_type: {kind: manifest_entry(f"{poi_type}.{kind}") for kind in ("geojson", "fgb")} for poi_type in POI_TYPES}
        )
    )

    (tmp_path / "elevation_manifest.json").write_text(json.dumps(manifest_entry("elevation_profile.json")))
    (tmp_path / "spurs_manifest.json").write_text(json.dumps(manifest_entry("spurs.json")))

    conditions_dir = tmp_path / "conditions"
    conditions_dir.mkdir()
    (tmp_path / "conditions_manifest.json").write_text(
        json.dumps({"artifacts": {kind: manifest_entry(f"conditions/{kind}.json") for kind in ("closures", "reports")}})
    )
    # Its own manifest, from export_atc_updates.py rather than
    # export_conditions.py - the two legs run under different conditions and
    # each rewrites its manifest whole (see publish.py's conditions block).
    (tmp_path / "atc_updates_manifest.json").write_text(
        json.dumps({"artifacts": {"atc_updates": manifest_entry("conditions/atc_updates.json")}})
    )

    for name in (*publish.BACKGROUND_ARCHIVES.values(), *publish.OFFLINE_SHEET_ARCHIVES.values()):
        (tmp_path / name).write_bytes(b"fake pmtiles bytes for " + name.encode())

    return set(publish.collect_artifacts())


def test_every_key_the_app_fetches_is_a_key_the_pipeline_publishes(published):
    """The whole point of the file, in one assertion.

    One direction only, deliberately. The pipeline publishing something no
    client asks for is ordinary - `trails.fgb` and the `quad_sheet` tier are
    both real and neither is fetched by this build - while a client asking
    for something the pipeline does not write is a 404 on a mountain.
    """
    missing = {key: asked_by for key, asked_by in client_keys().items() if key not in published}

    assert not missing, (
        "The app fetches keys publish.py does not write. A key in this bucket "
        "is a URL a deployed phone already requests, and the client fails "
        "soft on a missing artifact - so this is a layer quietly absent from "
        "the map, not an error anybody sees:\n"
        + "\n".join(f"  - {key}  (asked for by {asked_by})" for key, asked_by in sorted(missing.items()))
    )


def test_both_ends_publish_the_same_poi_types():
    """`lib/poi_schema.POI_TYPES` and `config.ts`'s copy of it.

    Compared as sets: the client lists them in the order the legend reads and
    the pipeline in the order it exports, and neither order is a promise to
    the other. Membership is.
    """
    client = set(client_poi_types())
    pipeline = set(POI_TYPES)

    assert client == pipeline, (
        "client/src/lib/config.ts and pipeline/lib/poi_schema.py disagree "
        "about the POI categories. A type only the client knows is a 404 it "
        "reads as an empty layer; a type only the pipeline knows is data "
        "published and never drawn.\n"
        f"  only in the client: {sorted(client - pipeline)}\n"
        f"  only in the pipeline: {sorted(pipeline - client)}"
    )


def test_the_download_tiers_name_the_same_archives_on_both_sides():
    """`config.ts`'s BACKGROUND_ARCHIVES against `publish.py`'s.

    test_publish.py already holds that the pipeline can produce every tier
    the app offers, but it names the three tiers in Python - so a tier RENAMED
    on the client, or pointed at a different file, passes it. This compares
    the mappings themselves.
    """
    client = client_background_archives()
    pipeline = publish.BACKGROUND_ARCHIVES

    for tier, name in client.items():
        assert tier in pipeline, (
            f"config.ts offers a '{tier}' download that publish.py has no archive for. publish.py knows: {sorted(pipeline)}"
        )
        assert pipeline[tier] == name, (
            f"The '{tier}' tier is two different files: config.ts fetches '{name}', publish.py writes '{pipeline[tier]}'"
        )


def test_every_key_the_app_fetches_is_legal_in_this_bucket():
    """The layout rules, applied to the requesting end.

    `assert_valid_keys` runs over what publish.py is about to upload. A key
    the client builds that would be refused there is a download that can
    never be satisfied, and it is worth catching in the suite that owns the
    rules rather than on the first run that tries to publish it.
    """
    illegal = {key: reason for key in client_keys() if (reason := validate_key(key)) is not None}

    assert not illegal, "Keys the app fetches that this bucket would refuse:\n" + "\n".join(
        f"  - {reason}" for reason in illegal.values()
    )


def test_this_is_actually_reading_the_client(published):
    """Guards the guard.

    Every regex above could match nothing and leave the comparisons running
    over empty sets - green for ever, while the two ends drifted. Named
    artifacts rather than counts, all of them long-standing, so this fails
    when the parse breaks rather than when somebody publishes something new.
    """
    keys = client_keys()

    assert "trails.geojson" in keys
    assert "poi_shelter.geojson" in keys
    assert "conditions/closures.json" in keys
    assert "dem.pmtiles" in keys
    assert "at_basemap_package.pmtiles" in keys
    assert len(keys) >= 12
    assert len(client_background_archives()) == 3
    assert len(published) >= 15
