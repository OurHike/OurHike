"""The client's release pin, checked against the pipeline that fills it (#1333).

`client/src/lib/dataRelease.ts` decides where the client fetches each key
from. This pipeline decides where each key is written. Nothing at either end
can see the other, so the agreement between them is exactly the kind that
drifts silently - and drifts into a 404 on a mountain rather than a test
failure.

So this reads the TypeScript, the same way `verify_release.expected_client_keys`
already reads `config.ts`'s key contract, and asserts the two ends still say
the same thing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import verify_release
from lib import r2_keys, releases

DATA_RELEASE_TS = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "dataRelease.ts"


@pytest.fixture(scope="module")
def source() -> str:
    return DATA_RELEASE_TS.read_text()


def _pin(source: str) -> str:
    match = re.search(r"^export const DATA_RELEASE = '([^']+)'$", source, re.MULTILINE)
    assert match, (
        "could not read DATA_RELEASE out of client/src/lib/dataRelease.ts. It has been "
        "restructured, and this check - and pages.yml's guard, which greps the same line - "
        "must be updated rather than left matching nothing."
    )
    return match.group(1)


def _root_scoped(source: str) -> tuple[list[str], list[str]]:
    prefixes = re.search(r"ROOT_SCOPED_PREFIXES = \[([^\]]*)\]", source)
    keys = re.search(r"ROOT_SCOPED_KEYS = \[([^\]]*)\]", source)
    assert prefixes and keys, "could not read the root-scoped lists out of dataRelease.ts"
    return re.findall(r"'([^']+)'", prefixes.group(1)), re.findall(r"'([^']+)'", keys.group(1))


def test_the_pin_is_an_id_a_publish_could_have_written(source):
    """A pin that r2_keys would reject names a folder no publish can create,
    so the guard in pages.yml would fail every deploy forever."""
    assert r2_keys.RELEASE_ID_PATTERN.match(_pin(source))


def test_every_key_the_client_declares_is_release_scoped(source):
    """The two contracts have to line up on the same keys.

    `verify_release.expected_client_keys()` is what the client says it will
    fetch; `dataRelease.ts` is where it will fetch each one from. A declared
    key the client treats as root-scoped would be requested from the bucket
    root while publish.py files it under the release folder - and since
    publish.py still writes the flat keys too, it would 404 only once those
    are finally frozen, which is the worst possible time to find out.
    """
    prefixes, root_keys = _root_scoped(source)
    misfiled = [
        key
        for key in verify_release.expected_client_keys()
        if key in root_keys or any(key.startswith(prefix) for prefix in prefixes)
    ]
    assert not misfiled, f"declared client keys that dataRelease.ts sends to the bucket root: {misfiled}"


def test_conditions_are_excluded_at_both_ends(source):
    """The one exclusion both sides must agree on.

    lib/releases.is_release_artifact keeps `conditions/` out of every release
    folder because safety data is rewritten in place and a reopened closure
    must stop being served. If the client asked for it under the pin it would
    read a folder that structurally never contains it - no closures, no
    warnings, no field notes, and no error either.
    """
    prefixes, _ = _root_scoped(source)

    assert "conditions/" in prefixes
    assert releases.is_release_artifact("conditions/closures.json") is False
    assert releases.is_release_artifact("trails.geojson") is True


def test_the_client_excludes_more_than_the_pipeline_does_and_that_is_correct(source):
    """`photos/` and `latest.json` are root-scoped on the client and are NOT
    excluded by is_release_artifact - which is agreement, not drift.

    Neither ever reaches that function: photos are uploaded by
    `upload_photos` and never enter `manifest["artifacts"]`, and `latest.json`
    is the pointer rather than an artifact. The pipeline has no opinion
    because it never sees them; the client needs one because it fetches them.
    Pinned so that a later reader does not "fix" the asymmetry by adding them
    to the Python, where they would do nothing.
    """
    prefixes, root_keys = _root_scoped(source)

    assert "photos/" in prefixes
    assert "latest.json" in root_keys
    assert releases.is_release_artifact("photos/abc.jpg") is True
    assert releases.is_release_artifact("latest.json") is True


def test_the_root_scoped_lists_stay_short(source):
    """A closed set, and small enough that growing it is a decision.

    The rule is an exclusion so that a new artifact is versioned by default
    (lib/releases.is_release_artifact's own reasoning). That property is only
    worth anything while the exclusion list is something a reader can hold in
    their head - this fails on the fourth prefix, which is the moment to ask
    whether the rule has stopped being an exclusion.
    """
    prefixes, root_keys = _root_scoped(source)

    assert sorted(prefixes) == ["conditions/", "photos/"]
    assert root_keys == ["latest.json"]
