"""A hard ceiling on how fast this build may talk to the Internet Archive.

**No more than `MAX_REQUESTS_PER_MINUTE` leave this process in any rolling
sixty seconds** - the maintainer's instruction, and enforced here rather than
approximated by a `sleep()` between calls.

WHY A LIMITER AND NOT A SLEEP, which is what both fetchers had first. A pause
between requests only sets the average when nothing else happens. Two things
routinely happen:

  - **Retries.** A 429 waits and then fires again, and that retry is a request
    the sleep-between-calls never counted. A backoff ladder can therefore
    issue a burst while every individual pause looks obedient.
  - **More than one call per unit of work.** Recovering one page is a CDX
    lookup AND a fetch. A five-second sleep after each yields twelve a minute
    from a loop that looks like it runs at six.

A rolling window cannot be fooled by either: it counts what actually left,
whatever path it left by, and blocks until a slot is genuinely free.

WHAT THIS COST TO LEARN, 2026-09-15. `fetch_wayback_hike_photos.py` ran at one
request a second over 403 images - about 60 a minute against a documented
ceiling near 15. It earned 429s with `Retry-After` up to 47s, then 503s, then
an outright refusal of the egress IP: `curl` returning 000 with no HTTP status
at all, and the agent proxy logging "tunnel closed after 6s, 39 B received"
for `web.archive.org:443`. It was confirmed host-specific at the time -
iNaturalist answered 200 in the same minute - so it was this client's doing
and not a flaky host. The archive is donation-funded and owes this project
nothing.

NEVER IN PARALLEL, and a limiter does not change that. Concurrent connections
from one address trip the same ban regardless of how the average looks, so
both fetchers stay single-threaded and this class is deliberately not
thread-safe: making it so would invite exactly the concurrency that is
forbidden.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

#: The ceiling, in requests per minute. Ten, per the maintainer's instruction
#: of 2026-09-15 - below the ~15 the archive documents, with room for the
#: measurement being approximate and for other clients sharing this egress
#: address.
MAX_REQUESTS_PER_MINUTE = 10

WINDOW_SECONDS = 60.0


class RateLimit:
    """A rolling-window limiter. `take()` blocks until a slot is free.

    `clock` and `sleep` are injectable so the behaviour can be tested against
    a fake clock rather than by actually waiting a minute - a limiter whose
    tests are slow is a limiter whose tests get skipped.
    """

    def __init__(
        self,
        max_requests: int = MAX_REQUESTS_PER_MINUTE,
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_requests < 1:
            raise ValueError("a limiter that allows no requests is a broken fetcher, not a polite one")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._sleep = sleep
        self._sent: deque[float] = deque()

    def _forget_old(self, now: float) -> None:
        while self._sent and now - self._sent[0] >= self.window_seconds:
            self._sent.popleft()

    def take(self) -> float:
        """Block until another request may be sent; return how long it waited.

        The wait is returned rather than printed so a caller can report it
        without this module deciding what a log line looks like.
        """
        waited = 0.0
        while True:
            now = self._clock()
            self._forget_old(now)
            if len(self._sent) < self.max_requests:
                self._sent.append(now)
                return waited
            # The oldest request in the window is the one whose expiry frees a
            # slot. Waiting any less would wake up and find the window still
            # full, which is a busy loop wearing a sleep.
            wait = self.window_seconds - (now - self._sent[0])
            if wait <= 0:
                continue
            self._sleep(wait)
            waited += wait


#: One limiter for the process, so that two fetchers run in the same session
#: cannot each spend the full allowance and together double it. Both archive
#: fetchers take from this rather than building their own.
ARCHIVE = RateLimit()
