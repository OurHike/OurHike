"""Where a report photo goes: a private R2 bucket, over boto3's S3 API.

#234 made the decisions this file implements, and three of them are the whole
reason it looks the way it does.

**The bucket is private.** `bad_hikers` is `internal_only` and those photos
are photos OF PEOPLE; `thanks` is `club_only`; and every type is unmoderated
at the moment a photo is attached, which #229 established is not publicly
visible. A world-readable bucket would publish the image while the report it
belongs to stayed private, undoing the routing `visibility` exists to
provide. Nothing here grants public read and nothing here builds a URL - the
Worker that checks the owning report before streaming an object is part 2,
and until it exists a photo can be written and not read. That is the honest
half-built state rather than an oversight.

**The key is DERIVED from the report id**, never random and stored. Two
stores with no transaction between them drift, and a derived key is what
makes that drift a cron job rather than a design problem: "which photos
belong to this report" is answerable from the id alone, and "does this object
have a report" by parsing the key. A retry overwrites the same key instead of
duplicating - which matters more here than usual, because the normal path is
an outbox flushing on a ridge with one bar.

The direction of truth, from #234 and stated once so it is not re-litigated
per bug: **the report row is authoritative, the R2 object is derived and
disposable.** A missing object degrades to "no photo"; an orphaned object
gets swept. Never the reverse.

**The write gate is `pipeline/publish.py`'s, not a new one.** Same env var
names, same `R2_WRITE_ENABLED` opt-in, same reason: an environment that
should not be writing to the bucket cannot, and it says so loudly rather than
uploading somewhere unintended. Reusing the names also means one set of
credentials to rotate instead of two that drift apart.
"""

import os
import re

import boto3

WRITE_ENABLED_ENV_VAR = "R2_WRITE_ENABLED"

REQUIRED_ENV_VARS = (
    "R2_ENDPOINT_URL",
    "R2_BUCKET",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
)

# One photo per report in v1, and the `1` is what leaves room for more
# without changing the scheme. `photo_url` is a single column, so a second
# upload overwrites the first - which is the same property that makes an
# outbox retry safe, arrived at from the other direction.
FIRST_PHOTO_INDEX = 1

CONTENT_TYPE = "image/jpeg"


# JPEG's SOI marker plus the first byte of the next one. The key ends `.jpg`
# and part 2's Worker will serve it as image/jpeg from that name, so anything
# else stored under it would be an object mislabelled at the moment it is
# read - by a component that has no way to notice. Checked here rather than
# trusting a Content-Type header the client also sends.
JPEG_MAGIC = b"\xff\xd8\xff"

# A ceiling, not a target. #234 puts downscaling and EXIF stripping in the
# client, before upload (part 3) - but a server whose only size limit is the
# client's good behaviour has no size limit, and this endpoint is reachable
# by anyone with an account. Generous enough to accept an undownscaled phone
# photo, because part 3 has not shipped and an early client may well send
# one; small enough that it cannot be used to fill a bucket.
MAX_PHOTO_BYTES = 8 * 1024 * 1024

# Report ids are UUIDs everywhere - `uuid4()` on the server, `crypto.randomUUID()`
# on the client, and `ReportCreate.id` is typed `uuid.UUID` so a client cannot
# supply anything else (#265). This is belt and braces on the one value that
# becomes a storage path: an id is checked again here because a key is a path,
# and a path assembled from unvalidated input is how traversal happens.
_UUID_PATTERN = re.compile(r"\A[0-9a-fA-F-]{36}\Z")


class PhotoStorageUnavailable(RuntimeError):
    """This deployment cannot write photos, and says which half is missing.

    Separate from a failed upload: nothing was attempted. The router turns it
    into a 503 so a client retries later rather than discarding the photo as
    rejected - the outbox has no way to tell those apart otherwise.
    """


def writes_enabled() -> bool:
    """Whether this environment is explicitly allowed to write to R2.

    Same env var and same accepted spellings as `pipeline/publish.py`'s gate,
    because it is the same gate protecting the same bucket.
    """
    return os.environ.get(WRITE_ENABLED_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def missing_settings() -> list[str]:
    """Which R2 environment variables this deployment has not been given.

    A list rather than a bool so the 503 can name them. A deployment with
    photos misconfigured is a deployment somebody has to fix, and "R2 is not
    configured" without saying which half is a support ticket.
    """
    return [name for name in REQUIRED_ENV_VARS if not os.environ.get(name, "").strip()]


def photo_key(report_id: str, index: int = FIRST_PHOTO_INDEX) -> str:
    """`reports/{report_id}/{n}.jpg` - derived, never stored and looked up.

    See the module docstring for why this is derived. The id is re-validated
    here because this is the point where it stops being an identifier and
    becomes a path.
    """
    if _UUID_PATTERN.match(report_id) is None:
        raise ValueError(f"A report id that is not a UUID cannot become a key: {report_id!r}")

    return f"reports/{report_id}/{index}.jpg"


def photo_rejection(data: bytes) -> str | None:
    """Why these bytes may not be stored, or None if they may.

    Returns a sentence written for a hiker rather than a code, matching what
    lib/api.ts's `permanentFailureReason` already surfaces on the More screen
    for a refused report: the client shows it, so it has to read as an
    explanation rather than a status.
    """
    if not data:
        return "That photo arrived empty."
    if len(data) > MAX_PHOTO_BYTES:
        megabytes = MAX_PHOTO_BYTES // (1024 * 1024)
        return f"That photo is larger than {megabytes} MB."
    if not data.startswith(JPEG_MAGIC):
        return "That file is not a JPEG photo."
    return None


def build_client():
    """A boto3 S3 client pointed at R2, from the environment only.

    Credentials are never arguments and never settings on `app.config`: the
    same posture `pipeline/publish.py` takes, and the reason app/config.py
    gives for the Supabase keys - a real credential does not belong in a file
    that can be read, defaulted, or accidentally committed.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )


def store_photo(report_id: str, data: bytes, *, s3_client=None, bucket: str | None = None) -> str:
    """Write the photo and return the key it was written under.

    Raises `PhotoStorageUnavailable` before touching the network when the
    write gate is closed or a credential is missing - nothing is attempted, so
    nothing partial is left behind.

    `s3_client` and `bucket` are injectable for the same reason
    `pipeline/publish.py` makes them injectable: the suite drives a real boto3
    client against moto rather than mocking the call and asserting it happened,
    so a key that would not survive a real PutObject fails here.
    """
    if not writes_enabled():
        raise PhotoStorageUnavailable(f"Photo uploads are disabled. Set {WRITE_ENABLED_ENV_VAR}=true to enable them.")

    missing = missing_settings()
    if missing and (s3_client is None or bucket is None):
        raise PhotoStorageUnavailable("Photo storage is not configured. Missing: " + ", ".join(missing))

    key = photo_key(report_id)
    client = s3_client if s3_client is not None else build_client()
    target = bucket if bucket is not None else os.environ["R2_BUCKET"]

    # No ACL argument, deliberately. R2 buckets are private by default and
    # this endpoint must never be the thing that changes that - a
    # `public-read` here would publish a `bad_hikers` photo of a person while
    # the report stayed internal_only, which is the exact failure #234
    # rejected a public bucket to avoid.
    client.put_object(Bucket=target, Key=key, Body=data, ContentType=CONTENT_TYPE)

    return key
