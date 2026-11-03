"""An organization's registry as a file its codeowners can review line by line.

**WHY THE REGISTRY BECOMES A FILE.** The approval decision of 2026-09-21: an
organization's three codeowners approve its registry on GitHub with their own
GitHub accounts, and branch protection gates the merge on that review.
`.github/CODEOWNERS` maps PATHS to people, so the registry needs a path -
one per organization, because a single combined file would make every
organization's codeowners an owner of every other organization's trails.

**WHY `pipeline/reference/orgs/`.** CONTRIBUTING.md's exception for that
directory is "a join that encodes judgement somebody reviews row by row",
which is what a sign-off is and not a description that had to be stretched.

**AND WHY A DIRECTORY PER ORG RATHER THAN A FILE.** Measured on the shape
below: a section serializes to 9 lines, so one file per organization holds
about 1,330 sections before passing `MAX_REFERENCE_LINES` (12,000). That is
ample for a club maintaining a stretch of the AT and **not** ample for one
maintaining a whole trail system - which is the organization whose registry
matters most, so a format that fails exactly there is the wrong format. One
file per park keeps each well inside the ceiling, and it matches how a
codeowner reads the thing anyway: park by park.

It also simplifies the gate. `.github/CODEOWNERS` names the organization's
DIRECTORY, so adding a park does not need CODEOWNERS regenerated and cannot
land a file nobody owns.

**WHAT IS LEFT OUT, AND WHY THAT IS THE DESIGN.** No row ids, no timestamps,
no geometry.

  - Ids and timestamps are database bookkeeping. They would churn the diff
    on every regeneration while telling a reviewer nothing, and a diff that
    is mostly noise is a diff nobody reads carefully.
  - Geometry is the one that matters. A linestring per section would bury
    the names, mileages and blazes a person is actually approving under
    megabytes they cannot read - which defeats the review this file exists
    for - and it is derived data, whose home is `pipeline/data/` and not a
    commit (CONTRIBUTING.md's "Data does not go in commits").

So **the reviewed file is the manifest, not the map**: what sections exist,
what the organization calls them, how long they are, and which blaze word
their own GIS uses. The shapes come from the organization's own GIS, which
is authoritative for them anyway and which we mirror rather than copy.

**NOTHING HERE TOUCHES THE FILESYSTEM.** This produces bytes; the pull
request opener commits them. A backend that wrote into a working tree would
be a backend that needs one.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.org_registry import OrgPark, OrgSection, OrgTrail

#: Where organizations' reviewed registries live. Written here once and read
#: by everything that has to agree about it - the CODEOWNERS generator, the
#: branch-protection expectation, and the pull request opener. Three copies
#: of a path string is how one of them quietly stops matching.
REGISTRY_DIR = "pipeline/reference/orgs"

#: The file every organization has, even one with no trails yet. It carries
#: the header and the list of parks, so the directory exists (and so is
#: owned) before the first import, and so a reviewer can see a park being
#: added or removed rather than only its file appearing.
INDEX_FILE = "organization.json"

#: Decimal places for a mileage. Enough that a tenth of a mile survives, few
#: enough that `0.1 + 0.2` does not reach the file as `0.30000000000000004`
#: and show up as a change nobody made.
MILEAGE_PLACES = 3


def org_dir(slug: str) -> str:
    """The directory holding `slug`'s reviewed registry.

    This is the string `.github/CODEOWNERS` names, so everything under it is
    owned by that organization's codeowners and nothing else is.
    """
    return f"{REGISTRY_DIR}/{slug}"


def _file_stem(name: str, taken: set[str]) -> str:
    """A park's name as a filename, and never the same one twice.

    Lowercased ASCII words joined by hyphens. Two parks whose names differ
    only in punctuation would otherwise collide and silently drop one -
    a registry quietly missing a park is the failure worth spending a
    suffix to avoid.
    """
    cleaned = "".join(character if character.isalnum() else "-" for character in (name or "").lower())
    stem = "-".join(part for part in cleaned.split("-") if part) or "park"
    candidate = stem
    suffix = 2
    while candidate in taken:
        candidate = f"{stem}-{suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate


def _miles(value: float | None) -> float | None:
    return None if value is None else round(value, MILEAGE_PLACES)


def _section(section: OrgSection) -> dict[str, Any]:
    return {
        "name": section.name,
        "start_anchor": section.start_anchor,
        "end_anchor": section.end_anchor,
        "start_mile": _miles(section.start_mile),
        "end_mile": _miles(section.end_mile),
        "miles": _miles(section.miles),
        "region": section.region,
    }


def registry_document(db: Session, club: Club) -> dict[str, Any]:
    """The whole registry of one organization, nested and sorted.

    **SORTED BY NAME AT EVERY TIER, and that is load-bearing rather than
    tidy.** Insertion order is whatever a GIS import happened to do, so an
    unsorted file would reshuffle on every regeneration and every pull
    request would read as a rewrite. A codeowner asked to approve a rewrite
    approves it without reading, which is the failure this whole file is
    meant to prevent.
    """
    parks = db.query(OrgPark).filter(OrgPark.club_id == club.id).all()
    park_ids = [park.id for park in parks]
    trails = db.query(OrgTrail).filter(OrgTrail.park_id.in_(park_ids)).all() if park_ids else []
    trail_ids = [trail.id for trail in trails]
    sections = db.query(OrgSection).filter(OrgSection.trail_id.in_(trail_ids)).all() if trail_ids else []

    by_trail: dict[str, list[OrgSection]] = {}
    for section in sections:
        by_trail.setdefault(section.trail_id, []).append(section)
    by_park: dict[str, list[OrgTrail]] = {}
    for trail in trails:
        by_park.setdefault(trail.park_id, []).append(trail)

    return {
        "org": {"slug": club.slug, "name": club.name},
        "parks": [
            {
                "name": park.name,
                "kind": park.kind.value if park.kind is not None else None,
                "trails": [
                    {
                        "name": trail.name,
                        "blaze_value_raw": trail.blaze_value_raw,
                        "blaze_mapped": trail.blaze_mapped,
                        "miles": _miles(trail.miles),
                        "sections": [
                            _section(section) for section in sorted(by_trail.get(trail.id, []), key=lambda row: row.name or "")
                        ],
                    }
                    for trail in sorted(by_park.get(park.id, []), key=lambda row: row.name or "")
                ],
            }
            for park in sorted(parks, key=lambda row: row.name or "")
        ],
    }


def _dump(document: Any) -> str:
    """A document as the exact bytes that get committed.

    Two spaces and a trailing newline because this is read as a diff by
    people rather than parsed by machines in a hurry, and a file without a
    final newline makes every later change touch its last line.
    """
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def registry_files(db: Session, club: Club) -> dict[str, str]:
    """Every file this organization's registry occupies, path to content.

    The index first, then one file per park. An organization with no trails
    yet still gets the index - it is what the first import diffs against,
    and what makes the directory exist to be owned.
    """
    document = registry_document(db, club)
    slug = club.slug or ""
    directory = org_dir(slug)

    taken: set[str] = set()
    stems = [_file_stem(park["name"], taken) for park in document["parks"]]

    files = {
        f"{directory}/{INDEX_FILE}": _dump(
            {
                "org": document["org"],
                "parks": [
                    {"name": park["name"], "kind": park["kind"], "file": f"{stem}.json"}
                    for park, stem in zip(document["parks"], stems, strict=True)
                ],
            }
        )
    }
    for park, stem in zip(document["parks"], stems, strict=True):
        files[f"{directory}/{stem}.json"] = _dump({"org": document["org"], "park": park})
    return files
