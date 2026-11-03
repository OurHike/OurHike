"""The work a hiker's browser does before this server will read a website.

The maintainer's 2026-09-17 decision on the nominate flow had three parts,
and this is the third: signed in, *and* a challenge, before we fetch an
address a stranger typed. Signing in bounds who can ask. The budget in
`app/core/assist.py` bounds how much one org can spend. Neither bounds how
fast one signed-in account can ask, and "make a challenge to stop anyone who
might be attempting to scrape the page" is that third bound.

**A PROOF OF WORK, NOT A CAPTCHA.** A CAPTCHA means a third party watching
every hiker who nominates a club, on a page whose entire subject is somebody
else's public data. The work here is arithmetic in the hiker's own browser,
costs an honest person a moment, and costs somebody running a thousand of
them a thousand moments. It stops bulk use rather than any single use, which
is what was asked for.

**THE SERVER KEEPS NO CHALLENGE IT ISSUED.** The challenge carries its own
HMAC, so a forged one fails without anything having been stored. The one
thing that does need storing is that a nonce has been spent - without it a
solved challenge is a token good forever, which is worse than no challenge.
"""

import pytest

from app.core.challenge import (
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    Challenge,
    ChallengeRefused,
    issue,
    leading_zero_bits,
    solve,
    verify,
)

SECRET = "a secret nobody outside this process has"
HIKER = "11111111-1111-1111-1111-111111111111"
SOMEBODY_ELSE = "22222222-2222-2222-2222-222222222222"
NOW = 1_780_000_000


def unspent():
    """A ledger nothing has been spent against yet."""
    spent: set[str] = set()

    def spend(nonce: str) -> bool:
        if nonce in spent:
            return False
        spent.add(nonce)
        return True

    return spend


def already_spent(nonce_to_block: str):
    def spend(nonce: str) -> bool:
        return nonce != nonce_to_block

    return spend


class TestCountingTheWork:
    @pytest.mark.parametrize(
        "digest,bits",
        [
            (b"\xff", 0),
            (b"\x7f", 1),
            (b"\x01", 7),
            (b"\x00\xff", 8),
            (b"\x00\x7f", 9),
            (b"\x00\x00\x01", 23),
            (b"\x00\x00\x00", 24),
        ],
    )
    def test_the_bits_are_counted_from_the_front(self, digest, bits):
        assert leading_zero_bits(digest) == bits


class TestIssuingOne:
    def test_a_challenge_carries_no_secret(self):
        """Whoever holds it can solve it. Nobody holding it can mint another."""
        challenge = issue(HIKER, secret=SECRET, now=NOW)
        assert SECRET not in str(challenge.__dict__)

    def test_two_challenges_are_not_the_same(self):
        """A reused nonce is a solved challenge somebody else can present."""
        first = issue(HIKER, secret=SECRET, now=NOW)
        second = issue(HIKER, secret=SECRET, now=NOW)
        assert first.nonce != second.nonce

    def test_the_difficulty_stays_inside_its_bounds(self):
        with pytest.raises(ValueError):
            issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY - 1)
        with pytest.raises(ValueError):
            issue(HIKER, secret=SECRET, now=NOW, difficulty=MAX_DIFFICULTY + 1)

    def test_it_expires(self):
        challenge = issue(HIKER, secret=SECRET, now=NOW, ttl=300)
        assert challenge.expires_at == NOW + 300


