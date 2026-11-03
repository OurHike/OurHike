"""The fields the publication rule reads are unchanged by the move of the extract into sources.json.

When every org's reads moved from pipeline/extract/<org>/*.py into the registry, each sources.json row gained an
`extract` field and new `notes`, and nothing else was meant to change. int_sources__publication.sql matches each row's
`licence`, `licence_basis` and `reaches_hikers` against seeds/licence_restriction_answers.csv and
seeds/publishable_licence_bases.csv, so an edit to any of them, even to the wording of `licence`, can stop a source
publishing. This compares those three fields with the commit before the move, 293f8ada, row by row.

It skips where git or that commit is not available (a shallow clone), and it stops being useful once a later change
edits a licence on purpose: then update BASE or delete this file in that change.
"""

import json
import subprocess

import pytest

from extract._contract import PIPELINE_DIR, REGISTRY_PATH

BASE = "293f8ada"
PUBLICATION_FIELDS = ("licence", "licence_basis", "reaches_hikers")


def _base_registry() -> dict:
    try:
        text = subprocess.run(
            ["git", "show", f"{BASE}:pipeline/sources.json"],
            cwd=PIPELINE_DIR,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip(f"git cannot show {BASE}:pipeline/sources.json here (a shallow clone?)")
    return {row["key"]: row for row in json.loads(text)["sources"]}


def test_the_fields_the_publication_rule_reads_are_unchanged_since_the_extract_moved_into_the_registry():
    base = _base_registry()
    now = {row["key"]: row for row in json.loads(REGISTRY_PATH.read_text())["sources"]}
    changed = sorted(
        f"{key}.{field}"
        for key, row in base.items()
        if key in now
        for field in PUBLICATION_FIELDS
        if row.get(field) != now[key].get(field)
    )
    assert not changed, f"publication fields changed since {BASE}: {changed}"
