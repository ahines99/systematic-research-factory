"""Evidence store (RSF-013): immutable originals in a blob store, records in the database."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..domain.clock import Clock
from ..domain.errors import NotFoundError
from ..domain.identity import canonical_json, content_id, sha256_hex
from ..domain.models import EvidenceRef
from ..persistence.blobs import BlobStore
from ..persistence.repositories import EvidenceRepository


class EvidenceStore:
    def __init__(self, repo: EvidenceRepository, blobs: BlobStore, clock: Clock):
        self.repo = repo
        self.blobs = blobs
        self.clock = clock

    @staticmethod
    def evidence_id_for(content_hash: str, source_uri: str, source_type: str, as_of: datetime | None) -> str:
        """Same bytes from the same source as of the same time always get the same ID."""
        return content_id(
            "ev",
            {
                "content_hash": content_hash,
                "source_uri": source_uri,
                "source_type": source_type,
                "as_of": as_of.isoformat() if as_of else None,
            },
        )

    def record_bytes(
        self,
        data: bytes,
        *,
        source_uri: str,
        source_type: str,
        as_of: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        step: str | None = None,
    ) -> EvidenceRef:
        content_hash = self.blobs.put(data)
        assert content_hash == sha256_hex(data)
        evidence_id = self.evidence_id_for(content_hash, source_uri, source_type, as_of)
        existing = self.repo.get(evidence_id)
        if existing is None:
            ref = EvidenceRef(
                evidence_id=evidence_id,
                source_uri=source_uri,
                source_type=source_type,
                content_hash=content_hash,
                retrieved_at=self.clock.now(),
                as_of=as_of,
                metadata={"bytes": len(data), **(metadata or {})},
            )
            self.repo.add(ref)
        else:
            ref = existing
        if run_id is not None:
            self.repo.link(run_id, evidence_id, step or "unspecified")
        return ref

    def record_json(self, value: Any, **kwargs: Any) -> EvidenceRef:
        return self.record_bytes(canonical_json(value), **kwargs)

    def record_derived(
        self,
        original: EvidenceRef,
        data: bytes,
        *,
        kind: str,
        run_id: str | None = None,
        step: str | None = None,
    ) -> EvidenceRef:
        """Derived content (e.g. extracted text) is stored separately from the immutable original."""
        return self.record_bytes(
            data,
            source_uri=f"{original.source_uri}#derived={kind}",
            source_type=f"derived:{kind}",
            as_of=original.as_of,
            metadata={"derived_from": original.evidence_id},
            run_id=run_id,
            step=step,
        )

    def get(self, evidence_id: str) -> EvidenceRef:
        ref = self.repo.get(evidence_id)
        if ref is None:
            raise NotFoundError(f"evidence {evidence_id} not found")
        return ref

    def exists(self, evidence_id: str) -> bool:
        return self.repo.get(evidence_id) is not None

    def load_bytes(self, evidence_id: str) -> bytes:
        return self.blobs.get(self.get(evidence_id).content_hash)

    def load_json(self, evidence_id: str) -> Any:
        return json.loads(self.load_bytes(evidence_id))
