"""Every install of pipeline/requirements-extract.txt checks a sha256 for every file.

The maintainer, 2026-10-11: the extract's venv runs in jobs that hold the raw store's write keys, the hourly legs among
them, so its install is hash-pinned, as the dbt install is.
It takes both parts below, because either alone fails open (test_dbt_install_is_hash_pinned.py has the measurement):

- requirements-extract.txt lists `--hash=sha256:` under every pin, compiled with --generate-hashes. pip switches hash
  checking on by itself only when a file lists some hash, so a recompile without the flag would install unchecked.
- every step that installs the file passes --require-hashes, so a file that lost its hashes stops the install instead.

No build environment to pin, unlike dbt's: every one of the file's 62 pins installed as a wheel on Python 3.12 with
--only-binary=:all: (Measured 2026-10-11), so pip builds nothing from an sdist here.
"""

from __future__ import annotations

import re
from pathlib import Path

import hash_pins

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "pipeline" / "requirements-extract.txt"

#: A command that runs pip's install on the file, quoted venv paths included (`"$RUNNER_TEMP/extract/bin/pip" install`).
INSTALLS_EXTRACT = re.compile(r"\bpip3?\"?\s+install\b[^\n]*\brequirements-extract\.txt\b")

#: Every file under .github that installs requirements-extract.txt today, with how many times. A new install must join
#: this list, so a scan that stops matching fails rather than passing on nothing.
INSTALL_SITES = {
    # The build and parity jobs, and the retention step (pipeline/prune_raw_store.py).
    "workflows/build-reference.yml": 3,
    "workflows/check-conditions.yml": 2,
    "workflows/extract-notices.yml": 1,
    "workflows/pipeline-tests.yml": 1,
    "workflows/publish-conditions.yml": 1,
    "workflows/purge-person-fields.yml": 1,
    "workflows/refresh-reference.yml": 2,
    "actions/dbt-docs-site/action.yml": 1,
}


def test_every_pin_in_requirements_extract_lists_a_sha256():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "--generate-hashes" in text.splitlines()[1], "the header's own command compiles with --generate-hashes"
    pins = hash_pins.pins(text)
    assert len(pins) >= 60, "the file's pins were found"
    unhashed = [pin.split()[0] for pin in pins if "--hash=sha256:" not in pin]
    assert unhashed == []


def test_every_install_of_requirements_extract_requires_hashes():
    installs = hash_pins.installs_of(INSTALLS_EXTRACT)
    assert {site: len(commands) for site, commands in installs.items()} == INSTALL_SITES
    missing = [
        (site, command.strip())
        for site, commands in installs.items()
        for command in commands
        if "--require-hashes" not in command
    ]
    assert missing == []
