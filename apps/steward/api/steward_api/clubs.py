"""Which clubs a weights change may name: the clubs in the analysis's summary.json.

The analysis job is the one home for the club list (it is ATC's
`Maintaining_Club` field, 29 names on 2026-10-27), so this reads the job's
published summary rather than keeping a second list to drift. Refusing an
unknown club keeps one account from minting a history for any string it likes.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import httpx

#: How long a fetched list is trusted. The job runs weekly, so an hour is
#: plenty fresh. `@unvalidated`: picked, nothing measured.
CACHE_SECONDS = 3600.0
FETCH_TIMEOUT_SECONDS = 5.0
#: summary.json was 8 KB on 2026-10-27; a body far past that is not it.
MAX_SUMMARY_BYTES = 1024 * 1024


class ClubsUnavailable(RuntimeError):
    pass


def fetch_clubs(url: str, transport: httpx.BaseTransport | None = None) -> frozenset[str]:
    """The club names in the summary at `url`. Raises ClubsUnavailable on any failure."""
    if not url.startswith("https://"):
        raise ClubsUnavailable("STEWARD_SUMMARY_URL must be an https:// address")
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False, transport=transport) as client:
            response = client.get(url)
        response.raise_for_status()
        if len(response.content) > MAX_SUMMARY_BYTES:
            raise ClubsUnavailable("summary.json is larger than any summary the job writes")
        clubs = response.json()["clubs"]
        names = frozenset(c["club"] for c in clubs if isinstance(c.get("club"), str) and c["club"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise ClubsUnavailable(f"could not read the club list from {url}: {exc}") from exc
    if not names:
        raise ClubsUnavailable(f"{url} names no clubs")
    return names


class ClubDirectory:
    def __init__(self, load: Callable[[], frozenset[str]], clock: Callable[[], float] = time.monotonic) -> None:
        self._load = load
        self._clock = clock
        self._lock = threading.Lock()
        self._names: frozenset[str] | None = None
        self._loaded_at = 0.0

    @classmethod
    def from_url(cls, url: str) -> ClubDirectory:
        def load() -> frozenset[str]:
            if not url:
                raise ClubsUnavailable("STEWARD_SUMMARY_URL is not set, so no club can be checked")
            return fetch_clubs(url)

        return cls(load)

    def names(self) -> frozenset[str]:
        """The current list. A failed refresh keeps serving the last good list
        rather than refusing everybody because a static file blinked."""
        with self._lock:
            if self._names is None or self._clock() - self._loaded_at > CACHE_SECONDS:
                try:
                    self._names = self._load()
                    self._loaded_at = self._clock()
                except ClubsUnavailable:
                    if self._names is None:
                        raise
            return self._names
