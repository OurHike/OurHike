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


#: How many consecutive give-ups mean the archive is refusing this CLIENT
#: rather than declining one URL (#1522).
#:
#: A give-up is a request that exhausted its caller's whole backoff ladder.
#: One of those is an ordinary fact about a corpus: a capture the archive
#: holds but will not serve today, which
#: fetch_wayback_hike_pages.py deliberately costs that page and not the run.
#: Three in a row is twelve refused requests, and the ladder in both fetchers
#: is 30 + 120 + 300 seconds per URL.
#:
#: HOW LONG THAT TAKES IS NOT BOUNDED BY THE THREE, and the first version of
#: this comment said "about 22 minutes" as though it were. Corrected against
#: run 35128687766 (2026-09-16), which stopped after **53 minutes**: the
#: archive served that runner intermittently - 3 write-ups recovered, 4
#: refused, of 7 attempted - and every served response resets the count, by
#: design, so the run only ended once three refusals landed genuinely
#: back-to-back. 22 minutes is the floor, reached only when the host refuses
#: from the first request and refuses quickly; a host that answers slowly or
#: in patches takes longer, and a run that is working is supposed to.
#:
#: @unvalidated - THREE IS PICKED, and what would settle it is the
#: distribution of consecutive give-ups on a run that went on to FINISH,
#: which no run here has yet recorded; 35128687766 is one refused run, not a
#: distribution. What is measured is the asymmetry that argues for a low
#: number, and it is what this rests on: at three, a refused run stopped in
#: 53 minutes having banked what it got, against run 35092759225 the same
#: day spending a whole 330-minute job on 42 of 444 write-ups and banking
#: nothing. Being wrong here costs a re-dispatch; being wrong the other way
#: cost five and a half hours. That is why this is not tuned upward without
#: the measurement.
MAX_CONSECUTIVE_REFUSALS = 3


class ArchiveRefusing(RuntimeError):
    """The archive has refused several requests in a row, so it is refusing us.

    Raised rather than returned because the callers are loops whose whole
    design is that one refused URL costs that URL. That is right until the
    host is refusing everything, at which point continuing is neither polite
    nor useful - and an exception is the one thing a `continue` cannot
    swallow.

    A caller catches this, WRITES WHAT IT HAS, and reports. Losing the
    recovered rows to the same event that stopped the fetch is the failure
    #1522 exists to end, so an unhandled escape of this class is a bug.
    """


class Refusals:
    """Counts give-ups in a row, and trips when there have been too many.

    Separate from `RateLimit` above because they answer opposite questions:
    the limiter decides when this build may SEND, and this decides when it
    should stop asking. They travel together only in that both are about the
    same host's patience.

    WHAT COUNTS AS BEING SERVED is the part worth getting right, and it is
    not "the answer was useful". An HTTP 404 from the archive is the archive
    working - it answered, and what it said is that it has no capture. A
    corpus full of those would trip a tripwire that counted them, and report
    a refusal that never happened.

    So `served()` is called for a response the caller takes as FINAL - a 200
    or a 404 alike - and `refused()` only where a caller has exhausted its
    ladder. The status in between, a 503 the caller is about to retry, is
    neither: calling `served()` on it would reset the count inside every
    ladder and the tripwire could never trip at all.
    """

    def __init__(self, ceiling: int = MAX_CONSECUTIVE_REFUSALS) -> None:
        if ceiling < 1:
            raise ValueError("a tripwire that trips before anything is refused would stop every run")
        self.ceiling = ceiling
        self.consecutive = 0

    def served(self) -> None:
        """The host answered. Whatever it said, it is not refusing us."""
        self.consecutive = 0

    def refused(self, what: str) -> None:
        """A request exhausted its ladder. Trip if that is now a pattern."""
        self.consecutive += 1
        if self.consecutive >= self.ceiling:
            raise ArchiveRefusing(
                f"{self.consecutive} requests in a row exhausted their retries, most recently {what}. "
                "The archive is refusing this client rather than declining one URL - see lib/wayback_rate.py."
            )


#: One tripwire for the process, for the same reason ARCHIVE is one limiter:
#: two fetchers sharing an egress address share the refusal too.
REFUSALS = Refusals()
