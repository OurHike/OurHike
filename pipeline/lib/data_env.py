"""Which environment's data a publisher writes and a checker reads.

[../features/DATA_ENVIRONMENTS.md](../../features/DATA_ENVIRONMENTS.md) is the
design; this is the half a test can run. It answers one question - "where in
the bucket does this environment's data live?" - and `publish.py` asks it
before it uploads anything.

WHY AN ENVIRONMENT IS A PREFIX AND NOT A BUCKET

[../RELEASING.md](../../RELEASING.md) §3 has three environments and one
bucket. Keeping it one bucket is the answer §14.2 already gave and this does
not disturb: UA reads through the same CORS policy, the same `r2.dev` host and
the same range machinery a phone uses, so what UA verifies is delivered by the
infrastructure production is delivered by. A second bucket would be a second
policy to keep in step, and LAUNCH_CHECKLIST.md already names two allow-lists
as "the same mistake waiting to happen twice".

What that answer did not cover is that every key published today is *mutable* -
a publish is a `PutObject` over a live key. Two environments sharing a mutable
key do not share data, they collide: a UA publish lands on the bytes a hiker is
downloading. So the prefix is what makes one bucket safe, rather than a
compromise against a bucket per environment.

WHY PRODUCTION IS THE ROOT AND NOT `environments/production/`

Because a published key is permanent. `publish()`'s manifest merge is
additive-only and app-store builds cannot be forced forward, so every key that
is live today is a URL some phone will go on requesting - moving production
under a prefix would rename all of them at once. Tidiness is not worth a 404 on
a mountain, and the asymmetry is the rule rather than an exception to it:
production is where the data already is, and every other environment is
somewhere it has never been.

WHY THE SET IS CLOSED

`OURHIKE_DATA_ENV=uat` is a typo, and an open set would answer it by publishing
a complete dataset into a tree nothing reads, nothing prunes and nobody is
looking at. That is the same reasoning `r2_keys.TOP_LEVEL_PREFIXES` records for
prefixes, and the names here are RELEASING.md §3's three so the two cannot
drift into disagreeing about how many environments exist.
"""

from __future__ import annotations

import os
import re

# RELEASING.md §3's three, spelled the way that table spells them.
#
# `dev` publishes to R2 rarely and deliberately - a field test needs real bytes
# over a real network, which is the one thing a laptop's static server cannot
# be. It is declared here so that when somebody does it, it lands somewhere
# named rather than on top of production.
PRODUCTION = "production"
UA = "ua"
DEV = "dev"

ENVIRONMENTS = (PRODUCTION, UA, DEV)

# The top-level prefix every non-production environment lives under. Named to
# be read rather than to be short - the same choice `_internal/` made, and for
# the same reason: somebody listing this bucket should not have to be told what
# they are looking at.
ENVIRONMENTS_PREFIX = "environments"

# How a publisher says which environment it is. Read from the environment only,
# never inferred - see `resolve`.
ENVIRONMENT_VAR = "OURHIKE_DATA_ENV"

# Legal as a single R2 path segment, so that an environment name can never be
# the thing that makes a key illegal. Deliberately narrower than
# `r2_keys.DIR_PATTERN` allows, because these are not discovered names: they
# are the three above.
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class UnknownEnvironment(ValueError):
    """A name that is not one of ENVIRONMENTS. Its own type because `publish.py`
    turns it into a message and an exit code rather than a traceback."""


def validate(name: str) -> str:
    """Return `name` if it is an environment, or raise saying what it is not.

    Both halves of the check earn their place. The membership test catches the
    typo; the pattern test catches a name that would be a legal environment and
    an illegal key, which is a failure that would otherwise surface as a
    confusing complaint about the layout several frames away from the mistake.
    """
    if name not in ENVIRONMENTS:
        raise UnknownEnvironment(
            f"'{name}' is not one of this project's data environments ({', '.join(ENVIRONMENTS)}). "
            f"Adding one is a design decision - see features/DATA_ENVIRONMENTS.md - rather than a "
            f"value {ENVIRONMENT_VAR} may take."
        )
    if not NAME_PATTERN.match(name):
        raise UnknownEnvironment(f"'{name}' is not usable as a bucket path segment")
    return name


