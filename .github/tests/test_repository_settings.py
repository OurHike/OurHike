"""Tests that this repository's GitHub Actions settings are what its workflows
expect to find.

Two halves, and the split is forced rather than chosen:

**What a checkout can answer** - whether `.github/expected-settings.yml` and
`.github/workflows/` still agree with each other. Runs anywhere, including on
a pull request from a fork, and needs access to nothing.

**What only Actions can answer** - whether those settings are actually
configured. A secret's value is write-only once set; the API will not read one
back and neither will the maintainer who set it. The only process that can see
whether `R2_SECRET_ACCESS_KEY` exists is a job running in this repository, so
`settings-configured.yml` resolves the `secrets` and `vars` contexts, reduces them
to the *names* that came back non-empty, and hands those here through the
environment. Values never enter this process, which is why nothing below has
to be careful about printing them - there is nothing here to print.

The live half skips when that environment is absent, which is every local run.
`test_the_live_check_is_not_silently_skipping_where_it_is_meant_to_run` stops
the skip from reading as a pass in the one place where the difference matters.
"""

from __future__ import annotations

import json
import os
import re
import warnings
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / ".github" / "expected-settings.yml"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# `${{ secrets.FOO }}`, and the same names in `if:` conditions, which carry no
# ${{ }}. It deliberately does not match `toJSON(secrets)` - no dot follows -
# which is why settings-configured.yml enumerates the settings that way rather than
# naming any of them, so that the workflow doing the checking does not read as
# a workflow expecting a setting called `toJSON`.
REFERENCE = re.compile(r"\b(secrets|vars)\.([A-Za-z_][A-Za-z0-9_]*)")

# GitHub normalises setting names to upper case and matches them
# case-insensitively; `github_token` comes back from toJSON(secrets) lower.
# Everything here is compared upper so those never look like two settings.
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

CONTEXT_FOR = {"secret": "secrets", "variable": "vars", "github-provided": "secrets"}
TAB_FOR = {"secret": "Secrets", "variable": "Variables"}

SETTINGS = {name.upper(): spec for name, spec in yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))["settings"].items()}


def _strings(node):
    """Every string anywhere in a parsed workflow, keys included.

    Parsing rather than scanning the raw text is what keeps a comment that
    mentions `secrets.SOMETHING` from registering as a workflow that reads it -
    and it fails loudly on a workflow that is not valid YAML, which is worth
    having on its own.
    """
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(key)
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)


def _workflows():
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def _references():
    """Every (context, NAME, workflow filename) any workflow reads."""
    found = []
    for path in _workflows():
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        for text in _strings(parsed):
            for context, name in REFERENCE.findall(text):
                found.append((context, name.upper(), path.name))
    return found


def _configured(variable):
    """The names settings-configured.yml found configured, or None if this is not
    the live job."""
    raw = os.environ.get(variable)
    if not raw:
        return None
    return {str(name).upper() for name in json.loads(raw)}


CONFIGURED_SECRETS = _configured("CONFIGURED_SECRETS")
CONFIGURED_VARIABLES = _configured("CONFIGURED_VARIABLES")

live = pytest.mark.skipif(
    CONFIGURED_SECRETS is None or CONFIGURED_VARIABLES is None,
    reason="Only a job running in this repository can see which settings are configured - see settings-configured.yml.",
)


def _is_a_name(item):
    return isinstance(item, str) and bool(NAME.match(item))


def _first_sentence(text):
    """Enough of a `why` to act on in a failure email, without pasting the
    whole paragraph the manifest is there to hold."""
    collapsed = " ".join(str(text).split())
    head, _, _ = collapsed.partition(". ")
    return head.rstrip(".") + "."


def _acceptable_tabs(spec):
    tabs = {spec["where"]}
    if spec.get("also-accepted-as-secret"):
        tabs.add("secret")
    return tabs


def _actual_tabs(name):
    found = set()
    if name in (CONFIGURED_SECRETS or set()):
        found.add("secret")
    if name in (CONFIGURED_VARIABLES or set()):
        found.add("variable")
    return found


# --- What a checkout can answer -------------------------------------------


def test_the_manifest_declares_a_home_and_a_reason_for_every_setting():
    malformed = []
    for name, spec in sorted(SETTINGS.items()):
        if not isinstance(spec, dict):
            malformed.append(f"{name}: not a mapping")
            continue
        if spec.get("where") not in CONTEXT_FOR:
            malformed.append(f"{name}: where must be one of {sorted(CONTEXT_FOR)}, got {spec.get('where')!r}")
        if not isinstance(spec.get("required"), bool):
            malformed.append(f"{name}: required must be true or false, got {spec.get('required')!r}")
        if not str(spec.get("why", "")).strip():
            malformed.append(f"{name}: needs a why - what breaks when it is missing")
    assert not malformed, "expected-settings.yml entries are malformed:\n  " + "\n  ".join(malformed)


