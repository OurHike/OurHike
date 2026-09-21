"""Which GitHub accounts GitHub asks to approve each organization's registry.

The gate at the end of the registry-approval decision of 2026-09-21: an
organization's codeowners approve its registry pull request with their own
GitHub accounts, and branch protection will not merge until they have. That
only works if `.github/CODEOWNERS` names them, which is what this writes.

**ONE LINE PER ORGANIZATION, NAMING ITS DIRECTORY.** Everything under
`pipeline/reference/orgs/<slug>/` is that organization's, so adding a park
needs no regeneration and cannot land a file nobody owns.

**AN ORGANIZATION WITH NOBODY NAMEABLE GETS NO LINE, WHICH IS NOT THE SAME
AS AN EMPTY ONE.** A CODEOWNERS pattern with no owners after it does not
mean "anybody may approve" - it overrides the previous matching rule and
requests nobody, which is strictly worse than silence. So an organization
whose codeowners have not linked a GitHub account is left out, and the
file's own `*` line keeps covering their directory until they do.

**THE BLOCK IS DELIMITED AND THE REST OF THE FILE IS LEFT ALONE.** The prose
in `.github/CODEOWNERS` explains what the file does and does not do, and why
the repository-wide code-owner requirement is a trap with one maintainer. A
generator that rewrote the whole file would delete that on its first run.

**WHAT THIS CANNOT DO, AND IT IS WORTH KNOWING BEFORE RELYING ON IT: GITHUB
READS CODEOWNERS FROM THE PULL REQUEST'S BASE BRANCH.** A pull request that
adds its own ownership line is therefore NOT gated by that line - the owners
it introduces are not requested on it. So an organization's first registry
pull request cannot be the one that grants it ownership, and the two have to
be separate: one pull request adds the organization's line and its empty
directory (a maintainer approves that), and every registry pull request
afterwards is gated by the owners it established. Doing it in one would
leave the FIRST import - the one that decides what an organization's trails
are - as the single change nobody at that organization has to approve.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.registry_file import org_dir
from app.models.club import Club, OrgAdmin, OrgState
from app.models.profile import Profile

#: The fences. Everything between them is rewritten on each run; everything
#: outside is somebody's prose and is not this module's to touch.
GENERATED_START = "# --- generated: organization registry owners (app/core/codeowners.py) ---"
GENERATED_END = "# --- end generated ---"


def codeowners_block(db: Session) -> str:
    """The generated lines, sorted by slug and stable between runs.

    Sorted because an unstable order produces a diff on every regeneration,
    and a diff that is always there is a diff nobody reads.

    Only a `claimed` organization appears. A `pending` one is a registration
    nobody at the organization has confirmed (see `OrgState`), and handing
    its registry to whoever registered it would make the squat
    authoritative.
    """
    rows = (
        db.query(Club.slug, Profile.github_login)
        .join(OrgAdmin, OrgAdmin.club_id == Club.id)
        .join(Profile, Profile.id == OrgAdmin.person_id)
        .filter(
            Club.state == OrgState.claimed,
            Club.slug.isnot(None),
            OrgAdmin.is_codeowner.is_(True),
            # Being invited is not agreeing. An unapproved seat that carried
            # approval power would let an invitation grant it.
            OrgAdmin.approved_at.isnot(None),
            OrgAdmin.declined_at.is_(None),
            Profile.github_login.isnot(None),
        )
        .all()
    )

    owners: dict[str, set[str]] = {}
    for slug, login in rows:
        owners.setdefault(slug, set()).add(login)

    lines = [f"/{org_dir(slug)}/ " + " ".join(f"@{login}" for login in sorted(logins)) for slug, logins in sorted(owners.items())]
    return "\n".join(lines)


def render_codeowners(existing: str, block: str) -> str:
    """`existing` with the generated block replaced, or appended if absent.

    Appended at the END rather than anywhere else, because CODEOWNERS is
    last-match-wins: an organization's line above the file's `*` rule would
    be overridden by it and own nothing.
    """
    body = f"{GENERATED_START}\n{block}\n{GENERATED_END}\n" if block else f"{GENERATED_START}\n{GENERATED_END}\n"

    start = existing.find(GENERATED_START)
    if start == -1:
        return existing.rstrip("\n") + "\n\n" + body

    end = existing.find(GENERATED_END, start)
    if end == -1:
        return existing[:start] + body
    return existing[:start] + body + existing[end + len(GENERATED_END) :].lstrip("\n")
