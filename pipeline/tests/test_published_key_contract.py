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


def client_conditions_keys() -> dict[str, str]:
    """Every `conditions/` key publishedConditions.ts declares.

    FOUND RATHER THAN LISTED, and that is the whole of #1145. This census
    named three of the eight - closures, reports and atc_updates - so drought,
    notes, disputes, work_projects and (newest, #1108) nynjtc_alerts were
    spelled at both ends with nothing holding the two spellings together.

    A hand-kept list here is the third copy this module's docstring says is
    the thing being guarded against, and it had already rotted twice by the
    time anybody looked: the list was written when there were three keys and
    never grew with the feed. Matching the declaration is what makes a ninth
    key covered on the day it is declared instead of on the day somebody
    remembers this file.

    THE CONDITIONS FAMILY IS THE WORST PLACE TO LOSE A NAME, which is why it
    is worth a function rather than five more lines. A 404 under this prefix
    is rendered as "this organization has no layer" by design - the right
    answer for a hiker, and the reason a respelling here is a permanently
    silent loss of a safety surface rather than an error anybody sees. This
    exact artifact 404'd on production between being registered (d0c169de,
    2026-08-27 02:14Z) and having a runner (#1108, c373e52c, 11:32Z the same
    day) - nine hours, not the three weeks an earlier version of this
    paragraph claimed. The duration is not the point and never was: nothing
    in the gap was going to end it except somebody noticing, and what ended
    it was a test rather than a person.
    """
    source = _read(PUBLISHED_CONDITIONS)
    found = re.findall(r"export const (PUBLISHED_\w+_KEY) = '(conditions/[^']+)'", source)
    assert found, (
        "Could not find any `export const PUBLISHED_..._KEY = 'conditions/...'` in "
        "publishedConditions.ts. If the declarations were restructured, fix the "
        "pattern here rather than leaving this matching nothing - an empty census "
        "passes silently, which is the failure this file exists to prevent."
    )
    return {key: f"publishedConditions.ts {name}" for name, key in found}


def client_background_archives() -> dict[str, str]:
    """config.ts's tier -> filename map. Not exported, so matched by name."""
    body = re.search(r"BACKGROUND_ARCHIVES[^=]*= \{(.*?)\n\}", _read(CONFIG), re.DOTALL)
    assert body is not None, "Could not find BACKGROUND_ARCHIVES in config.ts"
    return dict(re.findall(r"(\w+): '([^']+)'", body.group(1)))


