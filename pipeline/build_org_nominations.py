"""Fill the nominate form for every organization in the catalogue (#1543).

features/ORG_ONBOARDING.md's `/for-orgs/nominate/` screen does not hand
somebody a blank form. It reports what OurHike FOUND about an organization -
each endpoint with what is in it, the licence position, the membership and
donation links, and the flat files we refuse - and asks them to confirm it.
The prototype's `nomFound` array is that report.

This script builds one such report per organization from
`reference/trail_orgs.json`, so that loading 163 organizations is one reviewed
file and one run rather than 163 people typing.

WHAT IT DELIBERATELY DOES NOT DO

  - It does not probe anything. Every endpoint here is the research pass's,
    carrying the research pass's own `confidence`, and `inferred` means the URL
    was never opened. A nomination that claimed a feature count nobody measured
    would be exactly the "confidently wrong" this project refuses.
  - It does not invent contacts. The form wants a named human and the research
    collected none, so every nomination carries an empty contact list and says
    why. Thirty plausible-looking coordinator names would be worse than none -
    see `_CONTACT_GAP`.
  - It does not write to the repository. Output goes to `data/`, which is
    gitignored, because a generated file is not a reviewed one
    (CONTRIBUTING.md, "Data does not go in commits").

The reviewed input is `reference/trail_orgs.json`. This file is the arm that
turns it into submissions, and features/ORG_BULK_LOAD.md is why the batches
are grouped the way they are.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE / "reference" / "trail_orgs.json"
EMBLEMS = HERE / "reference" / "trail_emblems.json"
OUT = HERE / "data" / "org_nominations.json"

_CONTACT_GAP = (
    "No contact was collected for this organization. The nominate form asks for a named human "
    "and a role address, and the research pass that produced this catalogue did not gather "
    "either - so this is an empty list rather than a guess. A role address (trails@, gis@) is "
    "what features/SOURCE_REGISTRY.md asks for; a personal one is accepted and flagged."
)

# What each `load` verdict means to somebody reading a submission, in the
# prototype's own vocabulary: `tone` drives the colour, `label` the pill,
# `included` whether the row is part of what we are proposing to take.
TONE = {
    "ship": ("easy", "usable", True),
    "via": ("info", "already covered", True),
    "hold": ("moderate", "needs a URL", False),
    "refuse": ("strenuous", "not accepted", False),
    "none": ("info", "nothing to take", False),
}


def _licence_finding(org: dict) -> dict:
    """The row the prototype puts last and the maintainer cares about most.

    The prototype's own example reads "nothing restricting use - published
    publicly, no terms attached" against a label of "no restrictions", which is
    the maintainer's assume-open position already drawn into the design. This
    reproduces it without letting it say more than the catalogue knows.
    """
    basis = org["licence_basis"]
    if basis == "public_domain":
        return {
            "label": "public domain",
            "tone": "easy",
            "included": True,
            "note": "A federal, state or municipal publisher. Redistributable, and the "
            "attribution is a courtesy this project pays anyway.",
        }
    if basis == "stated_by_org" and org["load"] == "refuse":
        return {
            "label": "restricted",
            "tone": "strenuous",
            "included": False,
            "note": f"The organization states terms that refuse this: {org['licence']}.",
        }
    if basis == "stated_by_org":
        return {
            "label": "stated licence",
            "tone": "easy",
            "included": True,
            "note": f"The organization published terms: {org['licence']}. Attribution is rendered exactly as recorded.",
        }
    if basis == "maintainer_authorisation":
        return {
            "label": "on our own authorisation",
            "tone": "moderate",
            "included": True,
            "note": "Ships on the maintainer's recorded authorisation rather than on a grant "
            "from the organization. NOT A LICENCE FROM THEM, and a club inheriting "
            "this project has to re-confirm it in its own name.",
        }
    if basis == "unstated":
        return {
            "label": "no restrictions found",
            "tone": "easy",
            "included": True,
            "note": "Nothing restricting use was found - no terms attached either way. "
            "Treated as open per the maintainer's decision of 2026-09-17, and "
            "recorded as unstated rather than as a grant nobody made. They still "
            "get the final say when they approve the proposal.",
        }
    return {
        "label": "not reached",
        "tone": "info",
        "included": False,
        "note": "There is nothing to licence, because there is nothing to take.",
    }


def nomination(org: dict, emblems_by_steward: dict) -> dict:
    tone, label, included = TONE[org["load"]]
    found = []

    if org["endpoint"]:
        confidence = org["confidence"]
        found.append(
            {
                "what": {
                    "external_arcgis_layer": "ArcGIS feature layer",
                    "ogc_features": "OGC API / WFS endpoint",
                    "geofabrik_extract": "OSM extract",
                    "http_file": "File or page at a stable URL",
                }.get(org["endpoint_kind"], org["endpoint_kind"] or "Endpoint"),
                "where": org["endpoint"],
                "note": (
                    "Confirmed resolving by the research pass on 2026-09-17. NOT PROBED BY US - "
                    "no feature count, no CRS and no field list has been read from it."
                    if confidence == "verified"
                    else "NEVER OPENED. The data path is well-supported and the exact URL was not "
                    "tested, so this is a lead rather than an endpoint."
                ),
                "tone": tone if confidence == "verified" else "moderate",
                "label": label if confidence == "verified" else "untested",
                "included": included,
            }
        )
    elif org["load"] == "via":
        found.append(
            {
                "what": "Geometry arrives through another organization",
                "where": f"org:{org['via']}",
                "note": org["why"],
                "tone": "info",
                "label": "already covered",
                "included": True,
            }
        )
    else:
        found.append(
            {
                "what": "No dataset found",
                "where": org["website"] or "no website recorded",
                "note": org["why"],
                "tone": "moderate",
                "label": "needs a URL",
                "included": False,
            }
        )

    found.append({"what": "Licence", "where": org["licence"] or "nothing found either way", **_licence_finding(org)})

    emblems = emblems_by_steward.get(f"org:{org['slug']}", [])
    return {
        "slug": org["slug"],
        "org": org["org"],
        "domain": org["website"],
        "where": org["states"],
        "org_type": org["type"],
        "trails": org["trails"],
        "approx_miles": org["miles"],
        "submission_kind": "maintainer_research",
        "submitted_via": "research pass of 2026-09-17, loaded by build_org_nominations.py",
        "state": "unclaimed",
        "found": found,
        "contacts": [],
        "contacts_note": _CONTACT_GAP,
        "emblems": emblems,
        "membership_url": None,
        "donation_url": None,
        "giving_note": (
            "The form puts an organization's own membership and donation links in front of every "
            "hiker walking its trails, and no money passes through OurHike. The research pass "
            "collected neither URL, so both are null rather than guessed."
        ),
        "verdict": org["load"],
        "reaches_hikers": False,
    }


def build() -> dict:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    emblems = json.loads(EMBLEMS.read_text(encoding="utf-8"))

    by_steward: dict[str, list] = {}
    for trail in emblems["trails"]:
        if trail["steward"]:
            by_steward.setdefault(trail["steward"], []).append(
                {"slug": trail["slug"], "trail": trail["trail"], "blaze": trail["blaze"], "mark_state": trail["mark_state"]}
            )

    orgs = catalogue["orgs"]
    return {
        "_comment": (
            "Generated by build_org_nominations.py from reference/trail_orgs.json. NOT REVIEWED "
            "SOURCE - the reviewed file is the catalogue, and this is what a run makes of it. "
            "Nothing here reaches a hiker: every nomination carries reaches_hikers false, and a "
            "merged pull request against sources.json is still the only thing that changes that."
        ),
        "generated_from": {
            "catalogue_rows": len(orgs),
            "emblem_trails": len(emblems["trails"]),
        },
        "nominations": [nomination(org, by_steward) for org in orgs],
    }


def summarise(payload: dict) -> str:
    """The table a reviewer reads instead of 163 diffs."""
    noms = payload["nominations"]
    verdicts = Counter(n["verdict"] for n in noms)
    lines = [
        f"{len(noms)} nominations built, none reaching a hiker.",
        "",
        f"  {'verdict':10} {'orgs':>5}   what it costs to load",
        f"  {'-' * 10} {'-' * 5}   {'-' * 40}",
    ]
    cost = {
        "ship": "a fetch, a clip and download budget",
        "via": "nothing - another row already carries it",
        "hold": "nothing - a row in a file",
        "refuse": "nothing - stated terms refuse it",
        "none": "nothing - no geometry exists",
    }
    for verdict in ("ship", "via", "hold", "refuse", "none"):
        lines.append(f"  {verdict:10} {verdicts.get(verdict, 0):>5}   {cost[verdict]}")
    ships = [n for n in noms if n["verdict"] == "ship"]
    lines += [
        "",
        f"  {len(ships)} endpoints to register. Contacts collected: "
        f"{sum(len(n['contacts']) for n in noms)} - the form asks for one per org and the "
        "research gathered none.",
        f"  Badged trails attached to an organization: "
        f"{sum(len(n['emblems']) for n in noms)} of {payload['generated_from']['emblem_trails']}.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--summary-only", action="store_true", help="print the review table without writing the file")
    args = parser.parse_args()

    payload = build()
    if not args.summary_only:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    print(summarise(payload))


if __name__ == "__main__":
    main()
