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
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"
WEATHER = WORKFLOWS / "publish-weather.yml"
CONDITIONS = WORKFLOWS / "publish-conditions.yml"
PATHS = [
    "pipeline/data/raw/closure_trail_lines/lines.parquet",
    "pipeline/data/raw/closure_trail_lines/release.json",
]
PREFIX = "closure-trail-lines-"


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
