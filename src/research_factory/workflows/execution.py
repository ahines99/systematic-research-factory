"""Recorded inputs and runtime identity for deterministic execution."""

from __future__ import annotations

import platform
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from .. import __version__
from ..config import Settings
from ..domain.identity import sha256_hex
from ..judgment.prompts import skills_root


@lru_cache(maxsize=1)
def runtime_identity() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    sources = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*.py")
        if "_skills" not in p.relative_to(root).parts
    }
    assets = skills_root()
    if assets is not None:
        sources.update(
            {
                "_skills/" + p.relative_to(assets).as_posix(): p.read_bytes()
                for p in assets.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            }
        )
    source = b"".join(
        name.encode() + b"\0" + data.replace(b"\r\n", b"\n") for name, data in sorted(sources.items())
    )
    return {
        "package_version": __version__,
        "source_sha256": sha256_hex(source),
        "python": ".".join(platform.python_version_tuple()[:2]),
        "numpy": np.__version__,
        "platform": f"{platform.system()}-{platform.machine()}",
        "dependencies": {
            name: version(name)
            for name in (
                "numpy",
                "pydantic",
                "pydantic-settings",
                "sqlalchemy",
                "alembic",
                "anyio",
                "tzdata",
                "PyYAML",
            )
        },
    }


def execution_manifest(settings: Settings, snapshots: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "format": "rsf-execution/1",
        "runtime": runtime_identity(),
        "thresholds": settings.thresholds.model_dump(mode="json"),
        "snapshots": dict(snapshots or {}),
    }
