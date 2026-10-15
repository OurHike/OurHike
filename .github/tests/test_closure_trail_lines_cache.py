"""The release's nearby trail lines reach the hourly cut of area closures through one cache, written in one place.

Decision 187 (S6, the maintainer's poll of 2026-10-11) crosses out an area
closure's trails where they run inside it, in conditions/trail_closures.json,
and the hourly conditions build cuts them. Its lines are the release's nearby
trail lines, which publish-weather.yml prepares once per release
(pipeline/prepare_closure_trail_lines.py) and caches under the release's id,
and publish-conditions.yml restores before the build, as the weather squares
go between the same two jobs. Nothing at runtime says when that hand-over
breaks: actions/cache finds an entry by its paths as well as its key, so a
path changed on one side alone leaves the restore green and empty every
hour, and the area closures quietly stop being drawn. This holds the two
sides to one another.

And to the script's SCHEMA. The conditions job restores the newest entry
whose key starts with its restore-keys prefix, so a prefix that does not name
the schema restores an entry written to an older rule until a new one is
saved: under SCHEMA 1 the lines held no A.T. line, and an hour cut against
one would leave the A.T. open where decision 192 crosses it out. Naming the
schema in both keys makes a schema bump a new prefix, which the old entries
cannot match.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
WEATHER = WORKFLOWS / "publish-weather.yml"
CONDITIONS = WORKFLOWS / "publish-conditions.yml"
SCRIPT = REPO / "pipeline" / "prepare_closure_trail_lines.py"
PATHS = [
    "pipeline/data/raw/closure_trail_lines/lines.parquet",
    "pipeline/data/raw/closure_trail_lines/release.json",
]
#: prepare_closure_trail_lines.py's SCHEMA, read from its text: this suite does not import pipeline/.
SCHEMA = int(re.search(r"^SCHEMA = (\d+)$", SCRIPT.read_text(encoding="utf-8"), re.MULTILINE).group(1))
PREFIX = f"closure-trail-lines-v{SCHEMA}-"


def _steps(workflow: Path, job: str) -> list[dict]:
    return yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"][job]["steps"]


def _caching(steps: list[dict]) -> list[dict]:
    return [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/cache") and PREFIX in str((step.get("with") or {}).get("key", ""))
    ]


def _paths(step: dict) -> list[str]:
    return str(step["with"]["path"]).split()


def test_the_weather_job_looks_up_and_saves_one_key_over_the_paths_the_conditions_job_restores():
    lookup, save = _caching(_steps(WEATHER, "build"))
    (restore,) = _caching(_steps(CONDITIONS, "publish"))

    assert lookup["uses"].startswith("actions/cache/restore") and lookup["with"].get("lookup-only") is True
    assert save["uses"].startswith("actions/cache/save")
    assert _paths(lookup) == _paths(save) == _paths(restore) == PATHS
    assert lookup["with"]["key"] == save["with"]["key"]
    assert save["with"]["key"].startswith(f"{PREFIX}ua-"), "the weather job prepares UA's release, and says so in the key"
    assert restore["with"]["restore-keys"] == PREFIX + "${{ matrix.data_environment }}-", (
        "each conditions leg restores its own environment's newest entry, never another environment's lines"
    )


def test_every_key_on_either_side_names_the_scripts_schema():
    """No step of either workflow keys the lines without the schema, so none can restore or save an older one's."""
    for workflow, job in ((WEATHER, "build"), (CONDITIONS, "publish")):
        for step in _steps(workflow, job):
            settings = step.get("with") or {}
            for field in ("key", "restore-keys"):
                value = str(settings.get(field, ""))
                if "closure-trail-lines" in value:
                    assert value.startswith(PREFIX), f"{workflow.name}: {step['name']}'s {field} {value!r}"


def test_the_conditions_job_restores_the_lines_on_the_dbt_path_before_the_build_and_never_saves_them():
    steps = _steps(CONDITIONS, "publish")
    (restore,) = _caching(steps)
    build = next(position for position, step in enumerate(steps) if step.get("id") == "build")

    assert restore["uses"].startswith("actions/cache/restore")
    assert steps.index(restore) < build
    assert restore.get("if") == "env.PHONE_FILES == 'dbt'"


def test_preparing_the_lines_never_delays_or_stops_a_forecast():
    """After the upload the publish job reads, and allowed to fail: a release whose lines cannot be prepared leaves the
    last release's entry for the conditions job, and the forecast goes out as it would have."""
    steps = _steps(WEATHER, "build")
    upload = next(position for position, step in enumerate(steps) if step.get("id") == "upload")
    lines = [
        position
        for position, step in enumerate(steps)
        if "prepare_closure_trail_lines.py" in str(step.get("run", "")) or step in _caching(steps)
    ]

    assert len(lines) == 4, "the release's id, the lookup, the preparation and the save"
    assert min(lines) > upload
    for position in lines:
        step = steps[position]
        if "run" in step:
            assert step.get("continue-on-error") is True and step.get("timeout-minutes"), step["name"]
