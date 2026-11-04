"""Every install of backend/requirements-archive.txt checks a sha256 for every file.

The 2026-11-04 security review: analytics-rollup.yml's `ua` and `production` jobs install this file, and the packages it
installs are imported by the steps that hold the usage archive's R2 write keys and the analytics databases' URLs
(`scripts/analytics_archive.py`, `analytics_rollup.py`, `analytics_quality.py`). It carried `==` pins and no hashes,
while the pipeline's dbt and extract installs, which run beside keys of the same kind, are hash-pinned
(test_dbt_install_is_hash_pinned.py, test_extract_install_is_hash_pinned.py). It takes both parts below, because
either alone fails open (test_dbt_install_is_hash_pinned.py has the measurement, on pip 24.0):

- requirements-archive.txt lists `--hash=sha256:` under every pin, compiled with --generate-hashes. pip switches hash
  checking on by itself only when a file lists some hash, so a recompile without the flag would install unchecked.
- every step that installs the file passes --require-hashes, so a file that lost its hashes stops the install instead.

And a third, because --require-hashes checks only what pip downloads: every such step passes --only-binary=:all: too.
The file lists sdist hashes beside the wheels', so a pin with no wheel for the job's interpreter - a bump that lands
before its wheels, or a `python-version` that moves on - would build its sdist, and pip fills that build's environment
(setuptools, Cython, maturin) with no pin and no hash, under --require-hashes as well (requirements-dbt-build.in has
that measurement, on pip 24.0). With the flag, a missing wheel fails the install instead. Nothing is lost today:
`pip download --require-hashes --only-binary=:all:` for CPython 3.14 on manylinux x86_64, the jobs' interpreter,
fetched a wheel for each of the 42 pins whose markers apply there (measured 2026-11-04 with pip 24.0; colorama and
tzdata are Windows-only).
"""

from __future__ import annotations

import re
from pathlib import Path

import hash_pins

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "backend" / "requirements-archive.txt"

#: A command that runs pip's install on the file, quoted venv paths included.
INSTALLS_ARCHIVE = re.compile(r"\bpip3?\"?\s+install\b[^\n]*\brequirements-archive\.txt\b")

#: Every file under .github that installs requirements-archive.txt today, with how many times. A new install must join
#: this list, so a scan that stops matching fails rather than passing on nothing.
INSTALL_SITES = {
    # The `ua` and `production` jobs, one install each.
    "workflows/analytics-rollup.yml": 2,
}

#: What every install of the file passes: the hash check, and wheels only, so no sdist build fetches unhashed tools.
REQUIRED_FLAGS = ("--require-hashes", "--only-binary=:all:")


def test_every_pin_in_requirements_archive_lists_a_sha256():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "--generate-hashes" in text.splitlines()[1], "the header's own command compiles with --generate-hashes"
    pins = hash_pins.pins(text)
    assert len(pins) >= 40, "the file's pins were found"
    assert any(pin.startswith("pyarrow==") for pin in pins), "the one package only the archive needs is still in it"
    unhashed = [pin.split()[0] for pin in pins if not re.search(r"--hash=sha256:[0-9a-f]{64}\b", pin)]
    unpinned = [pin.split()[0] for pin in pins if not re.match(r"^[A-Za-z0-9_.-]+==[^\s=;]+(\s|$)", pin)]
    assert unhashed == []
    assert unpinned == [], "--require-hashes refuses a requirement that is not pinned with =="


def test_every_install_of_requirements_archive_requires_hashes():
    installs = hash_pins.installs_of(INSTALLS_ARCHIVE)
    assert {site: len(commands) for site, commands in installs.items()} == INSTALL_SITES
    missing = [
        (site, flag, command.strip())
        for site, commands in installs.items()
        for command in commands
        for flag in REQUIRED_FLAGS
        if flag not in command.split()
    ]
    assert missing == []
