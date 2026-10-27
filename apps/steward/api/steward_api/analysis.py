"""What the latest analysis says: which sites exist, which need work, and which clubs there are.

The analysis job is the one home for all three (apps/steward/pipeline/), and it
publishes them as sites.json beside the web app. So this reads that file
rather than keeping a second list to drift:

- a weights change must name one of its clubs (#1906), so one account cannot
  mint a history for any string it likes;
- a claim must name a site it says needs work, closing or hardening (#1910),
  so one account cannot block sites that do not exist or need nothing
  (the adversarial review's finding 2, 2026-10-27).

FAILURE IS SERVED STALE, AND NEVER RETRIED IN A STORM. A failed refresh keeps
the last good copy and waits RETRY_SECONDS before trying again; while one
request refreshes, the others are answered from what is cached rather than
queued behind it. Before 2026-10-27 a source that was down was refetched by
every request, one at a time under a lock, with a database connection held by
each waiter (the review's finding 4).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

#: How long a fetched copy is trusted. The job runs weekly. `@unvalidated`: picked.
CACHE_SECONDS = 3600.0
#: How long after a failed fetch before trying again. `@unvalidated`: picked.
RETRY_SECONDS = 60.0
FETCH_TIMEOUT_SECONDS = 10.0
#: sites.json was 4.3 MB on 2026-10-27; four times that is not it.
MAX_SITES_BYTES = 16 * 1024 * 1024
#: The actions that are work a volunteer can claim (rules.ACTIONABLE in the job).
WORKABLE_ACTIONS = frozenset({"close_restore", "harden"})


class AnalysisUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Analysis:
    clubs: frozenset[str]
    #: Every RIMS_ID in the analysis.
    sites: frozenset[str]
    #: The RIMS_IDs whose action is work: the sites that may be claimed.
    workable: frozenset[str]


def parse_sites(records: object) -> Analysis:
    if not isinstance(records, list) or not records:
        raise AnalysisUnavailable("sites.json is not a list of sites")
    clubs, sites, workable = set(), set(), set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("rims_id"), str):
            continue
        sites.add(record["rims_id"])
        if record.get("action") in WORKABLE_ACTIONS:
            workable.add(record["rims_id"])
        if isinstance(record.get("club"), str) and record["club"]:
            clubs.add(record["club"])
    if not sites:
        raise AnalysisUnavailable("sites.json names no sites")
    return Analysis(clubs=frozenset(clubs), sites=frozenset(sites), workable=frozenset(workable))


def fetch_analysis(url: str, transport: httpx.BaseTransport | None = None) -> Analysis:
    """The analysis at `url`. Raises AnalysisUnavailable on any failure."""
    if not url.startswith("https://"):
        raise AnalysisUnavailable("STEWARD_SITES_URL must be an https:// address")
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False, transport=transport) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_SITES_BYTES:
                        raise AnalysisUnavailable("sites.json is larger than any the job writes")
        return parse_sites(httpx.Response(200, content=bytes(body)).json())
    except AnalysisUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - a deeply nested file raises RecursionError, not ValueError
        raise AnalysisUnavailable(f"could not read the analysis from {url}: {exc}") from exc


class AnalysisDirectory:
    def __init__(self, load: Callable[[], Analysis], clock: Callable[[], float] = time.monotonic) -> None:
        self._load = load
        self._clock = clock
        self._lock = threading.Lock()
        self._data: Analysis | None = None
        self._loaded_at = 0.0
        self._failed_at: float | None = None
        self._refreshing = False

    @classmethod
    def from_url(cls, url: str) -> AnalysisDirectory:
        def load() -> Analysis:
            if not url:
                raise AnalysisUnavailable("STEWARD_SITES_URL is not set, so no site or club can be checked")
            return fetch_analysis(url)

        return cls(load)

    @classmethod
    def fixed(cls, analysis: Analysis) -> AnalysisDirectory:
        return cls(lambda: analysis)

    def current(self) -> Analysis:
        now = self._clock()
        with self._lock:
            fresh = self._data is not None and now - self._loaded_at < CACHE_SECONDS
            failed_recently = self._failed_at is not None and now - self._failed_at < RETRY_SECONDS
            if fresh or failed_recently or self._refreshing:
                if self._data is None:
                    raise AnalysisUnavailable("the analysis is not loaded yet")
                return self._data
            self._refreshing = True
        # Whatever the load does, the flag comes down: an exception this did not
        # expect used to leave it up for good, so nothing ever loaded again
        # (the re-check's N4).
        try:
            data = self._load()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._failed_at = self._clock()
                self._refreshing = False
                if self._data is None:
                    if isinstance(exc, AnalysisUnavailable):
                        raise
                    raise AnalysisUnavailable(str(exc)) from exc
                return self._data
        with self._lock:
            self._data = data
            self._loaded_at = self._clock()
            self._failed_at = None
            self._refreshing = False
        return data
