"""Opening the pull request an organization's codeowners review.

**WHOSE CREDENTIALS, AND WHY NOT AN ADMIN'S.** Opening a pull request needs
write access to the repository. An organization admin has no GitHub account
here, and giving one the power to cause a push would make every org admin a
committer to a public repository - so this holds a service identity's token
and never a person's.

That is only half of what `sign_off_registry`'s docstring used to say, and
the half that survives. **Approving needs no write access at all**: on a
public repository any account may submit a review, so the organization's
codeowners approve with their own accounts, which is the whole point of the
arrangement. Opening and approving are different questions and running them
together is what made the original objection look like it ruled out both.

**THE GUARD WITH TEETH IS CONTAINMENT.** Scoping the token GitHub-side is a
console setting this repository cannot assert. What it can assert - and does,
on every write - is that no path leaves the organization's own directory. A
write outside it is a change to this repository that no organization's
codeowners review, which is exactly the bug worth refusing rather than
logging.

**IT NEVER MERGES.** CLAUDE.md's rule applied to the one piece of code here
holding a token that could. It opens, and a person merges.

**OFF UNTIL SOMEBODY TURNS IT ON.** The same argument `mail_enabled` makes: a
preview deployment holding a fixture must not be one variable away from
opening pull requests against a public repository.

**ONE COMMIT, VIA THE GIT DATA API.** The contents API would make one commit
per file and a registry would arrive as eleven of them - eleven things to
read in a review that should be one.

**TWO THINGS GO UP THIS WAY NOW, AND THEY SHARE ONE PATH TO GITHUB.** An
organization's registry, and one of its challenges (#1780, features/
CHALLENGES.md): a club's list of places, saved in the console and written to
`pipeline/reference/challenges/<slug>/<id>.json` for a maintainer to review.
Both openers hand `_put_up_for_review` their files and the one directory
they may write into, so the containment check, the switch and the
never-merge rule are enforced in one place rather than copied into two.
"""

from __future__ import annotations

import base64
import json
import posixpath
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.core.registry_file import org_dir, registry_files
from app.core.trail_challenge import ID_RE, challenge_dir, challenge_file, may_publish_as
from app.models.club import Club, OrgState

GITHUB_API = "https://api.github.com"
GITHUB_VERSION = "2022-11-28"

#: Short, because every call here is a small JSON request against a remote
#: that is either up or is not, and a long timeout on a write is a long time
#: to hold a request open for something that already failed.
TIMEOUT_SECONDS = 20.0


class RegistryPrRefused(RuntimeError):
    """The pull request was not opened, and nothing was written."""


@dataclass(frozen=True)
class OpenedPr:
    number: int
    url: str


def branch_for(slug: str) -> str:
    """One branch per organization, reused.

    Reused rather than dated, so an organization pressing sign off twice
    updates one pull request instead of leaving two open against its own
    registry, each half-reviewed.
    """
    return f"registry/{slug}"


def _request(client: httpx.Client, method: str, path: str, *, json: dict | None = None) -> dict:
    """One call, and a refusal for anything that is not a success.

    **NO RETRY**, the same posture as `core/assist.py`: a retry against a
    remote that just failed is how one stuck request becomes ten, and this
    one holds a write token.
    """
    try:
        response = client.request(
            method,
            f"{GITHUB_API}{path}",
            json=json,
            timeout=TIMEOUT_SECONDS,
            headers={
                "authorization": f"Bearer {settings.registry_pr_token}",
                "accept": "application/vnd.github+json",
                "x-github-api-version": GITHUB_VERSION,
            },
        )
    except httpx.HTTPError as exc:
        raise RegistryPrRefused("GitHub did not answer.") from exc

    if response.status_code >= 400:
        # The body can carry token or account detail, so what reaches a
        # caller is the status and the path and nothing else.
        raise RegistryPrRefused(f"GitHub refused {method} {path} ({response.status_code}).")
    try:
        return response.json() or {}
    except ValueError as exc:
        raise RegistryPrRefused(f"GitHub's answer to {method} {path} could not be read.") from exc