def test_every_setting_a_workflow_reads_is_declared():
    undeclared = sorted({(name, workflow) for _, name, workflow in _references() if name not in SETTINGS})
    assert not undeclared, (
        "These workflows read a setting that expected-settings.yml does not declare, so nothing checks that it is "
        "configured:\n  " + "\n  ".join(f"{name} in {workflow}" for name, workflow in undeclared)
    )


def test_every_declared_setting_is_read_by_some_workflow():
    read = {name for _, name, _ in _references()}
    unused = sorted(name for name in SETTINGS if name not in read)
    assert not unused, (
        "expected-settings.yml declares settings no workflow reads any more. Delete the entry, and delete the setting "
        "itself if nothing else wants it - a credential kept past its last use is one nobody thinks to rotate:\n  "
        + "\n  ".join(unused)
    )


def test_each_setting_is_read_from_the_context_it_is_declared_for():
    wrong = []
    for context, name, workflow in sorted(set(_references())):
        spec = SETTINGS.get(name)
        if spec is None:
            continue  # its own test above
        allowed = {CONTEXT_FOR[tab] for tab in _acceptable_tabs(spec)}
        if context not in allowed:
            wrong.append(f"{workflow} reads {context}.{name}, but it is declared as {spec['where']}")
    assert not wrong, (
        "A workflow reads a setting from the wrong context. GitHub resolves the wrong one to an empty string rather "
        "than an error, so this fails as missing configuration somewhere far away:\n  " + "\n  ".join(wrong)
    )


# --- What only Actions can answer -----------------------------------------


@live
def test_every_required_setting_is_configured():
    missing = []
    for name, spec in sorted(SETTINGS.items()):
        if spec["where"] == "github-provided" or not spec["required"]:
            continue
        if not _acceptable_tabs(spec) & _actual_tabs(name):
            tabs = " or ".join(sorted(TAB_FOR[tab] for tab in _acceptable_tabs(spec)))
            missing.append(f"{name} - expected on the {tabs} tab. {_first_sentence(spec['why'])}")
    assert not missing, (
        "Settings -> Secrets and variables -> Actions is missing something every workflow that needs it will fail on. "
        "LAUNCH_CHECKLIST.md steps 1.3 and 2 are the instructions:\n  " + "\n  ".join(missing)
    )


@live
def test_a_setting_meant_for_the_variables_tab_is_not_also_kept_as_a_secret():
    """A warning, not a failure: a duplicate on the Secrets tab still works,
    which is the whole reason it survives unnoticed. What it costs is the
    readability that put the value on the Variables tab in the first place -
    GitHub masks any registered secret value everywhere it appears, so the
    variable's own value prints as *** too, and pages.yml's `Data source: ...`
    line stops being evidence of anything. pages.yml cannot see this: it takes
    the variable and never looks at the secret."""
    for name, spec in sorted(SETTINGS.items()):
        if spec["where"] == "variable" and _actual_tabs(name) == {"secret", "variable"}:
            warnings.warn(
                f"{name} is set on both tabs. The Variables copy is the one in use; the Secrets copy only masks its "
                f"value in logs. Delete the secret unless something still needs it.",
                stacklevel=1,
            )


@live
def test_the_live_inputs_carry_names_only_never_values():
    """The reason the rest of this file can be careless about what it prints.
    Reducing the contexts to names happens in settings-configured.yml, so a change
    that passed toJSON(secrets) straight through would put real credentials in
    this process and in any assertion message that named one. This asserts the
    shape that cannot - and reports offenders by position, never by content."""
    for variable in ("CONFIGURED_SECRETS", "CONFIGURED_VARIABLES"):
        # Nothing parsed is ever bound to a local or named inside an assert.
        # pytest rewrites assertions to print the subexpressions they contain,
        # so `assert isinstance(parsed, list)` would dump the whole object -
        # values included - in the one test whose job is to catch values being
        # here at all. Only derived facts escape: a type name, a count, a
        # position. Re-reading the environment is the cost of that.
        shape = type(json.loads(os.environ[variable])).__name__
        assert shape == "list", (
            f"{variable} arrived as a JSON {shape}, not an array of names. An object is the shape of the raw context, "
            f"which would mean settings-configured.yml stopped reducing it to keys and values are now reaching this process."
        )
        offenders = [i for i, item in enumerate(json.loads(os.environ[variable])) if not _is_a_name(item)]
        assert not offenders, (
            f"{variable} holds {len(offenders)} entr{'y' if len(offenders) == 1 else 'ies'} that are not setting "
            f"names, at position(s) {offenders} - reported by position because the contents may be secret values."
        )


def test_the_live_check_is_not_silently_skipping_where_it_is_meant_to_run():
    """Everything above marked @live skips when its environment is absent,
    which is correct locally and would be a silent pass in the one job whose
    entire purpose is to run them."""
    if os.environ.get("SETTINGS_CHECK_LIVE") != "1":
        pytest.skip("Not the job that checks the configured settings.")
    assert CONFIGURED_SECRETS is not None and CONFIGURED_VARIABLES is not None, (
        "This job is meant to check the configured settings, but CONFIGURED_SECRETS/CONFIGURED_VARIABLES did not "
        "arrive, so every live test skipped and the job would have passed having checked nothing."
    )