class TestSolvingAndVerifying:
    def test_a_solved_challenge_is_accepted(self):
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        answer = solve(challenge)
        verify(challenge, answer, subject=HIKER, secret=SECRET, spend=unspent(), now=NOW)

    def test_an_unsolved_challenge_is_refused(self):
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        with pytest.raises(ChallengeRefused):
            verify(challenge, "not the answer", subject=HIKER, secret=SECRET, spend=unspent(), now=NOW)

    def test_a_challenge_issued_to_one_hiker_cannot_be_spent_by_another(self):
        """Otherwise one solved challenge is a service for everybody else.

        The subject is inside the signature rather than beside it, so there
        is nothing to swap without invalidating the whole thing.
        """
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        answer = solve(challenge)
        with pytest.raises(ChallengeRefused):
            verify(challenge, answer, subject=SOMEBODY_ELSE, secret=SECRET, spend=unspent(), now=NOW)

    def test_an_expired_challenge_is_refused_however_well_it_was_solved(self):
        challenge = issue(HIKER, secret=SECRET, now=NOW, ttl=300, difficulty=MIN_DIFFICULTY)
        answer = solve(challenge)
        with pytest.raises(ChallengeRefused):
            verify(challenge, answer, subject=HIKER, secret=SECRET, spend=unspent(), now=NOW + 301)

    def test_a_nonce_is_good_once(self):
        """Without this a solved challenge is a token that never expires.

        Which is strictly worse than no challenge: it costs an attacker one
        solve and then nothing, while still costing every honest hiker one.
        """
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        answer = solve(challenge)
        spend = unspent()
        verify(challenge, answer, subject=HIKER, secret=SECRET, spend=spend, now=NOW)
        with pytest.raises(ChallengeRefused):
            verify(challenge, answer, subject=HIKER, secret=SECRET, spend=spend, now=NOW)

    def test_a_nonce_the_ledger_has_already_seen_is_refused(self):
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        answer = solve(challenge)
        with pytest.raises(ChallengeRefused):
            verify(
                challenge,
                answer,
                subject=HIKER,
                secret=SECRET,
                spend=already_spent(challenge.nonce),
                now=NOW,
            )

    def test_the_work_is_not_spent_when_the_answer_is_wrong(self):
        """A wrong answer must not burn the nonce.

        Otherwise anybody who learns a nonce can spend it with garbage and
        make the hiker who earned it start over - a nuisance that costs the
        attacker nothing.
        """
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        spends: list[str] = []

        def spend(nonce: str) -> bool:
            spends.append(nonce)
            return True

        with pytest.raises(ChallengeRefused):
            verify(challenge, "wrong", subject=HIKER, secret=SECRET, spend=spend, now=NOW)
        assert spends == []


class TestTampering:
    def test_a_lowered_difficulty_is_refused(self):
        """The cheapest attack there is: ask for 18 bits, present 1.

        The difficulty is inside the signature, so changing it invalidates
        the challenge rather than making it easier.
        """
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY + 4)
        weakened = Challenge(
            nonce=challenge.nonce,
            difficulty=MIN_DIFFICULTY,
            expires_at=challenge.expires_at,
            signature=challenge.signature,
        )
        with pytest.raises(ChallengeRefused):
            verify(weakened, solve(weakened), subject=HIKER, secret=SECRET, spend=unspent(), now=NOW)

    def test_a_stretched_expiry_is_refused(self):
        challenge = issue(HIKER, secret=SECRET, now=NOW, ttl=300, difficulty=MIN_DIFFICULTY)
        stretched = Challenge(
            nonce=challenge.nonce,
            difficulty=challenge.difficulty,
            expires_at=challenge.expires_at + 86_400,
            signature=challenge.signature,
        )
        with pytest.raises(ChallengeRefused):
            verify(stretched, solve(stretched), subject=HIKER, secret=SECRET, spend=unspent(), now=NOW + 400)

    def test_a_challenge_minted_against_another_secret_is_refused(self):
        challenge = issue(HIKER, secret="somebody else's secret", now=NOW, difficulty=MIN_DIFFICULTY)
        with pytest.raises(ChallengeRefused):
            verify(challenge, solve(challenge), subject=HIKER, secret=SECRET, spend=unspent(), now=NOW)

    def test_a_difficulty_below_the_floor_is_refused_even_when_properly_signed(self):
        """Belt to the signature's braces.

        If a bug ever mints a challenge at difficulty 1, verification still
        refuses it rather than quietly accepting free work.
        """
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        weak = Challenge(
            nonce=challenge.nonce,
            difficulty=0,
            expires_at=challenge.expires_at,
            signature=_resign(challenge, difficulty=0),
        )
        with pytest.raises(ChallengeRefused):
            verify(weak, solve(weak), subject=HIKER, secret=SECRET, spend=unspent(), now=NOW)

    @pytest.mark.parametrize("answer", ["", "   ", "x" * 500, "\x00"])
    def test_nonsense_answers_are_refused_rather_than_raising(self, answer):
        challenge = issue(HIKER, secret=SECRET, now=NOW, difficulty=MIN_DIFFICULTY)
        with pytest.raises(ChallengeRefused):
            verify(challenge, answer, subject=HIKER, secret=SECRET, spend=unspent(), now=NOW)


def _resign(challenge: Challenge, *, difficulty: int) -> str:
    """A correctly-signed challenge at a difficulty `issue` would not mint."""
    from app.core.challenge import _sign

    return _sign(
        nonce=challenge.nonce,
        subject=HIKER,
        difficulty=difficulty,
        expires_at=challenge.expires_at,
        secret=SECRET,
    )