def _refuse_unless_switched_on() -> None:
    if not settings.registry_pr_enabled or not settings.registry_pr_token:
        raise RegistryPrRefused("Opening registry pull requests is not switched on for this deployment.")


def _refuse_unless_claimed(club: Club) -> str:
    """The organization's slug, once it is one allowed to publish anything."""
    if club.state != OrgState.claimed:
        raise RegistryPrRefused(
            "Only a claimed organization publishes a registry or a challenge. A held registration has not been "
            "confirmed by anybody at the organization."
        )
    slug = club.slug or ""
    if not slug:
        raise RegistryPrRefused("This organization has no address yet.")
    return slug


def _put_up_for_review(
    owned: httpx.Client,
    *,
    files: dict[str, str],
    inside: str,
    branch: str,
    message: str,
    title: str,
    body: str,
) -> OpenedPr:
    """Commit `files` to `branch` as one commit and open (or move on) its pull request.

    `inside` is the one directory every path must be under, and it is checked
    here - before any request - so no opener can reach GitHub without passing
    it. A path is also refused if it does not normalize to itself: a string
    prefix check alone would pass `<dir>/../../.github/x`, and a traversal is
    precisely a write outside the directory.
    """
    outside = sorted(path for path in files if not path.startswith(inside) or posixpath.normpath(path) != path)
    if outside or not files:
        # Refused rather than filtered. A writer producing a path outside the
        # organization's directory is a writer that has gone wrong, and
        # quietly dropping the bad paths would commit the rest as if nothing
        # had happened.
        raise RegistryPrRefused(f"Refusing to write outside {inside}: {outside}")

    repo = settings.registry_pr_repo

    base = _request(owned, "GET", f"/repos/{repo}/git/ref/heads/main")
    base_sha = base.get("object", {}).get("sha")
    if not base_sha:
        raise RegistryPrRefused("GitHub did not say where main is.")

    tree = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": _request(
                owned,
                "POST",
                f"/repos/{repo}/git/blobs",
                json={"content": base64.b64encode(content.encode("utf-8")).decode("ascii"), "encoding": "base64"},
            )["sha"],
        }
        for path, content in sorted(files.items())
    ]
    made_tree = _request(owned, "POST", f"/repos/{repo}/git/trees", json={"base_tree": base_sha, "tree": tree})
    commit = _request(
        owned,
        "POST",
        f"/repos/{repo}/git/commits",
        json={"message": message, "tree": made_tree["sha"], "parents": [base_sha]},
    )

    existing = _request(owned, "GET", f"/repos/{repo}/pulls?head={repo.split('/')[0]}:{branch}&state=open")
    if isinstance(existing, list) and existing:
        # The branch already has a pull request. Move it on and leave the
        # review that is already happening where it is.
        _request(owned, "PATCH", f"/repos/{repo}/git/refs/heads/{branch}", json={"sha": commit["sha"], "force": True})
        return OpenedPr(number=existing[0]["number"], url=existing[0].get("html_url", ""))

    _request(owned, "POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    opened = _request(
        owned,
        "POST",
        f"/repos/{repo}/pulls",
        json={"title": title, "head": branch, "base": "main", "body": body},
    )
    return OpenedPr(number=opened["number"], url=opened.get("html_url", ""))


def _plain(name: str) -> str:
    """A club's name as inert text in a commit, a PR title and a PR body.

    The name is whatever the organization typed. Unescaped, a closing keyword
    and an issue number in a merged commit message closes that issue, an
    `@` pings somebody, and brackets, backticks and URLs make links and code.
    So the name keeps only letters, digits, spaces and plain punctuation
    (`. , ' & -`), with a `GH-` reference broken apart, and is cut at 120
    characters - a commit message has no escaping at all, so this is a
    whitelist rather than a list of dangers (second security review,
    2026-10-01).
    """
    kept = "".join(ch for ch in name if ch.isalnum() or ch in " .,'&-")
    kept = re.sub(r"(?i)\bGH-(?=\d)", "GH ", kept)
    kept = " ".join(kept.split())[:120].strip()
    return kept or "An organization"


