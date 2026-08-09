"""Every Dependabot update opens its pull requests already exempt from
`pr-issue-link.yml`.

That check fails any pull request closing no issue, and a dependency bump has
none to close. The exemption is a label, and before `.github/dependabot.yml`
carried `labels:` nothing applied it: five to seven bumps a week opened red and
waited for a human. The failure mode is not the labelling chore - it is what a
permanently red check teaches people to ignore.

What is worth a test here is not that the config is correct today. It is that
the two ends stay tied:

  * `pr-issue-link.yml` owns the label's name, in one `env:` entry. This suite
    reads it from there rather than repeating the string, so renaming the
    exemption cannot leave `dependabot.yml` quietly pointing at a label that no
    longer exempts anything.
  * A sixth ecosystem added to `dependabot.yml` is one line and reintroduces
    the whole problem for that manifest alone - visible only weekly, and only
    to whoever happens to look at that one pull request.

One thing no test in a checkout can reach: whether the labels named here exist
in the repository. Dependabot applies a label it recognises and drops one it
does not, silently either way, and `.github/tests/test_repository_settings.py`
draws the same line for secrets - the live half of a question like this can only
be answered from inside the repository, and is not answered here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from release_notes import INTERNAL_ONLY

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPENDABOT_PATH = REPO_ROOT / ".github" / "dependabot.yml"
ISSUE_LINK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-issue-link.yml"

# The label Dependabot applies to everything it opens, and the one the rest of
# the repository finds a bump by. `labels:` replaces Dependabot's defaults
# rather than extending them, so this is only present because dependabot.yml
# writes it back out - which is exactly why it can be dropped by accident.
BUMP_LABEL = "dependencies"


def _yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _env_values(node, name: str):
    """Every value given to an environment variable `name`, anywhere in a workflow.

    Walking the parsed tree rather than scanning the text keeps a mention of the
    variable in a comment from counting as a definition of it.
    """
    if isinstance(node, dict):
        env = node.get("env")
        if isinstance(env, dict) and name in env:
            yield env[name]
        for value in node.values():
            yield from _env_values(value, name)
    elif isinstance(node, list):
        for item in node:
            yield from _env_values(item, name)


@pytest.fixture(scope="module")
def escape_label() -> str:
    """The label `pr-issue-link.yml` accepts in place of a linked issue.

    Read from the workflow so that this suite cannot disagree with it. If that
    workflow stops declaring the name in `env:`, this fails rather than falling
    back to a guess - a hardcoded copy is the half that would go stale.
    """
    declared = list(_env_values(_yaml(ISSUE_LINK_WORKFLOW), "ESCAPE_LABEL"))
    assert len(declared) == 1, f"pr-issue-link.yml should declare ESCAPE_LABEL exactly once; found {declared}"
    return declared[0]


@pytest.fixture(scope="module")
def updates() -> list[dict]:
    parsed = _yaml(DEPENDABOT_PATH)["updates"]
    assert parsed, "dependabot.yml declares no updates"
    return parsed


def _describe(update: dict) -> str:
    return f"{update.get('package-ecosystem')} in {update.get('directory')}"


class TestTheExemptionArrivesWithTheBump:
    def test_the_workflow_reads_the_label_from_its_environment(self):
        """The fixture above derives the name from `env:`, which is only the
        real name if the script reads it from there too. A script that went back
        to a literal would leave this suite deriving a value nothing uses."""
        assert "process.env.ESCAPE_LABEL" in ISSUE_LINK_WORKFLOW.read_text(encoding="utf-8")

    def test_every_update_labels_its_pull_requests_exempt(self, updates, escape_label):
        """The whole point. An update without this opens red every week, and the
        only thing that notices is a person deciding red is normal here."""
        missing = [_describe(update) for update in updates if escape_label not in (update.get("labels") or [])]
        assert not missing, f"these Dependabot updates open pull requests that fail 'PR has a linked issue': {missing}"

    def test_no_update_loses_the_label_a_bump_is_found_by(self, updates):
        """`labels:` replaces Dependabot's defaults rather than adding to them,
        so `dependencies` survives only because each update writes it out again.
        Losing it costs nothing visible and breaks every search for a bump."""
        missing = [_describe(update) for update in updates if BUMP_LABEL not in (update.get("labels") or [])]
        assert not missing, f"these Dependabot updates would open without the `{BUMP_LABEL}` label: {missing}"

    def test_the_exemption_keeps_bumps_out_of_the_hiker_facing_notes(self, escape_label):
        """The second reason the fix is a label and not an author check inside
        `pr-issue-link.yml`. release_notes.py classifies by label, so an
        author-based exemption would pass CI and file every weekly bump under
        things a hiker can observe."""
        assert escape_label in INTERNAL_ONLY, (
            f"release_notes.py no longer treats `{escape_label}` as internal-only, "
            "so labelled dependency bumps will be offered as hiker-facing changes"
        )
