from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PYTHON_CANDIDATES = ("python3.13", "python3.12", "python3.11", "python3", "python")


class RuthLauncherTests(unittest.TestCase):
    def test_launchers_probe_for_supported_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory)
            log = bin_dir / "launch.log"
            _write_fake_pythons(bin_dir)
            env = _launcher_env(bin_dir, log, supported={"python3.11"})

            cases = [
                ("bin/ruth", ["doctor"], "python3.11 -m ruth doctor"),
                ("bin/ruth-daemon", ["status"], "python3.11 -m ruth.operations.daemon status"),
                ("bin/ruth-agent", [], "python3.11 -m ruth.agent"),
            ]

            for script, args, expected in cases:
                with self.subTest(script=script):
                    log.write_text("", encoding="utf-8")

                    result = subprocess.run(
                        [str(ROOT / script), *args],
                        cwd="/",
                        env=env,
                        text=True,
                        capture_output=True,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(expected, log.read_text(encoding="utf-8"))

    def test_ruth_python_overrides_probe_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory)
            log = bin_dir / "launch.log"
            custom_python = bin_dir / "custom-python"
            _write_fake_pythons(bin_dir, extra=(custom_python.name,))
            env = _launcher_env(bin_dir, log, supported={custom_python.name, "python3.11"})
            env["RUTH_PYTHON"] = str(custom_python)

            result = subprocess.run(
                [str(ROOT / "bin/ruth"), "doctor"],
                cwd="/",
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text(encoding="utf-8"), "custom-python -m ruth doctor\n")

    def test_unsupported_ruth_python_fails_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory)
            log = bin_dir / "launch.log"
            _write_fake_pythons(bin_dir)
            env = _launcher_env(bin_dir, log, supported={"python3.11"})
            env["RUTH_PYTHON"] = str(bin_dir / "python3")

            result = subprocess.run(
                [str(ROOT / "bin/ruth"), "doctor"],
                cwd="/",
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("RUTH_PYTHON points to an unsupported interpreter", result.stderr)
            self.assertFalse(log.exists())


def _launcher_env(bin_dir: Path, log: Path, *, supported: set[str]) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("RUTH_PYTHON", None)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["RUTH_TEST_LAUNCH_LOG"] = str(log)
    env["RUTH_TEST_SUPPORTED_PYTHONS"] = " ".join(sorted(supported))
    return env


def _write_fake_pythons(bin_dir: Path, *, extra: tuple[str, ...] = ()) -> None:
    for name in (*PYTHON_CANDIDATES, *extra):
        path = bin_dir / name
        path.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    'name="${0##*/}"',
                    'if [[ "${1:-}" == "-c" ]]; then',
                    '  case " ${RUTH_TEST_SUPPORTED_PYTHONS:-} " in',
                    '    *" $name "*) exit 0 ;;',
                    "    *) exit 1 ;;",
                    "  esac",
                    "fi",
                    'printf "%s %s\\n" "$name" "$*" >> "$RUTH_TEST_LAUNCH_LOG"',
                    "exit 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
