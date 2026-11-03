"""publish-vector-data.yml's "from the published data" restores read the folder the run publishes into.

Two steps refill a cold fetch cache from what the last publish left in the
bucket: "Restore derived water data from the published data" and "Restore
photo outcomes from the published data". A publish writes under
`environments/<data_environment>/`, never the bucket root.

WHAT GETTING IT WRONG COST (#1850). Both steps read
`${DATA_BASE_URL%/}/$name`, the root, where every one of their five files
answers 404 (Measured 2026-10-18 against data.ourhike.org; the same names
under `environments/ua/` answer 200). Branch runs hit the fetch cache and
never noticed. Run 170, the first UA publish from `main` after #1805, missed
the cache, restored nothing, and spent 2 h 04 min re-fetching ATC's photos
that the warm run 169 skipped in 0 s. It was cancelled at 2 h 24 min, still
fetching, against a 180-minute job limit.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-vector-data.yml"

RESTORE_STEPS = (
    "Restore derived water data from the published data",
    "Restore photo outcomes from the published data",
)


def _steps_by_name() -> dict[str, dict]:
    doc = yaml.safe_load(WORKFLOW.read_text())
    return {step.get("name"): step for step in doc["jobs"]["build"]["steps"]}


def test_each_published_data_restore_reads_its_own_environment_folder() -> None:
    steps = _steps_by_name()
    for name in RESTORE_STEPS:
        step = steps[name]
        assert step["env"]["DATA_ENVIRONMENT"] == "${{ inputs.data_environment }}", name
        assert '"${DATA_BASE_URL%/}/environments/${DATA_ENVIRONMENT}/$name"' in step["run"], name


def test_no_published_data_restore_reads_the_bucket_root() -> None:
    steps = _steps_by_name()
    for name in RESTORE_STEPS:
        assert '"${DATA_BASE_URL%/}/$name"' not in steps[name]["run"], name
