"""Tests for lib/wayback_rate.py - the hard ceiling on requests to the
Internet Archive (#1450).

Driven by a FAKE CLOCK, so the rolling window is proved rather than waited
out. A limiter whose tests take a real minute is a limiter whose tests get
skipped, and then the ceiling it promises is not checked by anything.

The load-bearing test is `test_a_retry_cannot_slip_past_the_ceiling`. Both
archive fetchers had a `sleep()` between calls before this module existed, and
a sleep sets the average only when nothing else fires - a backoff ladder can
issue a burst while every individual pause looks obedient. That is how one
request a second became an egress IP refused outright on 2026-09-15.
"""

import pytest

from lib import wayback_rate


class FakeClock:
    """A clock the tests advance by hand. `sleep` moves it, exactly as a real
    sleep would, so the limiter cannot tell the difference."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _limiter(max_requests=10, window=60.0):
    clock = FakeClock()
    return wayback_rate.RateLimit(max_requests, window, clock=clock.time, sleep=clock.sleep), clock


# --- the ceiling ---------------------------------------------------------------


def test_the_shipped_ceiling_is_ten_a_minute():
    """The maintainer's instruction of 2026-09-15, pinned so a later change
    has to be deliberate."""
    assert wayback_rate.MAX_REQUESTS_PER_MINUTE == 10
    assert wayback_rate.WINDOW_SECONDS == 60.0


def test_the_first_requests_up_to_the_ceiling_do_not_wait():
    limiter, clock = _limiter(max_requests=10)

    for _ in range(10):
        assert limiter.take() == 0.0

    assert clock.slept == []


def test_the_eleventh_request_waits_for_the_window_to_roll():
    """Ten are allowed in any sixty seconds. The eleventh waits until the
    first has aged out, not for some fixed pause."""
    limiter, clock = _limiter(max_requests=10)
    for _ in range(10):
        limiter.take()

    waited = limiter.take()

    assert waited == pytest.approx(60.0)


def test_requests_spread_over_the_window_never_wait():
    """A caller already pacing itself pays nothing. The limiter is a ceiling,
    not a metronome that slows down work already under the limit."""
    limiter, clock = _limiter(max_requests=10)

    for _ in range(30):
        assert limiter.take() == 0.0
        clock.now += 6.1  # just over 10/min

    assert clock.slept == []


def test_a_slot_frees_exactly_when_the_oldest_request_ages_out():
    limiter, clock = _limiter(max_requests=2, window=60.0)
    limiter.take()
    clock.now += 25.0
    limiter.take()

    waited = limiter.take()

    # The oldest was 25s ago, so 35s of its minute remain.
    assert waited == pytest.approx(35.0)


def test_never_more_than_the_ceiling_in_any_rolling_window():
    """The property the whole module exists for, checked directly: slide a
    sixty-second window over every request that was issued and assert no
    position holds more than the ceiling."""
    limiter, clock = _limiter(max_requests=10, window=60.0)
    issued = []
    for _ in range(50):
        limiter.take()
        issued.append(clock.now)
        clock.now += 0.001  # a caller with no pacing of its own at all

    for start in issued:
        in_window = [t for t in issued if start <= t < start + 60.0]
        assert len(in_window) <= 10


# --- the case a sleep could not cover -------------------------------------------


def test_a_retry_cannot_slip_past_the_ceiling():
    """THE test. A retry is a request. Both fetchers call `take()` INSIDE the
    retry loop for this reason - a ladder that backs off politely and then
    fires an uncounted request is how a sleep-based throttle exceeds its own
    ceiling while every individual pause looks obedient."""
    limiter, clock = _limiter(max_requests=3, window=60.0)

    # Three real requests, then three "retries" - six attempts, cap of three.
    for _ in range(3):
        assert limiter.take() == 0.0
    total_waited = sum(limiter.take() for _ in range(3))

    assert total_waited > 0
    assert clock.now >= 1000.0 + 60.0


def test_two_fetchers_in_one_process_share_the_allowance():
    """ARCHIVE is module-level so that running both archive fetchers in one
    session cannot spend the allowance twice and together double it."""
    import fetch_wayback_hike_pages as pages
    import fetch_wayback_hike_photos as photos

    assert photos.ARCHIVE is pages.ARCHIVE is wayback_rate.ARCHIVE


# --- refusals ------------------------------------------------------------------


def test_a_limiter_that_allows_nothing_is_refused():
    """Zero is not a very polite fetcher, it is a hung one, and the failure
    would look like the archive being slow."""
    with pytest.raises(ValueError):
        wayback_rate.RateLimit(max_requests=0)
