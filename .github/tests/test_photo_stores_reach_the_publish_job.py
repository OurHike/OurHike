"""Every local photo store the publisher reads is carried to the job that
publishes (#1550).

THE FAILURE THIS EXISTS TO CATCH is silent by construction.
`publish.py`'s `collect_photos()` reads an ABSENT store as an empty one - it
has to, because a run without `include_photos` legitimately has no photos -
so a handoff that stops carrying a store does not fail, does not warn, and
publishes every other artifact exactly as before. The only visible symptom is
a card with no picture on it, weeks later, which is also what "nobody has
confirmed one yet" looks like.

It is a two-file invariant, which is why no single file can hold it.
`publish-vector-data.yml` builds in one job and publishes in another (#1265),
so a store on the build runner reaches the publisher only if the handoff
artifact names it. `poi_photos/` has been named since the split;
`wayback_photos/` was added with the store itself, and the next store added
will be a fresh chance to forget.

WHAT THIS CHECKS AND WHAT IT DOES NOT. It reads the DIRECTORY NAMES
`publish.py` joins onto `RAW_DIR`, so a store is discovered by the code that
reads it rather than by a list kept here that could go stale. It does not
check that the store has any bytes in it, or that anything uploads them - the
first is a property of a run, and the second is `verify_photo_promises()`'
job, which fails a publish loudly when a referenced key exists in neither the
local store nor the bucket.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "pipeline"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-vector-data.yml"

#: The artifact the build job hands the publish job. Named rather than
#: discovered: this test is about one specific handoff, and a second artifact
#: appearing in this workflow would be a different question.
HANDOFF_ARTIFACT = "vector-data-build-output"

#: Where `publish.py` finds the constants it joins onto `RAW_DIR`. Two files
#: because `PHOTOS_DIRNAME` is `lib/photo_store.py`'s - it names the store
#: every photo source writes into - while `ARCHIVE_STORE_DIRNAME` is
#: `publish.py`'s own, spelled there so a publisher does not import a fetcher.
CONSTANT_SOURCES = (PIPELINE / "publish.py", PIPELINE / "lib" / "photo_store.py")


def _store_constants() -> set[str]:
    """Every `RAW_DIR / <CONSTANT>` in publish.py, as constant names.

    A directory joined onto RAW_DIR is a local store this publisher reads.
    Matching the join rather than the constant's spelling is what keeps this
    honest when a third store is added: it is discovered the moment
    publish.py reads it, with no list here to update.
    """
    source = (PIPELINE / "publish.py").read_text(encoding="utf-8")
    return set(re.findall(r"RAW_DIR / ([A-Z][A-Z0-9_]*DIRNAME)", source))


def _resolve(constant: str) -> str:
    for path in CONSTANT_SOURCES:
        found = re.search(rf'^{constant} = "([^"]+)"', path.read_text(encoding="utf-8"), re.MULTILINE)
        if found:
            return found.group(1)
    raise AssertionError(f"{constant} is joined onto RAW_DIR in publish.py but defined in neither {CONSTANT_SOURCES}")


def _handoff_paths() -> list[str]:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in (document.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            uses, with_ = str(step.get("uses") or ""), step.get("with") or {}
            if uses.startswith("actions/upload-artifact") and with_.get("name") == HANDOFF_ARTIFACT:
                return [line.strip() for line in str(with_.get("path") or "").splitlines() if line.strip()]
    raise AssertionError(f"{WORKFLOW.name} uploads no artifact named {HANDOFF_ARTIFACT}")


def test_publish_reads_at_least_the_two_photo_stores_this_test_was_written_for():
    """A guard on the discovery itself. `_store_constants` finds stores by
    matching source text, so a refactor that spelled the join differently
    would make every assertion below vacuously true - this fails instead."""
    assert {"PHOTOS_DIRNAME", "ARCHIVE_STORE_DIRNAME"} <= _store_constants()


def test_every_photo_store_publish_reads_is_named_in_the_handoff_artifact():
    paths = _handoff_paths()
    for constant in sorted(_store_constants()):
        directory = _resolve(constant)
        wanted = f"pipeline/data/raw/{directory}/"
        assert wanted in paths, (
            f"publish.py reads data/raw/{directory} ({constant}), and the {HANDOFF_ARTIFACT} handoff "
            f"does not carry it - the publish job would find that store empty and say nothing. "
            f"Add {wanted} to the upload's path list. Carried today: {paths}"
        )
