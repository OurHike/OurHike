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
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.registry_file import org_dir, registry_files
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


def open_registry_pr(db, club: Club, *, client: httpx.Client | None = None) -> OpenedPr:
    """Put this organization's registry up for its codeowners to approve."""
    if not settings.registry_pr_enabled or not settings.registry_pr_token:
        raise RegistryPrRefused("Opening registry pull requests is not switched on for this deployment.")
    if club.state != OrgState.claimed:
        raise RegistryPrRefused(
            "Only a claimed organization publishes a registry. A held registration has not been "
            "confirmed by anybody at the organization."
        )
    slug = club.slug or ""
    if not slug:
        raise RegistryPrRefused("This organization has no address yet.")

    files = registry_files(db, club)
    inside = f"{org_dir(slug)}/"
    outside = sorted(path for path in files if not path.startswith(inside))
    if outside:
        # Refused rather than filtered. A writer producing a path outside the
        # organization's directory is a writer that has gone wrong, and
        # quietly dropping the bad paths would commit the rest as if nothing
        # had happened.
        raise RegistryPrRefused(f"Refusing to write outside {inside}: {outside}")

    owned = client if client is not None else httpx.Client()
    repo = settings.registry_pr_repo
    branch = branch_for(slug)

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
        json={
            "message": f"{club.name}: registry as its codeowners signed it off",
            "tree": made_tree["sha"],
            "parents": [base_sha],
        },
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
        json={
            "title": f"{club.name}: registry",
            "head": branch,
            "base": "main",
            "body": (
                f"The registry {club.name} signed off, as files.\n\n"
                "Its codeowners are requested on this automatically - "
                "`.github/CODEOWNERS` names them against this directory.\n\n"
                "**Nothing here merges itself.**"
            ),
        },
    )
    return OpenedPr(number=opened["number"], url=opened.get("html_url", ""))
