"""Validate built artifacts outside the checkout using the project lockfile."""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import tempfile
import venv
from pathlib import Path


def run(*args: str, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)  # noqa: S603 - repository-owned commands


def main() -> None:
    artifacts = Path(sys.argv[1]).resolve()
    wheel = next(artifacts.glob("*.whl"))
    sdist = next(artifacts.glob("*.tar.gz"))
    with tempfile.TemporaryDirectory(prefix="rsf-distributions-") as temp:
        scratch = Path(temp)
        env = {k: v for k, v in os.environ.items() if not k.startswith("RSF_") and k != "PYTHONPATH"}
        # Install only the built wheel and exactly the dependencies exported from the lockfile.
        target = scratch / "installed"
        venv.EnvBuilder(with_pip=False).create(target)
        python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        requirements = scratch / "requirements.txt"
        run(
            "uv",
            "export",
            "--quiet",
            "--locked",
            "--all-extras",
            "--no-dev",
            "--no-emit-project",
            "--no-hashes",
            "--output-file",
            str(requirements),
            cwd=Path(__file__).resolve().parents[1],
            env=env,
        )
        run(
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--requirements",
            str(requirements),
            str(wheel),
            cwd=scratch,
            env=env,
        )
        run(
            str(python),
            "-c",
            "import research_factory; assert 'installed' in research_factory.__file__, research_factory.__file__",
            cwd=scratch,
            env=env,
        )
        run(str(python), "-m", "research_factory.cli", "demo", cwd=scratch, env=env)
        run(str(python), "-m", "research_factory.cli", "eval", "--provider", "rules", cwd=scratch, env=env)
        with tarfile.open(sdist) as archive:
            archive.extractall(scratch / "source", filter="data")
        source = next((scratch / "source").iterdir())
        source_env = env | {"PYTHONPATH": str(source / "src")}
        run(sys.executable, "-m", "pytest", "-q", cwd=source, env=source_env)


if __name__ == "__main__":
    main()
