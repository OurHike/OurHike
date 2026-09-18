"""The work a hiker's browser does before this server will read a website.

See ../../../features/ORG_ONBOARDING.md's "Nominating an organization". The
maintainer's 2026-09-17 decision had three parts and this is the third:
signed in, *and* a challenge, before we fetch an address a stranger typed.

Each bound does something the others do not. Signing in bounds **who** can
ask. `app/core/assist.py`'s budget bounds **how much** gets spent. Neither
bounds **how fast one account can ask**, and a single signed-in account
driving this endpoint in a loop is a fetcher farm pointed at other people's
websites, in our name and out of our address space.

**A PROOF OF WORK RATHER THAN A CAPTCHA.** A CAPTCHA means a third party
watching every hiker who nominates a club - on a page whose entire subject
is somebody else's public data, and in a project whose stated values put
that third party where it can be seen. The arithmetic here happens in the
hiker's own browser, tells us nothing about them, and needs no vendor. It
costs an honest person one moment and somebody running a thousand of them a
thousand moments, which is the shape of the thing that was asked for: it
does not stop any single use and is not meant to.

**THE SERVER STORES NO CHALLENGE IT ISSUES.** A challenge carries its own
HMAC over every field that matters - nonce, subject, difficulty, expiry - so
a forged or edited one fails with nothing having been written down. The one
fact that must be stored is that a nonce has been **spent**, because without
it a solved challenge is a token good forever: one solve for an attacker and
then nothing, while still costing every honest hiker one. `spend` is
injected rather than imported so this module stays testable and so the
ledger can move without it noticing.

**A WRONG ANSWER DOES NOT BURN THE NONCE.** The checks run in the order
signature, expiry, shape, work, and only then spend. The other order lets
anybody who learns a nonce spend it with garbage and make the hiker who
earned it start over, which costs the attacker nothing and is a nuisance
worth designing out.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass

# The floor exists so a bug that mints an easy challenge is refused at
# verification too, rather than quietly accepting free work. 12 bits is
# roughly 4,000 hashes - a blink, and deliberately cheap so the test suite
# can solve dozens without being slow.
MIN_DIFFICULTY = 12

# The ceiling is a guard against the same bug in the other direction: a
# challenge nobody's phone can solve is an outage that looks like a hang.
MAX_DIFFICULTY = 24

# MEASURED 2026-09-17, and the measurement changed the design rather than
# confirming it. Timings are medians of 15 solves on this repository's CI-class
# container, using a synchronous JS SHA-256 verified byte-identical to
# `crypto.subtle.digest('SHA-256', ...)`:
#
#     16 bits   median   78 ms   p90   235 ms
#     18 bits   median  437 ms   p90 1,207 ms
#     20 bits   median 2,210 ms  p90 4,921 ms
#
# The first attempt measured WebCrypto called once per candidate and got
# 2,887 ms at 16 bits - about 44 microseconds a hash, nearly all of it the
# `await`. So the browser side must hash synchronously; a proof of work built
# on `await crypto.subtle.digest` in a loop is thirty times more expensive
# than it looks, for the honest hiker and not for anybody else.
#
# 18 is the default because half a second is a wait a spinner covers and
# 20 is not. The spread is wide because the number of attempts is geometric,
# not because the machine is noisy: p90 is around 2.8x the median at every
# difficulty, and a hiker occasionally waits three seconds.
#
# @unvalidated on a phone. Every figure above is a container with a desktop
# CPU. A mid-range phone is commonly two to four times slower at single-thread
# JavaScript, which would put p90 between two and five seconds - tolerable
# next to a fetch that takes seconds anyway, but nobody has run it on real
# hardware. What would settle it: this solver in a page, on a phone somebody
# actually owns, at 16, 18 and 20 bits.
DEFAULT_DIFFICULTY = 18

# Long enough to solve on a slow phone and to think about what you are
# nominating, short enough that a stockpile of unsolved challenges goes stale.
DEFAULT_TTL = 600

# What a solution may look like, so a hostile one cannot be long or strange.
# The reference solver emits decimal integers; the bound is far above what
# MAX_DIFFICULTY needs.
_MAX_ANSWER = 64
_ANSWER_ALPHABET = frozenset(string.ascii_letters + string.digits + "-_")


class ChallengeRefused(Exception):
    """This challenge does not entitle anybody to a fetch, and why."""


@dataclass(frozen=True)
class Challenge:
    """What the browser is given. Everything here is public by design."""

    nonce: str
    difficulty: int
    expires_at: int
    signature: str


def leading_zero_bits(digest: bytes) -> int:
    """How many zero bits a digest opens with.

    Bits rather than hex characters, so difficulty moves by factors of two
    rather than sixteen - four steps of tuning where there would be one.
    """
    count = 0
    for byte in digest:
        if byte == 0:
            count += 8
            continue
        count += 8 - byte.bit_length()
        break
    return count


def _sign(*, nonce: str, subject: str, difficulty: int, expires_at: int, secret: str) -> str:
    """The HMAC over everything a tamperer would want to change.

    The subject is inside it rather than beside it: a challenge issued to one
    hiker and presented by another has to fail, and there is nothing to swap
    without invalidating the whole thing.
    """
    message = f"{nonce}|{subject}|{difficulty}|{expires_at}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def issue(
    subject: str,
    *,
    secret: str,
    now: int,
    difficulty: int = DEFAULT_DIFFICULTY,
    ttl: int = DEFAULT_TTL,
) -> Challenge:
    """Mint one challenge for one hiker.

    `now` is passed rather than read so that expiry is testable and so this
    module has no clock of its own to disagree with the caller's.
    """
    if not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
        raise ValueError(f"difficulty {difficulty} is outside {MIN_DIFFICULTY}-{MAX_DIFFICULTY}")
    nonce = secrets.token_urlsafe(18)
    expires_at = now + ttl
    return Challenge(
        nonce=nonce,
        difficulty=difficulty,
        expires_at=expires_at,
        signature=_sign(
            nonce=nonce,
            subject=subject,
            difficulty=difficulty,
            expires_at=expires_at,
            secret=secret,
        ),
    )


def solve(challenge: Challenge) -> str:
    """The reference solution, in the server's own language.

    Here so the tests exercise the real thing rather than a fixture, and so
    the browser implementation has something to agree with. It is not used in
    production - the whole point is that the browser does this work.
    """
    for attempt in range(1 << 32):  # pragma: no branch - returns long before
        answer = str(attempt)
        if leading_zero_bits(_digest(challenge.nonce, answer)) >= challenge.difficulty:
            return answer
    raise RuntimeError("no solution found")  # pragma: no cover


def _digest(nonce: str, answer: str) -> bytes:
    return hashlib.sha256(f"{nonce}:{answer}".encode()).digest()


def verify(
    challenge: Challenge,
    answer: str,
    *,
    subject: str,
    secret: str,
    spend,
    now: int,
) -> None:
    """Accept this challenge once, or say why not.

    `spend(nonce)` returns True if the nonce was not already spent and is now.
    It is called last, deliberately - see the module header.
    """
    if not isinstance(challenge.difficulty, int) or not (MIN_DIFFICULTY <= challenge.difficulty <= MAX_DIFFICULTY):
        raise ChallengeRefused("That challenge asks for the wrong amount of work.")

    expected = _sign(
        nonce=challenge.nonce,
        subject=subject,
        difficulty=challenge.difficulty,
        expires_at=challenge.expires_at,
        secret=secret,
    )
    if not hmac.compare_digest(expected, challenge.signature or ""):
        raise ChallengeRefused("That challenge was not issued to you.")

    if now >= challenge.expires_at:
        raise ChallengeRefused("That challenge has expired. Ask for another and try again.")

    answer = (answer or "").strip()
    if not answer or len(answer) > _MAX_ANSWER or not set(answer) <= _ANSWER_ALPHABET:
        raise ChallengeRefused("That is not an answer to the challenge.")

    if leading_zero_bits(_digest(challenge.nonce, answer)) < challenge.difficulty:
        raise ChallengeRefused("That answer does not solve the challenge.")

    if not spend(challenge.nonce):
        raise ChallengeRefused("That challenge has already been used.")