def open_registry_pr(db, club: Club, *, client: httpx.Client | None = None) -> OpenedPr:
    """Put this organization's registry up for its codeowners to approve."""
    _refuse_unless_switched_on()
    slug = _refuse_unless_claimed(club)

    return _put_up_for_review(
        client if client is not None else httpx.Client(),
        files=registry_files(db, club),
        inside=f"{org_dir(slug)}/",
        branch=branch_for(slug),
        message=f"{_plain(club.name)}: registry as its codeowners signed it off",
        title=f"{_plain(club.name)}: registry",
        body=(
            f"The registry {_plain(club.name)} signed off, as files.\n\n"
            "Its codeowners are requested on this automatically - "
            "`.github/CODEOWNERS` names them against this directory.\n\n"
            "**Nothing here merges itself.**"
        ),
    )


def challenge_branch_for(slug: str, challenge_id: str) -> str:
    """One branch per challenge, reused - `branch_for`'s reason, per challenge.

    Per challenge rather than per organization because a club editing two
    lists at once should get two reviews, not one pull request whose second
    push silently replaced the first list's change.
    """
    return f"challenges/{slug}/{challenge_id}"


def open_challenge_pr(
    club: Club, challenge_id: str, definition: dict[str, Any], *, client: httpx.Client | None = None
) -> OpenedPr:
    """Put one of this organization's challenges up for a maintainer to review.

    Writes exactly one file, `pipeline/reference/challenges/<org>/<id>.json`,
    and nothing else. It is a request for review and nothing more: the
    pipeline's own checks (pipeline/lib/challenges.py) run on the pull
    request, and a person merges it or does not.

    **NOT OWNED BY THE CLUB'S CODEOWNERS.** `.github/CODEOWNERS` names each
    organization's registry directory and not this one, so the review a
    challenge gets is the `*` rule's - the maintainer's. That is deliberate
    rather than an omission: a challenge is published under the club's name
    to every phone, and whether its places are the club's to use (design
    principle 5) is a judgement the pipeline and a maintainer make, not one
    the club makes about itself.
    """
    _refuse_unless_switched_on()
    slug = _refuse_unless_claimed(club)
    # The directory is the definition's org: the club's own slug, or a
    # publisher whose domain this club proved (the save route already held
    # it to one of the two; checked again here because this builds a path).
    org = definition.get("org") if isinstance(definition.get("org"), str) else slug
    if not may_publish_as(org, slug=slug, domain=club.domain):
        org = slug
    if not ID_RE.match(challenge_id) or not ID_RE.match(org):
        # Both are validated at the wire already; this is the opener refusing
        # to build a path from anything it has not checked itself.
        raise RegistryPrRefused("A challenge id or organization address is not a plain path segment.")
    domain = (club.domain or "").strip().lower()
    # The domain the saving org proved travels in the file, so the pipeline
    # can refuse a file under `atc/` saved by anybody but the domain
    # publishers.json names - a reviewer reading a long JSON diff should not
    # be the only thing standing between a squatter and the ATC's rules link.
    reviewed = {**definition, "published_by_domain": domain}

    return _put_up_for_review(
        client if client is not None else httpx.Client(),
        files={challenge_file(org, challenge_id): json.dumps(reviewed, indent=2, ensure_ascii=False) + "\n"},
        inside=f"{challenge_dir(org)}/",
        branch=challenge_branch_for(org, challenge_id),
        message=f"{_plain(club.name)}: challenge {challenge_id} as saved in the console",
        title=f"{_plain(club.name)}: challenge {challenge_id}",
        body=(
            f"{_plain(club.name)}'s challenge `{challenge_id}`, as its admins saved it in the organization console "
            "(features/CHALLENGES.md).\n\n"
            f"Saved by an organization that proved the domain `{domain}`. "
            f"`pipeline/reference/challenges/publishers.json` must name that domain for `{org}`, "
            "and the pipeline refuses the file if it does not.\n\n"
            "The pipeline checks every place against the club's own trails when this runs; a maintainer "
            "reviews the list and merges it or does not.\n\n"
            "**Nothing here merges itself.**"
        ),
    )
