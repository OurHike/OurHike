"""Confirm the R2 credentials/endpoint/bucket currently configured actually
work, without touching any data.

publish.py surfaces a bad credential too - but only mid-publish, after
uploads have already started. This exists so a credentials problem shows up
as a fast, read-only check instead: head_bucket confirms the endpoint is
reachable, the access key pair is valid, and it has at least read access to
the named bucket, without listing or touching a single object in it.

    R2_ENDPOINT_URL=... R2_BUCKET=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
        .venv/Scripts/python check_r2_connection.py
"""

from __future__ import annotations

import os
import sys

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

REQUIRED_VARS = ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


def check(*, s3_client=None, bucket: str | None = None) -> tuple[bool, str]:
    """The pass/fail verdict plus a human-readable reason. Takes an optional
    injected client/bucket, same dependency-injection shape as
    publish.publish(), so this is testable against moto without a real R2
    endpoint."""
    missing = [name for name in REQUIRED_VARS if name not in os.environ]
    if missing and (s3_client is None or bucket is None):
        return False, f"Missing environment variable(s): {', '.join(missing)}"

    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        )
    if bucket is None:
        bucket = os.environ["R2_BUCKET"]

    try:
        s3_client.head_bucket(Bucket=bucket)
    except NoCredentialsError:
        return False, "No credentials were supplied."
    except EndpointConnectionError as exc:
        return False, f"Could not reach the R2 endpoint: {exc}"
    except ClientError as exc:
        # HEAD responses carry no body, so S3-compatible APIs (R2 included)
        # report the bare HTTP status as the error code here rather than a
        # named error like AccessDenied/NoSuchBucket - check both forms.
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in ("403", "AccessDenied"):
            return False, "Credentials were accepted but do not have access to this bucket - check the token's scope."
        if code in ("404", "NoSuchBucket"):
            return False, f"Bucket '{bucket}' does not exist at this endpoint."
        return False, f"{code or 'Unknown error'}: {exc}"

    return True, f"Connected - '{bucket}' is reachable with the supplied credentials."


def main() -> int:
    ok, message = check()
    print(("OK   " if ok else "FAIL ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
