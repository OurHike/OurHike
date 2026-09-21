"""Opening the pull request an organization's codeowners review.

**WHY A SERVICE IDENTITY AND NOT AN ADMIN.** Opening a pull request needs
write access to the repository, and an org admin has no GitHub account here
- giving one the power to cause a push would make every org admin a
committer to a public repository. Approving needs no write access at all,
which is why the codeowners can do that with their own accounts and this
cannot be theirs. The two halves were run together in `sign_off_registry`'s
docstring and they are different questions.

**THE GUARD WITH TEETH IS CONTAINMENT.** GitHub-side scoping of the token is
somebody's console setting and not something this repository can assert. What
it can assert is that this code never writes a path outside the organization's
own directory - which is the bug that would matter, because a write outside it
is a change to this repository that no organization's codeowners review and no
test here would otherwise catch.

**AND IT NEVER MERGES.** CLAUDE.md's rule, applied to the one piece of code in
this repository that holds a token which could.
"""

import httpx
import pytest

from app.core.registry_pr import RegistryPrRefused, open_registry_pr
from app.models.club import OrgState
from tests.factories import make_org, make_section


class Recorder:
    """Every request the opener made, and a canned GitHub to make them against."""

    def __init__(self, *, existing_pulls=None):
        self.calls: list[tuple[str, str, dict]] = []
        self._existing = existing_pulls or []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.content) if request.content else {}
            self.calls.append((request.method, request.url.path, body))

            if request.method == "GET" and request.url.path.endswith("/git/ref/heads/main"):
                return httpx.Response(200, json={"object": {"sha": "basesha"}})
            if request.method == "GET" and request.url.path.endswith("/pulls"):
                return httpx.Response(200, json=self._existing)
            if request.method == "POST" and request.url.path.endswith("/git/blobs"):
                return httpx.Response(201, json={"sha": "blobsha"})
            if request.method == "POST" and request.url.path.endswith("/git/trees"):
                return httpx.Response(201, json={"sha": "treesha"})
            if request.method == "POST" and request.url.path.endswith("/git/commits"):
                return httpx.Response(201, json={"sha": "commitsha"})
            if request.method == "POST" and request.url.path.endswith("/git/refs"):
                return httpx.Response(201, json={"ref": "refs/heads/x"})
            if request.method == "PATCH":
                return httpx.Response(200, json={})
            if request.method == "POST" and request.url.path.endswith("/pulls"):
                return httpx.Response(201, json={"number": 42, "html_url": "https://github.com/OurHike/OurHike/pull/42"})
            return httpx.Response(404, json={})

        return httpx.MockTransport(handler)

    def paths_written(self) -> list[str]:
        for method, path, body in self.calls:
            if method == "POST" and path.endswith("/git/trees"):
                return [entry["path"] for entry in body.get("tree", [])]
        return []


@pytest.fixture
def enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "registry_pr_enabled", True, raising=False)
    monkeypatch.setattr(settings, "registry_pr_token", "a-token", raising=False)
    monkeypatch.setattr(settings, "registry_pr_repo", "OurHike/OurHike", raising=False)
    return settings


class TestTheSwitch:
    def test_it_is_off_until_somebody_turns_it_on(self, client, db_session):
        """A merge is not a decision to start opening pull requests on a
        public repository, which is the same argument `mail_enabled` makes."""
        club = make_org(db_session, state=OrgState.claimed)

        with pytest.raises(RegistryPrRefused):
            open_registry_pr(db_session, club, client=httpx.Client(transport=Recorder().transport()))

    def test_a_held_registration_opens_nothing(self, client, db_session, enabled):
        """`pending` means nobody at the organization has confirmed it exists
        here. Publishing its registry would put our name behind a squat."""
        club = make_org(db_session, state=OrgState.pending)
        recorder = Recorder()

        with pytest.raises(RegistryPrRefused):
            open_registry_pr(db_session, club, client=httpx.Client(transport=recorder.transport()))

        assert recorder.calls == []


class TestWhatItWrites:
    def test_every_path_is_inside_the_organizations_own_directory(self, client, db_session, enabled):
        """The guard with teeth. A path outside it is a change to this
        repository that no organization's codeowners review."""
        club = make_org(db_session, state=OrgState.claimed)
        make_section(db_session, club, name="Pine Meadow North")
        recorder = Recorder()

        open_registry_pr(db_session, club, client=httpx.Client(transport=recorder.transport()))

        written = recorder.paths_written()
        assert written
        for path in written:
            assert path.startswith("pipeline/reference/orgs/ramapo-trail-conference/")

    def test_one_commit_rather_than_one_per_file(self, client, db_session, enabled):
        """A registry arriving as eleven commits is eleven things to read
        in a review that should be one."""
        club = make_org(db_session, state=OrgState.claimed)
        make_section(db_session, club, name="Pine Meadow North")
        recorder = Recorder()

        open_registry_pr(db_session, club, client=httpx.Client(transport=recorder.transport()))

        commits = [call for call in recorder.calls if call[0] == "POST" and call[1].endswith("/git/commits")]
        assert len(commits) == 1


class TestWhatItNeverDoes:
    def test_it_never_merges(self, client, db_session, enabled):
        """CLAUDE.md's rule, on the one piece of code here holding a token
        that could."""
        club = make_org(db_session, state=OrgState.claimed)
        make_section(db_session, club, name="Pine Meadow North")
        recorder = Recorder()

        open_registry_pr(db_session, club, client=httpx.Client(transport=recorder.transport()))

        assert not any("/merge" in path for _, path, _ in recorder.calls)

    def test_a_second_call_reuses_the_open_pull_request(self, client, db_session, enabled):
        """An organization pressing sign off twice should not have two pull
        requests open against its own registry, each half-reviewed."""
        club = make_org(db_session, state=OrgState.claimed)
        make_section(db_session, club, name="Pine Meadow North")
        recorder = Recorder(
            existing_pulls=[{"number": 7, "html_url": "https://example/7", "head": {"ref": "registry/ramapo-trail-conference"}}]
        )

        result = open_registry_pr(db_session, club, client=httpx.Client(transport=recorder.transport()))

        assert result.number == 7
        assert not any(call[0] == "POST" and call[1].endswith("/pulls") for call in recorder.calls)

    def test_a_failure_is_a_refusal_rather_than_a_retry(self, client, db_session, enabled):
        """The same posture as `core/assist.py`: a retry against a remote
        that just failed is how one stuck request becomes ten."""
        club = make_org(db_session, state=OrgState.claimed)
        make_section(db_session, club, name="Pine Meadow North")
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            return httpx.Response(500, json={})

        with pytest.raises(RegistryPrRefused):
            open_registry_pr(db_session, club, client=httpx.Client(transport=httpx.MockTransport(handler)))

        assert len(calls) == 1
