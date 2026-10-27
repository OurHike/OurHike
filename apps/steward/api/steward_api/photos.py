"""Where claim photos are kept: a private R2 bucket, read through short-lived signed URLs.

backend/app/core/photos.py's design, for its reasons: the object key is derived
from ids and never stored (the row is authoritative, the object disposable), the
bucket is private, writes sit behind an explicit flag, and a storage failure
reaches the caller as a short sentence while the bucket's address stays in the log.

Its own bucket and its own STEWARD_R2_* names, never OurHike's R2_* or
R2_PHOTO_*: a deployment that carries OurHike's environment must not be able to
write steward photos into OurHike's buckets.
"""

from __future__ import annotations

import logging
import uuid
from typing import Protocol

logger = logging.getLogger(__name__)

#: How long a signed read URL lasts: long enough to look through a submission.
READ_URL_SECONDS = 600

UNAVAILABLE = "Photo storage is not available right now. Try again shortly."
NOT_SET_UP = "Photo storage is not set up on this deployment."


class PhotoStorageUnavailable(RuntimeError):
    pass


def photo_key(claim_id: uuid.UUID, photo_id: uuid.UUID) -> str:
    """The only spelling of a photo's object key."""
    return f"claims/{claim_id}/{photo_id}"


class PhotoStore(Protocol):
    def put(self, key: str, body: bytes, content_type: str) -> None: ...
    def url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...


class MemoryPhotoStore:
    """For tests and local runs: the objects in a dict, and fake URLs."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = (body, content_type)

    def url(self, key: str) -> str:
        return f"memory://{key}"

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class R2PhotoStore:
    def __init__(self, endpoint_url: str, bucket: str, access_key_id: str, secret_access_key: str) -> None:
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key

    def _client(self):
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
        )

    def put(self, key: str, body: bytes, content_type: str) -> None:
        try:
            self._client().put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        except Exception as exc:  # noqa: BLE001 - botocore raises many kinds; all mean the same here
            logger.warning("R2 put failed for %s: %s", key, exc)
            raise PhotoStorageUnavailable(UNAVAILABLE) from exc

    def url(self, key: str) -> str:
        try:
            return self._client().generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=READ_URL_SECONDS
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("R2 signing failed for %s: %s", key, exc)
            raise PhotoStorageUnavailable(UNAVAILABLE) from exc

    def delete(self, key: str) -> None:
        try:
            self._client().delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            # The row goes regardless; an orphaned object is swept, never served.
            logger.warning("R2 delete failed for %s: %s", key, exc)


# --- What an upload must be --------------------------------------------------------

#: The image types accepted, by the bytes they start with. The declared
#: Content-Type is not trusted; the magic number decides.
_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def sniff(body: bytes) -> str | None:
    for signature, content_type in _SIGNATURES:
        if body.startswith(signature):
            return content_type
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def carries_location_metadata(body: bytes, content_type: str) -> bool:
    """Whether a JPEG still carries an EXIF block, which is where a phone puts
    the GPS position and the camera's details. The web app re-encodes every
    photo through a canvas, which drops it; a photo that still has it came
    from somewhere else and is refused rather than published with a location
    fix the volunteer did not mean to share. PNG and WebP from a canvas carry none.
    """
    if content_type != "image/jpeg":
        return False
    # APP1 segments holding EXIF sit in the header, before the image data.
    return b"Exif\x00\x00" in body[:65536]
