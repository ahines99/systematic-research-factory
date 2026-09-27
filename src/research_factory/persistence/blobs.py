"""Content-addressed, write-once blob stores. A blob's ID is the SHA-256 of its bytes."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Protocol

from ..domain.errors import ConflictError, NotFoundError
from ..domain.identity import sha256_hex


class BlobStore(Protocol):
    def put(self, data: bytes) -> str: ...
    def get(self, blob_id: str) -> bytes: ...
    def exists(self, blob_id: str) -> bool: ...


def _check_id(blob_id: str) -> None:
    if len(blob_id) != 64 or any(c not in "0123456789abcdef" for c in blob_id):
        raise NotFoundError(f"invalid blob id {blob_id!r}")


class MemoryBlobStore:
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        blob_id = sha256_hex(data)
        self._blobs.setdefault(blob_id, bytes(data))
        return blob_id

    def get(self, blob_id: str) -> bytes:
        _check_id(blob_id)
        try:
            return self._blobs[blob_id]
        except KeyError as exc:
            raise NotFoundError(f"blob {blob_id} not found") from exc

    def exists(self, blob_id: str) -> bool:
        return blob_id in self._blobs


class FileBlobStore:
    """Blobs under ``root/ab/cd/<sha256>``; files are made read-only after writing."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, blob_id: str) -> Path:
        _check_id(blob_id)
        return self.root / blob_id[:2] / blob_id[2:4] / blob_id

    def put(self, data: bytes) -> str:
        blob_id = sha256_hex(data)
        path = self._path(blob_id)
        if path.exists():
            self.get(blob_id)
            return blob_id  # content-addressed: same bytes, nothing to do
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f"{blob_id}.", suffix=".tmp", dir=path.parent)
        tmp = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            # Publish complete bytes atomically, without replacing a concurrent winner.
            try:
                os.link(tmp, path)
            except FileExistsError:
                self.get(blob_id)
        finally:
            tmp.unlink(missing_ok=True)
        path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        return blob_id

    def get(self, blob_id: str) -> bytes:
        path = self._path(blob_id)
        if not path.exists():
            raise NotFoundError(f"blob {blob_id} not found")
        data = path.read_bytes()
        if sha256_hex(data) != blob_id:
            raise ConflictError(f"blob {blob_id} failed its integrity check")
        return data

    def exists(self, blob_id: str) -> bool:
        return self._path(blob_id).exists()


class S3BlobStore:
    """S3-compatible store (Cloudflare R2 in production, ADR-0006).

    Writes are conditional (``If-None-Match: *``) so an existing object is never
    overwritten. The credentials given to the app should not include delete permission.
    """

    def __init__(self, bucket: str, client: Any, prefix: str = "blobs/"):
        self.bucket = bucket
        self.client = client
        self.prefix = prefix

    @classmethod
    def from_settings(
        cls, bucket: str, endpoint_url: str | None, key_id: str | None, secret: str | None
    ) -> S3BlobStore:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name="auto",
        )
        return cls(bucket, client)

    def _key(self, blob_id: str) -> str:
        _check_id(blob_id)
        return f"{self.prefix}{blob_id[:2]}/{blob_id}"

    def put(self, data: bytes) -> str:
        blob_id = sha256_hex(data)
        if self.exists(blob_id):
            return blob_id
        try:
            self.client.put_object(Bucket=self.bucket, Key=self._key(blob_id), Body=data, IfNoneMatch="*")
        except Exception as exc:  # botocore raises ClientError with code PreconditionFailed
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code not in ("PreconditionFailed", "412"):
                raise
        return blob_id

    def get(self, blob_id: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=self._key(blob_id))
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise NotFoundError(f"blob {blob_id} not found") from exc
            raise
        data: bytes = obj["Body"].read()
        if sha256_hex(data) != blob_id:
            raise ConflictError(f"blob {blob_id} failed its integrity check")
        return data

    def exists(self, blob_id: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(blob_id))
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404", "NotFound"):
                return False
            raise
        return True


def blob_store_from_url(url: str, **s3_kwargs: Any) -> BlobStore:
    if url.startswith("memory://"):
        return MemoryBlobStore()
    if url.startswith("file://"):
        return FileBlobStore(url.removeprefix("file://"))
    if url.startswith("s3://"):
        return S3BlobStore.from_settings(url.removeprefix("s3://").strip("/"), **s3_kwargs)
    raise ValueError(f"unsupported blob store URL {url!r}")
