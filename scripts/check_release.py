"""Fail before publication when the tag and both source version declarations disagree."""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path


def check(tag: str, root: Path) -> None:
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    declarations = ast.parse((root / "src/research_factory/__init__.py").read_text(encoding="utf-8"))
    reported = next(
        ast.literal_eval(node.value)
        for node in declarations.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
    )
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) or tag != f"v{version}" or version != reported:
        raise SystemExit(
            "tag, pyproject version and __init__ version must agree; update both, run uv lock, and commit before tagging"
        )


if __name__ == "__main__":
    check(sys.argv[1], Path(__file__).resolve().parents[1])