def resolve(name: str | None = None) -> str:
    """The environment to act on: `name` if given, else `$OURHIKE_DATA_ENV`.

    **Unset is a refusal, not production.** A publisher that does not say which
    environment it is publishing to is a publisher whose author did not decide,
    and the cost of guessing wrong is asymmetric to the point of being no
    contest - guessing `ua` wastes a run, guessing `production` overwrites what
    hikers download. There is no default for the same reason
    `publish.writes_enabled()` has no default: the dangerous direction is the
    one that must be typed out.
    """
    raw = (name if name is not None else os.environ.get(ENVIRONMENT_VAR, "")).strip()
    if not raw:
        raise UnknownEnvironment(
            f"No data environment is set. Export {ENVIRONMENT_VAR}=<{'|'.join(ENVIRONMENTS)}> before publishing - "
            f"there is deliberately no default, because the only safe default would be the one that overwrites "
            f"what hikers download (features/DATA_ENVIRONMENTS.md)."
        )
    return validate(raw)


def prefix_for(name: str) -> str:
    """The key prefix this environment's objects live under, `''` for
    production, otherwise `environments/<name>/` - trailing slash included so
    that concatenation is the whole of `scope_key`."""
    if validate(name) == PRODUCTION:
        return ""
    return f"{ENVIRONMENTS_PREFIX}/{name}/"


def scope_key(name: str, key: str) -> str:
    """Place one key in an environment. `scope_key('ua', 'trails.geojson')` is
    `'environments/ua/trails.geojson'`; the same call for production is
    `'trails.geojson'`, unchanged and unchangeable."""
    return f"{prefix_for(name)}{key}"


def unscope_key(name: str, key: str) -> str:
    """The inverse, for reading a key back out of a log or a listing. A key
    that is not in this environment comes back as it went in, because "not
    ours" and "ours, at the root" are different answers only production can
    confuse - and production's prefix is empty, so it can't."""
    prefix = prefix_for(name)
    if prefix and key.startswith(prefix):
        return key[len(prefix) :]
    return key


def split_key(key: str) -> tuple[str, str]:
    """`(environment, key-within-it)` for any key in the bucket.

    The reader's half of `scope_key`: `environments/ua/conditions/reports.json`
    is UA's `conditions/reports.json`, and anything else is production's own
    key, because production is the root. An `environments/` key naming an
    environment that does not exist raises rather than being read as
    production's - that key is a mistake and reading it as the live one is the
    mistake's worst possible consequence.
    """
    if not key.startswith(f"{ENVIRONMENTS_PREFIX}/"):
        return PRODUCTION, key
    rest = key[len(ENVIRONMENTS_PREFIX) + 1 :]
    name, slash, within = rest.partition("/")
    if not slash or not within:
        raise UnknownEnvironment(f"'{key}' is under {ENVIRONMENTS_PREFIX}/ but names no object within an environment")
    return validate(name), within


def base_url_for(name: str, base: str) -> str:
    """The public base URL an environment's client is built against, and the
    one every checker points at.

    This is the whole client-side mechanism. `client/src/lib/config.ts` builds
    every URL it fetches as `${DATA_BASE_URL}/${key}`, so an environment is a
    longer base and nothing in the app has to learn what an environment is -
    `ua.yml` already resolves `UA_DATA_BASE_URL` for exactly this, and this is
    what computes the value it should hold.
    """
    trimmed = base.rstrip("/")
    prefix = prefix_for(name)
    return f"{trimmed}/{prefix.rstrip('/')}" if prefix else trimmed


def resolve_base(base: str | None, name: str | None = None, *, variable: str = "DATA_BASE_URL") -> str:
    """The base URL a checker should point at: `base` or `$DATA_BASE_URL`,
    moved into `name`'s environment when one is named.

    **A reader may leave the environment unset where a writer may not**, and
    the asymmetry is the point rather than an inconsistency. `resolve` refuses
    an unset environment because the wrong guess overwrites what hikers have
    downloaded; a check pointed at the wrong environment reports on the wrong
    environment, which is a wasted run and nothing worse. So an unnamed check
    reads the base exactly as given - which is also what keeps every existing
    caller, and `--base https://.../environments/ua` typed out by hand, working
    unchanged.
    """
    resolved = (base or os.environ.get(variable, "")).strip().rstrip("/")
    if not resolved or name is None:
        return resolved
    return base_url_for(validate(name), resolved)