def client_keys() -> dict[str, str]:
    """Every published key this build of the app can request, and what asks
    for it - the label is what turns a failure into a place to go."""
    config = _read(CONFIG)
    poi_format = client_poi_key_format()

    keys = {
        _string_const(config, "TRAILS_KEY"): "config.ts TRAILS_KEY",
        _string_const(config, "TRAILS_OVERVIEW_KEY"): "config.ts TRAILS_OVERVIEW_KEY",
        # The per-vertex miles beside the line (#1192). Optional on the phone,
        # like spurs.json - and the fallback when it is missing is the client
        # measuring the line itself, silently, which is exactly why a respelt
        # name here would never be noticed from a phone.
        _string_const(config, "TRAIL_MILES_KEY"): "config.ts TRAIL_MILES_KEY",
        _string_const(config, "SPURS_KEY"): "config.ts SPURS_KEY",
        _string_const(config, "ELEVATION_KEY"): "config.ts ELEVATION_KEY",
        # #831: the client started requesting the tombstones when it got a
        # card to draw them with. Listed here so a rename on either end is a
        # failing test rather than a 404 on a mountain.
        _string_const(config, "RETIRED_POI_KEY"): "config.ts RETIRED_POI_KEY",
        # The routes somebody wrote up (#1290). Optional on the phone like
        # spurs.json, and the client half shipped a release before any
        # exporter wrote it (#1284) - so a respelling on either end would
        # read as "nobody has published a route" for ever.
        _string_const(config, "SUGGESTED_HIKES_KEY"): "config.ts SUGGESTED_HIKES_KEY",
        # The corridor-view sketch of the other organizations' lines (#1135) -
        # what the opening camera draws so the whole network shows without
        # fetching the whole-file artifact, which no client declares a key
        # for since #1257 (the lines are tiles now, below). Published under
        # the licence gate, so the day-the-gate-opens argument applies to its
        # spelling: the contract is about the name, and the day the gate
        # opens is a bad day to discover the two ends spelled it differently.
        _string_const(config, "NETWORK_OVERVIEW_KEY"): "config.ts NETWORK_OVERVIEW_KEY",
        # The same lines as vector tiles (#1257), read by byte range through
        # map/networkTiles.ts rather than fetched whole. A respelling here is
        # the quietest failure in this file: the map asks a scheme for tiles
        # and every tile is a 404 that draws as "no network here".
        _string_const(config, "NEARBY_TRAILS_TILES_KEY"): "config.ts NEARBY_TRAILS_TILES_KEY",
        # Those tiles' coverage-cell index (#1257 stage 2), fetched by
        # lib/coverageCells.ts under its NETWORK_CELLS family. A respelling
        # is a stretch download that quietly carries no network.
        _string_const(config, "NEARBY_TRAILS_CELLS_KEY"): "config.ts NEARBY_TRAILS_CELLS_KEY",
        # The waypoints those same organizations publish (#1097). Unlike its
        # sibling above, this one is NOT held back today - DEC's and OPRHP's
        # POI sources ship on the same footing their trails do - so a spelling
        # drift here is a 404 on a mountain now rather than on the day a
        # licence answer lands.
        _string_const(config, "NEARBY_POI_KEY"): "config.ts NEARBY_POI_KEY",
        # The junction graph's cell index (#1257 stage 3), fetched by
        # lib/coverageCells.ts under its GRAPH_CELLS family - and the only
        # graph key the client declares as a constant. The cells themselves
        # are named per cell per half by `trailGraphCellKey`, read below by
        # client_graph_cell_keys; the whole-file graph and its three
        # companions are still published and no client asks for them.
        _string_const(config, "TRAIL_GRAPH_CELLS_KEY"): "config.ts TRAIL_GRAPH_CELLS_KEY",
    }

    # Every `conditions/` key the client declares, found rather than listed
    # (#1145). See client_conditions_keys.
    keys.update(client_conditions_keys())

    # The four halves of one graph cell, built the way the client builds
    # them. None is fetched at launch - the routing half arrives where the
    # hiker plans, the lines with the builder, the climb beside them, the
    # profile only when a chart opens - which is exactly why a rename would
    # go unnoticed here until somebody opened a day hike.
    keys.update(client_graph_cell_keys())

    for poi_type in client_poi_types():
        keys[poi_format.format(type=poi_type)] = f"config.ts poiKey('{poi_type}')"

    for tier, name in client_background_archives().items():
        keys[name] = f"config.ts BACKGROUND_ARCHIVES.{tier}"

    # `[Aa]rtifact` rather than `artifact`, so `demArtifact` is caught too.
    # The DEM became per-level with #1088 and its name moved out of packages.ts
    # into hikingDetail.ts beside the basemap cut's; a regex that only knew the
    # old spelling went on passing while it matched one artifact fewer, which
    # is the exact way this guard could rot without going red. What caught it
    # was test_this_is_actually_reading_the_client naming dem.pmtiles outright.
    for artifact in re.findall(r"[Aa]rtifact: '([^']+)'", _read(HIKING_DETAIL)):
        keys[artifact] = "hikingDetail.ts"

    for artifact in re.findall(r"[Aa]rtifact: '([^']+)'", _read(PACKAGES)):
        keys[artifact] = "packages.ts"

    return keys


GRAPH_CELL_HALVES = ("graph", "geometry", "elevation", "profile")


