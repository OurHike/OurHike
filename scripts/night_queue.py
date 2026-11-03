#!/usr/bin/env python3
"""Which open issues may an unattended session pick up, and why not the rest.

The gate for the night lane, as a pure function of an issue's labels, so it can
be held by a test without the network (#1463). scripts/nightshift.sh is the
half that fetches; this half decides, and the split is deliberate - a rule that
can only be exercised by calling GitHub is a rule nobody re-checks.

    night_queue.py            read issues as JSON on stdin, print the verdict
    night_queue.py --census   the bucket counts behind #1463's table
    night_queue.py --triage   the unlabeled issues, which no rule can route

Input is the issues API's own shape - a JSON list of objects carrying at least
`number`, `title`, `labels` and `updated_at` - with two optional keys the
fetcher fills in: `has_open_pr`, true when an open pull request already closes
the issue, and `claimed`, true when a claim comment says a session has started.

THE GATE. An issue is eligible only if all four hold:

  - it carries no `client` label. The maintainer's lane: a change a hiker can
    see is reviewed on a phone, not by CI (CONTRIBUTING.md, "Two lanes").
  - it carries no `night-shift-hold`. The veto, so the derived rule never has
    to be argued with - one label beats any amount of reasoning about whether
    a particular issue is really server-side.
  - it carries no `blocked-external` and no `needs-field-testing`. Neither is
    waiting on work; one waits on a third party and the other on somebody
    standing on a trail.
  - it carries at least one AREA label. This is what the 28 unlabeled issues
    fail, and failing it is the whole reason #1463 exists: a rule reading
    labels cannot see three quarters of this backlog.

Nothing here is a judgement about difficulty. An unattended session that finds
an eligible issue harder than it looks stops and says so, which is cheaper than
a gate trying to guess complexity from a title.

RANKING. Reasoned, except the tiebreak:

  1. `deployment-health` - these are bot-filed and the bot closes them when the
     check goes green (check-deployed-app.yml, "opened green->red, closed
     red->green"), so an OPEN one describes a check that is failing now rather
     than one that failed once.
  2. `release-followup` - names something a merge already left undone, which is
     the dropped-handoff failure #1123 is about.
  3. everything else, least-recently-updated first. @unvalidated - picked, not
     measured. The argument for it is that the issue nobody has touched in
     longest is the least likely to collide with something a person is already
     thinking about, which is plausible and unchecked. What would settle it is
     which order actually empties the queue fastest over a month of nights,
     which cannot be known before there have been any.
"""

import json
import sys

# Labels that make an issue routable at all. Area labels as CONTRIBUTING.md
# lists them, minus `client` (the other lane), plus the three the bots and the
# release process file under - `deployment-health` and `data-freshness` issues
# carry no area label and are server-side by construction, and a
# `release-followup` is server-side unless it also says `client`.
AREA = frozenset(
    {
        "pipeline",
        "backend",
        "ops",
        "data",
        "docs",
        "testing",
        "site",
        "deployment-health",
        "data-freshness",
        "release-followup",
    }
)

# Each is a reason an unattended session must not take the issue, paired with
# the sentence it prints. Order matters: the first match is what gets printed,
# so the most specific reason wins.
DISQUALIFIERS = (
    ("night-shift-hold", "held - `night-shift-hold` is the maintainer's veto"),
    ("client", "maintainer's lane - a hiker can see it, so it is reviewed on a phone"),
    ("blocked-external", "waiting on a third party, not on work"),
    ("needs-field-testing", "needs somebody on an actual trail"),
)


def _labels(issue):
    """The issue's label names, however the caller spelled them.

    The REST API returns objects with a `name`; the GraphQL-backed MCP tool
    returns bare strings. Both arrive here, so both are read.
    """
    out = set()
    for label in issue.get("labels") or ():
        out.add(label if isinstance(label, str) else label.get("name", ""))
    return out - {""}


def verdict(issue):
    """`(True, rank)` if an unattended session may take this, else `(False, why)`."""
    labels = _labels(issue)

    if issue.get("has_open_pr"):
        return False, "already in flight - an open pull request closes it"
    if issue.get("claimed"):
        return False, "already claimed - a comment says a session has started"

    for label, reason in DISQUALIFIERS:
        if label in labels:
            return False, reason

    if not labels:
        return False, "unlabeled - no rule can route it (--triage lists these)"
    if not labels & AREA:
        return False, f"no area label - carries only {', '.join(sorted(labels))}"

    if "deployment-health" in labels:
        tier = 1
    elif "release-followup" in labels:
        tier = 2
    else:
        tier = 3
    return True, (tier, issue.get("updated_at", ""), issue.get("number", 0))


def queue(issues):
    """The eligible issues in the order an unattended session should take them."""
    eligible = []
    for issue in issues:
        ok, rank = verdict(issue)
        if ok:
            eligible.append((rank, issue))
    eligible.sort(key=lambda pair: pair[0])
    return [issue for _, issue in eligible]


def excluded(issues):
    """Every issue that is not eligible, each with the one reason it is not."""
    return [(issue, why) for issue in issues for ok, why in [verdict(issue)] if not ok]


def census(issues):
    """The bucket counts behind #1463's table, so the table stays re-derivable."""
    labelled = [_labels(i) for i in issues]
    server_side = [ls for ls in labelled if ls & {"pipeline", "backend", "ops", "data"} and "client" not in ls]
    return {
        "open issues": len(issues),
        "carry `client`": sum(1 for ls in labelled if "client" in ls),
        "server-side only": len(server_side),
        "no label at all": sum(1 for ls in labelled if not ls),
        "blocked-external": sum(1 for ls in labelled if "blocked-external" in ls),
        "deployment-health": sum(1 for ls in labelled if "deployment-health" in ls),
        "eligible tonight": len(queue(issues)),
    }


def _title(issue):
    """#N and its title, never the bare number (CLAUDE.md, "Name an issue")."""
    return f"#{issue.get('number')} — {issue.get('title', '')}"


def main(argv):
    issues = [i for i in json.load(sys.stdin) if "pull_request" not in i]

    if "--census" in argv:
        for name, count in census(issues).items():
            print(f"  {count:4d}  {name}")
        return 0

    if "--triage" in argv:
        unlabeled = [i for i in issues if not _labels(i)]
        print(f"{len(unlabeled)} issue(s) carry no label, so no rule can route them:\n")
        for issue in sorted(unlabeled, key=lambda i: -i.get("number", 0)):
            print(f"  {_title(issue)}")
        if unlabeled:
            print("\nLabelling these is the highest-leverage thing in the backlog: each one")
            print("is invisible to the gate until it carries an area label.")
        return 0

    tonight = queue(issues)
    print(f"\n{len(tonight)} issue(s) an unattended session may take, in order:\n")
    for position, issue in enumerate(tonight, start=1):
        print(f"  {position:2d}. {_title(issue)}")

    skipped = excluded(issues)
    print(f"\n{len(skipped)} issue(s) it may not, and why:\n")
    for issue, why in sorted(skipped, key=lambda pair: pair[1]):
        print(f"  {_title(issue)}")
        print(f"      → {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
