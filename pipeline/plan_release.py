"""Decide whether this week's data is worth a release, and what to call it.

The `plan` job of DATA_RELEASES.md section 2 (#1314), and the half of that
design that holds no credentials: everything here reads either a local file
this run produced or a public object a hiker's phone could fetch. A job that
cannot write to R2 cannot change what anybody downloads, which is section 1's
property carried one job further along.

WHAT IT DECIDES, and what it deliberately does not. Two answers:

  release_id   the next id `releases/` has room for
  rebuild      whether anything upstream moved enough to be worth a build

It does NOT decide which artifacts to rebuild, and that gap is the honest
part of this file rather than an omission. `check_freshness.py` answers
freshness per SOURCE - atc, opentrail, topo_quads, elevation,
atc_trail_updates, usgs_3dhp - and nothing anywhere maps a source to the
artifacts derived from it. Inventing that map here would mean asserting, with
nothing behind it, that (say) an opentrail edit cannot move `trails.geojson`.

@unvalidated - the rebuild rule below is all-or-nothing: any source STALE or
UNKNOWN rebuilds everything. Nobody has measured which sources actually move
which artifacts, so a finer rule would be a guess wearing a number. What
would settle it: a few weeks of this job's own output beside the resulting
manifests, which is a thing this job produces and nothing has yet collected.
Until then the coarse rule is the conservative one - it over-builds, and
over-building costs runner minutes where under-building ships a stale map.

WHY UNKNOWN REBUILDS. `lib/freshness_state.py` keeps STALE and UNKNOWN apart
because they call for different responses, and it would be reasonable to read
UNKNOWN as "no evidence of change, carry on". This does the opposite, for the
reason that module states in its own header: the failure that matters is a
false FRESH. An upstream nobody could reach is not an upstream that did not
move, and the cost of being wrong is asymmetric - a needless build against a
map that quietly stopped tracking the trail.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from lib import freshness_state, releases

# The freshness verdicts that mean "build". Spelled as a set rather than
# `!= FRESH` so a fourth verdict added later fails loudly here rather than
# being silently swept into one side or the other.
REBUILD_ON = frozenset({freshness_state.Freshness.STALE.value, freshness_state.Freshness.UNKNOWN.value})


def load_index(index_url: str | None) -> dict | None:
    """The published release index, or None when there is not one yet.

    A missing index is the first-run case and not an error - `index_ids`
    already reads a missing or malformed index as "no ids are taken". What is
    an error is a URL this pipeline may not fetch, which
    `freshness_state.read_published` refuses on the host allowlist #173 put up.
    """
    if not index_url:
        return None
    try:
        return json.loads(freshness_state.read_published(index_url))
    except freshness_state.StateUnavailable as exc:
        # A 404 here is the first publish, which is ordinary. Anything else -
        # a refused host, an unreachable bucket - is worth printing, because
        # planning against "no releases exist" when three do would mint a
        # colliding id that r2_keys then rejects mid-build.
        print(f"No release index read ({exc}); planning as if none exists.", file=sys.stderr)
        return None
    except ValueError as exc:
        print(f"Release index is not valid JSON ({exc}); planning as if none exists.", file=sys.stderr)
        return None


def rebuild_reasons(verdict: dict, *, force: bool = False) -> list[str]:
    """Why this run should build, one sentence per reason. Empty means skip.

    Reasons rather than a bare bool because the workflow prints them into its
    job summary, and "rebuild: true" with nothing beside it is the kind of
    output people stop reading after the third week.
    """
    if force:
        return ["force_full_rebuild was requested"]

    reasons = []
    for source in verdict.get("sources", []):
        if source.get("freshness") in REBUILD_ON:
            detail = source.get("detail") or "no detail given"
            reasons.append(f"{source.get('source')} is {source.get('freshness')}: {detail}")
    return reasons


def plan(verdict: dict, index: dict | None, *, force: bool = False, today=None) -> dict:
    """The whole answer as plain JSON, for a workflow to render or a job to read."""
    taken = releases.index_ids(index)
    reasons = rebuild_reasons(verdict, force=force)

    # No index at all means nothing has ever been staged, so there is no
    # previous release for the freshness state to have described. Building is
    # the only thing that can be true here, whatever the verdict says.
    if not taken:
        reasons = reasons or ["no release has been staged yet"]

    return {
        "planned_at": verdict.get("checked_at"),
        "release_id": releases.next_release_id(taken, today=today),
        "rebuild": bool(reasons),
        "reasons": reasons,
        # Carried through rather than recomputed: "nothing moved" against a
        # six-month-old capture is a different sentence from the one a reader
        # assumes, and check_freshness.py already measured it.
        "state_age_days": verdict.get("state_age_days"),
        "previous_release": taken[-1] if taken else None,
        "releases_listed": len(taken),
    }


def write_github_output(document: dict, path: str | None) -> None:
    """Expose the two decisions as step outputs, when running under Actions."""
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"release_id={document['release_id']}\n")
        handle.write(f"rebuild={'true' if document['rebuild'] else 'false'}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--verdict",
        metavar="PATH",
        type=Path,
        required=True,
        help="check_freshness.py --json output for this run.",
    )
    parser.add_argument(
        "--index-url",
        metavar="URL",
        help="Published releases/index.json. Omit for the first-run case.",
    )
    parser.add_argument("--json", metavar="OUT", type=Path, help="Write the plan to OUT as JSON.")
    parser.add_argument(
        "--force-full-rebuild",
        action="store_true",
        help="Build regardless of what upstream did. The dispatch escape hatch.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        verdict = json.loads(args.verdict.read_text())
    except (OSError, ValueError) as exc:
        # Unlike a missing index, this one is fatal. The verdict is this run's
        # own output from a step that just succeeded, so an unreadable one
        # means the run is confused about itself - and planning "nothing
        # changed" from it would be the false FRESH this whole design is
        # built to avoid.
        print(f"Could not read the freshness verdict at {args.verdict}: {exc}", file=sys.stderr)
        return 1

    document = plan(verdict, load_index(args.index_url), force=args.force_full_rebuild)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2))

    write_github_output(document, os.environ.get("GITHUB_OUTPUT"))

    if document["rebuild"]:
        print(f"Planning release {document['release_id']}:")
        for reason in document["reasons"]:
            print(f"  - {reason}")
    else:
        print(f"Nothing upstream moved since {document['previous_release']}; no release to stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
