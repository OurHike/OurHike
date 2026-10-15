"""Refuse a deploy whose pinned release carries a file a phone fetches whole over the launch budget (check 22).

    python3 .github/scripts/check_launch_budget.py <manifest.json> --release <id>
    python3 .github/scripts/check_launch_budget.py <manifest.json> --release <id> --warn --banner <file>

The manifest is the pinned release's own, `releases/<id>/manifest.json`, which
the step running this has just fetched from its own data base. The check is
pipeline/lib/client_contract.py's check_launch_budget, verify_release.py's
check 22: every file the client at this commit fetches whole and parses
(client/src/lib/config.ts's keys, the graph's cell shards and each hike's
detail) is weighed by its manifest `size_bytes` against
client/src/lib/artifactBudget.ts's LAUNCH_ARTIFACT_BUDGET_BYTES.

WHY A DEPLOY ASKS. The phone already declines such a file at the manifest
(lib/nearbyTrailData.ts, lib/trailGraphData.ts), so it survives, but without
the file. UA's release 2026-10-03-2 carried a 41,216,145-byte
network_overview.geojson against the 33,554,432-byte budget, ua.yml deployed
builds pinned to it, and the opening map drew the A.T. alone, for every UA
phone, because UA serves no channels.json (review 5528343443 on PR #1805,
Measured 2026-10-15). verify-release.yml, the only place check 22 ran, is a
dispatch-only promotion gate that no UA deploy passes through.

ua.yml and pages.yml refuse (exit 1). pr-preview.yml passes `--warn`: a
preview is the screen a reviewer judges the change on, so it still deploys,
and the sentence `--banner` writes leads its comment instead.

ONE MANIFEST IS ENOUGH. The step weighs the release DATA_RELEASE names. A phone
that has read channels.json follows that file's entry instead, and the two
steps after it hold that entry to DATA_RELEASE (check_pin_matches_channels.py,
decision 145) and the uploaded copy to the committed entry, so a build that
deploys has one release to weigh.

ONLY THE STANDARD LIBRARY, here and in lib/client_contract.py, so a runner's
bare python3 runs it with nothing installed, as it runs
check_pin_matches_channels.py.

Exit 0 when every weighed file fits, including a file with no `size_bytes`,
which a phone weighs once it arrives (lib/artifactBudget.ts's `oversized`
reads unknown as not too large); 1 when a file is over the budget; 2 when the
manifest or the client's declarations cannot be read the way this expects.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from lib import client_contract  # noqa: E402 - pipeline/ is on the path from the line above

#: A release id, as lib/dataRelease.ts's RELEASE_ID spells one.
RELEASE_ID = re.compile(r"\d{4}-\d{2}-\d{2}(?:-\d+)?")
#: A key this check will repeat in a workflow command or a pull request comment.
#: The manifest is text this check did not write, so anything else is named by
#: what it is rather than by itself.
SHOWN_KEY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,200}")

OVER = 1
UNREADABLE = 2


def _shown(key: str) -> str:
    return key if SHOWN_KEY.fullmatch(key) else "a file whose name this check does not repeat"


def _one_line(text: str) -> str:
    """`text` on one line: a line break in it could start a workflow command."""
    return " ".join(text.splitlines())


def weigh(manifest: dict, release: str) -> tuple[list[str], list[str]]:
    """(over, lines): a sentence per file over the budget, and every line to print besides."""
    reports = client_contract.check_launch_budget(manifest)
    budget = client_contract.launch_artifact_budget()
    over = []
    for found in reports:
        if found["state"] != client_contract.FAILED:
            continue
        size = manifest["artifacts"][found["key"]]["size_bytes"]
        over.append(
            f"Release {release}'s {_shown(found['key'])} is {size:,} bytes decoded, over the {budget:,}-byte launch "
            "budget (client/src/lib/artifactBudget.ts), so a phone of this build declines it at the manifest and "
            "draws without it."
        )
    unweighed = sum(
        1 for found in reports if found["state"] == client_contract.SKIPPED and found["detail"].startswith("no size_bytes")
    )
    # check_launch_budget's last row is always its one OK row for the family.
    lines = [f"Release {release}, check 22 (pipeline/lib/client_contract.py's check_launch_budget): {reports[-1]['detail']}."]
    if unweighed:
        lines.append(
            f"{unweighed} file(s) a phone fetches whole publish no size_bytes, so they were not weighed here; "
            "a phone weighs each once it arrives (client/src/lib/artifactBudget.ts)."
        )
    return over, lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("manifest", type=Path, help="the pinned release's manifest.json, as the step fetched it")
    parser.add_argument("--release", required=True, help="the release id the manifest is for")
    parser.add_argument("--warn", action="store_true", help="annotate a file over the budget as a warning, not an error")
    parser.add_argument("--banner", type=Path, help="write one Markdown sentence here when a file is over the budget")
    args = parser.parse_args(argv)
    level = "warning" if args.warn else "error"

    if not RELEASE_ID.fullmatch(args.release):
        print(f"::{level}::The release to weigh is not a release id, so this check cannot say which release it read.")
        return UNREADABLE
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"::{level}::Release {args.release}'s manifest could not be read as JSON, so nothing was weighed.")
        return UNREADABLE
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(artifacts, dict) or not all(isinstance(entry, dict) for entry in artifacts.values()):
        print(f"::{level}::Release {args.release}'s manifest has no `artifacts` mapping, so nothing was weighed.")
        return UNREADABLE
    try:
        over, lines = weigh({"artifacts": artifacts}, args.release)
    except (OSError, ValueError) as error:
        # The client's declarations moved: client_contract's own message says
        # which, and this check must follow them rather than weigh nothing.
        print(f"::{level}::{str(error).splitlines()[0]}")
        return UNREADABLE

    for line in lines:
        print(_one_line(line))
    if not over:
        print(f"No file release {args.release} lists that a phone fetches whole is over the launch budget.")
        return 0
    for sentence in over:
        print(f"::{level}::{sentence} Pin a release whose files fit, or cut this one (pipeline/lib/client_contract.py).")
    if args.banner is not None:
        args.banner.write_text(
            f"**This build's pinned release (`{args.release}`) carries {len(over)} file(s) over the launch budget**, "
            "which phones decline and draw without: " + " ".join(over),
            encoding="utf-8",
        )
    return OVER


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
