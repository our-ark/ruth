"""Run the same offline Python and JavaScript checks locally and in CI."""
from pathlib import Path
import os
import site
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    environment = dict(os.environ)
    environment.update({
        "OUR_ARK_RUNTIME_DEPENDENCY_PATHS": os.pathsep.join(site.getsitepackages()),
        "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in
                                    ("src", "libraries/agent-sdk/src", "libraries/app-sdk/src")),
        "RUTH_RELEASE_WHEELS": str(ROOT / ".ruth/test-wheels"),
        "RUTH_PYTHON": sys.executable,
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    })
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        [sys.executable, "-m", "unittest", "discover", "-s", "release_tests", "-t", "."],
        ["node", "tests/test_uaap_activity_ui.cjs"],
        ["node", "tests/test_shopping_order_ui.cjs"],
    ]
    for command in commands:
        print("Running: " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, env=environment, check=True)


if __name__ == "__main__":
    main()