def client_graph_cell_keys(cell: str = "n41w075") -> dict[str, str]:
    """The four keys `trailGraphCellKey` builds for one cell, read from its two
    template literals rather than restated - a third copy of the spelling is
    the thing this file guards against. tests/test_cut_trail_graph.py holds
    the other end, that cut_trail_graph.cell_key spells them the same way."""
    source = _read(CONFIG)
    match = re.search(r"export function trailGraphCellKey\([^)]*\)[^{]*\{(.*?)\n\}", source, re.DOTALL)
    assert match, "config.ts no longer defines trailGraphCellKey where this test can read it"
    templates = re.findall(r"`([^`]+)`", match.group(1))
    assert len(templates) == 2, f"expected the graph template and the companions' template, found {templates}"
    graph_template, companion_template = templates
    keys = {}
    for half in GRAPH_CELL_HALVES:
        template = graph_template if half == "graph" else companion_template
        key = template.replace("${half}", half).replace("${name}", cell)
        assert "${" not in key, f"trailGraphCellKey's template has a placeholder this test does not fill: {template}"
        keys[key] = f"config.ts trailGraphCellKey('{cell}', '{half}')"
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
    # The per-vertex miles, the same way (#1192, export_trails.write_trail_miles).
    trails_manifest["miles"] = manifest_entry("trail_miles.json")
    (tmp_path / "trails_manifest.json").write_text(json.dumps(trails_manifest))

    poi_dir = tmp_path / "poi"
    poi_dir.mkdir()
    (poi_dir / "manifest.json").write_text(
        json.dumps(
            {poi_type: {kind: manifest_entry(f"{poi_type}.{kind}") for kind in ("geojson", "fgb")} for poi_type in POI_TYPES}
        )
    )

    (tmp_path / "elevation_manifest.json").write_text(json.dumps(manifest_entry("elevation_profile.json")))
    # The suggested hikes (#1290): one manifest, one root artifact, the
    # shape highlights_manifest.json takes.
    (tmp_path / "suggested_hikes_manifest.json").write_text(json.dumps(manifest_entry("suggested_hikes.json")))
    (tmp_path / "spurs_manifest.json").write_text(json.dumps(manifest_entry("spurs.json")))
    # The tombstones (#673). This fixture is "one of every artifact" and was
    # missing this one, so the key looked unpublished the moment the client
    # started asking for it (#831) - publish.collect_artifacts has emitted it
    # since #673.
    (tmp_path / "retired_poi_manifest.json").write_text(json.dumps(manifest_entry("retired_poi.geojson")))
    # The nearby-trail network (#950), and the ONE artifact in this fixture
    # whose manifest has to say something beyond a path and a hash: publish.py
    # refuses to upload it while any source in it carries
    # `reaches_hikers: false`, which every source in the real registry does
    # today. So this fixture states the post-licence world deliberately.
    #
    # That is not the fixture dodging the gate - the gate has its own tests in
    # test_publish.py, both directions. It is this file answering the question
    # it exists to answer, which is whether the two ends agree on the NAME. A
    # fixture that left the sources held back would make this key look
    # unpublished for a reason that has nothing to do with spelling, and the
    # file's own docstring names that as the failure mode ("a run that
    # happened to skip an export would answer 'that key is not published' for
    # a reason that has nothing to do with whether the two ends agree").
    nearby = manifest_entry("nearby_trails.geojson")
    nearby["sources"] = {"oprhp_trails": {"reaches_hikers": True}}
    # The corridor-view sketch riding the same manifest (#1135), the way the
    # A.T.'s overview rides trails_manifest.json above.
    nearby["overview"] = manifest_entry("network_overview.geojson")
    # The vector tiles of the same lines (#1257), the third file the one
    # decision publishes.
    nearby["tiles"] = manifest_entry("nearby_trails.pmtiles")
    (tmp_path / "nearby_trails_manifest.json").write_text(json.dumps(nearby))
    # Those tiles' coverage cells (#1257 stage 2): cut_cells.py's own manifest
    # for the nearby_trails family, which publish.py collects inside the
    # nearby gate above. One cell, because the question is the index's name.
    (tmp_path / "nearby_trails_cells_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "nearby_trails_cells.json": manifest_entry("nearby_trails_cells.json"),
                    "nearby_trails_cell_n41w075.pmtiles": manifest_entry("nearby_trails_cell_n41w075.pmtiles"),
                }
            }
        )
    )

    # The nearby waypoints (#1097), through the same reaches_hikers gate as the
    # lines above. Stated here as shipping because that is what the real
    # registry now says - `dec_lean_tos` and the rest carry reaches_hikers true
    # on `dec_licence`'s footing, and `oprhp_facilities` flipped when this
    # export started reading it - so unlike its sibling this is the present
    # world rather than a post-licence one.
    nearby_poi = manifest_entry("nearby_poi.geojson")
    nearby_poi["sources"] = {"dec_lean_tos": {"reaches_hikers": True}}
    (tmp_path / "nearby_poi_manifest.json").write_text(json.dumps(nearby_poi))

    # The junction graph derived from those lines (#974). Same post-licence
    # framing as its parent above, for the same reason: this file asks whether
    # the two ends agree on the NAME, and the gate has its own tests.
    graph = manifest_entry("trail_graph.json")
    graph["sources"] = {"oprhp_trails": {"reaches_hikers": True}}
    geometry_entry = manifest_entry("trail_graph_geometry.json")
    graph["geometry_path"] = geometry_entry["path"]
    graph["geometry_sha256"] = geometry_entry["sha256"]
    (tmp_path / "trail_graph_manifest.json").write_text(json.dumps(graph))

    # The climb along each edge (#1011) and the dense profile a chart draws
    # from (#1045). Separate manifests because a publish can legitimately run
    # without either - both are gated on `include_elevation` in the workflow -
    # and the same post-licence framing as their parents above, for the same
    # reason: the question here is whether the two ends agree on the NAME.
    for name in ("trail_graph_elevation", "trail_graph_profile"):
        entry = manifest_entry(f"{name}.json")
        entry["sources"] = {"oprhp_trails": {"reaches_hikers": True}}
        (tmp_path / f"{name}_manifest.json").write_text(json.dumps(entry))

    # The graph cut per cell (#1257 stage 3): cut_trail_graph.py's own manifest,
    # collected inside the graph's gate above. One cell in all four halves,
    # because the question is the names - the index's and the halves'.
    (tmp_path / "trail_graph_cells_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "trail_graph_cells.json": manifest_entry("trail_graph_cells.json"),
                    "trail_graph_cell_n41w075.json": manifest_entry("trail_graph_cell_n41w075.json"),
                    "trail_graph_geometry_cell_n41w075.json": manifest_entry("trail_graph_geometry_cell_n41w075.json"),
                    "trail_graph_elevation_cell_n41w075.json": manifest_entry("trail_graph_elevation_cell_n41w075.json"),
                    "trail_graph_profile_cell_n41w075.json": manifest_entry("trail_graph_profile_cell_n41w075.json"),
                }
            }
        )
    )

    conditions_dir = tmp_path / "conditions"
    conditions_dir.mkdir()
    # export_conditions.py's four documents, all from one read of one database
    # (see its `written` list). Only closures and reports were here until
    # #1145, so `notes` and `disputes` looked unpublished the moment the
    # census stopped naming three keys by hand.
    (tmp_path / "conditions_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    kind: manifest_entry(f"conditions/{kind}.json") for kind in ("closures", "reports", "notes", "disputes")
                }
            }
        )
    )
    # The four that carry their own manifest, from their own exporter, rather
    # than riding export_conditions.py's - the legs run under different
    # conditions and each rewrites its manifest whole (see publish.py's
    # conditions block, and CONDITIONS_MANIFESTS for what forgetting one
    # costs). Built from that tuple rather than listed, so a fifth leg is
    # covered by this fixture the day publish.py learns to collect it.
    for manifest_name in publish.CONDITIONS_MANIFESTS:
        if manifest_name == "conditions_manifest.json":
            continue
        payload = manifest_name.removesuffix("_manifest.json")
        (tmp_path / manifest_name).write_text(json.dumps({"artifacts": {payload: manifest_entry(f"conditions/{payload}.json")}}))

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
