"""Provision a virtual environment from this checkout and immutable upstream pins.

Run with the virtual environment's Python. No model or chat credentials are used.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Create a virtual environment first; see CONTRIBUTING.md.")
    pip = [sys.executable, "-m", "pip", "--disable-pip-version-check"]
    subprocess.run(pip + ["install", "--require-hashes", "-r",
                         str(ROOT / ".github/requirements/test-build.txt")], check=True)
    manifest = tomllib.loads((ROOT / "genesis.toml").read_text())
    requirements = []
    for dependency in manifest["runtime_dependencies"]:
        source = ROOT / dependency.get("local_source", "__no_local_source__")
        requirements.append(str(source.parent) if source.is_dir() else dependency["requirement"])
    requirements.extend([str(ROOT / "libraries/app-sdk"), str(ROOT)])
    destination = ROOT / ".ruth/test-wheels"
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Replace the wheel set only after a successful build; stale versions must not
    # silently enter subsequent offline install tests.
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        subprocess.run(pip + ["wheel", "--no-deps", "--no-build-isolation",
                              "--wheel-dir", temporary, *requirements], check=True)
        destination.mkdir(exist_ok=True)
        for previous in destination.glob("*.whl"):
            previous.unlink()
        for wheel in Path(temporary).glob("*.whl"):
            wheel.replace(destination / wheel.name)
    subprocess.run(pip + ["install", "--no-index", "--no-deps", "--force-reinstall",
                          *(str(w) for w in sorted(destination.glob("*.whl")))], check=True)
    subprocess.run(pip + ["check"], check=True)
    print(f"Ready. Run: {sys.executable} scripts/test.py", flush=True)


if __name__ == "__main__":
    main()
