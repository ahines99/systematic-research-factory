"""RSF-064, RSF-075: secrets stay out of the repository; images and dependencies are pinned."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = {
    "anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "aws access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "rsf api key": re.compile(r"rsf_[0-9a-f]{12}_[A-Za-z0-9_-]{30,}"),
    "github token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
}


def _tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False)
    if out.returncode != 0:  # not a git checkout (e.g. an sdist): scan the source tree
        return [
            p for p in ROOT.rglob("*") if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts
        ]
    return [ROOT / line for line in out.stdout.splitlines()]


def test_no_secrets_in_tracked_files() -> None:
    hits = []
    for path in _tracked_files():
        if not path.exists() or path.suffix in (".gz", ".png", ".whl") or path.name == "uv.lock":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += [
            f"{path.relative_to(ROOT)}: {name}" for name, pat in SECRET_PATTERNS.items() if pat.search(text)
        ]
    assert not hits, hits


def test_skills_and_prompts_hold_no_credentials() -> None:
    for path in [*(ROOT / "skills").rglob("*"), ROOT / "src/research_factory/judgment/prompts.py"]:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            assert "api_key=" not in text and "password=" not in text, path


def test_env_files_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore and "!.env.example" in ignore
    assert (ROOT / ".env.example").exists()


def test_container_is_pinned_and_unprivileged() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"python:3\.12-slim-bookworm@sha256:[0-9a-f]{64}", dockerfile)
    assert re.search(r"ghcr.io/astral-sh/uv:\d+\.\d+\.\d+", dockerfile)
    assert "USER rsf" in dockerfile and "--locked" in dockerfile


def test_dependencies_are_locked() -> None:
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    for package in ("mcp", "pydantic", "sqlalchemy", "anthropic", "numpy"):
        assert f'name = "{package}"' in lock
