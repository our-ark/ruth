from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ruth.cli import ADMIN_COMMANDS, _repl, admin_help, main
from ruth.config import read_section
from ruth.immune import DoctorCheckResult, DoctorDiagnosis
from ruth.identity import load_identity


class RuthCliTests(unittest.TestCase):
    def test_admin_registry_drives_help_and_detailed_usage(self) -> None:
        overview = admin_help()

        self.assertEqual(
            len({command.name for command in ADMIN_COMMANDS}),
            len(ADMIN_COMMANDS),
        )
        for command in ADMIN_COMMANDS:
            self.assertIn(command.summary_line(), overview)
            self.assertIn(f"Usage: {command.usage}", admin_help(command.name))
        self.assertIn("Use help <command> for detailed usage.", overview)

    def test_help_shows_admin_command_surface(self) -> None:
        output = _run_repl_commands("help", "exit")

        self.assertIn("status      Show identity, model, and lineage.", output)
        self.assertIn("init        Create or claim a local Ruth instance worktree.", output)
        self.assertIn("setup       Configure the selected chat provider and lineage.", output)
        self.assertIn("thinking    Show or set Ruth's Codex thinking level.", output)
        self.assertIn("mission     Show or update Ruth's mission.", output)
        self.assertNotIn("memory      Manage long-term memory", output)
        self.assertIn("ancestors   Inspect ancestor chain and inheritable updates.", output)
        self.assertIn("inherit     Scan or inspect stored direct-parent changes.", output)
        self.assertIn("skills      Show declared skills for Ruth or another local agent.", output)
        self.assertNotIn("teach       Package local changes as a portable lesson.", output)
        self.assertIn("learn       Inspect a published skill for adaptation.", output)
        self.assertNotIn("debug       Inspect prompts, logs, state files, and worktree health.", output)
        self.assertNotIn("mode        Show or set chat/work mode.", output)
        self.assertIn("doctor      Run Ruth's local health checks", output)
        self.assertIn("state       Validate or migrate private runtime state.", output)
        self.assertIn(
            "update      Update from the authoritative repository, run doctor, and restart Ruth if safe.",
            output,
        )
        self.assertIn("Ruth CLI is admin-only.", output)
        self.assertNotIn("lastinput   Shortcut", output)
        self.assertNotIn("checktree   Shortcut", output)
        self.assertNotIn("Natural input is classified", output)

    @patch("ruth.cli.model_summary", return_value="AI model: gpt-5-codex")
    def test_status_combines_identity_model_and_lineage(self, model_summary: MagicMock) -> None:
        output = _run_repl_commands("status", "exit")

        model_summary.assert_called_once_with(ROOT)
        self.assertIn("Ruth status:", output)
        self.assertIn("I am Ruth.", output)
        self.assertIn("Mission:", output)
        self.assertIn("AI model: gpt-5-codex", output)
        self.assertNotIn("action mode", output)

    def test_init_claims_current_worktree_as_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands("init --instance gary", "exit", root=root)
            metadata = root / ".agent" / "instance.yaml"

            self.assertTrue(metadata.exists())
            text = metadata.read_text(encoding="utf-8")
            self.assertIn('name: "gary"', text)
            self.assertIn('package: "ruth"', text)
            self.assertIn(f'path: "{root.resolve()}"', text)
            self.assertIn("Initialized current worktree instance for Ruth.", output)
            self.assertIn(f"Metadata: {metadata.resolve()}", output)

    def test_init_can_create_linked_git_worktree_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ruth"
            instance = Path(directory) / "instances" / "gary-ruth"
            root.mkdir()
            _git(root, "init")
            (root / "README.md").write_text("Ruth\n", encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-m", "seed")

            output = _run_repl_commands(
                f"init --instance gary --worktree {instance}",
                "exit",
                root=root,
            )
            metadata = instance / ".agent" / "instance.yaml"

            self.assertTrue(metadata.exists())
            self.assertTrue((instance / ".git").exists())
            text = metadata.read_text(encoding="utf-8")
            self.assertIn('name: "gary"', text)
            self.assertIn(f'path: "{instance.resolve()}"', text)
            self.assertIn('branch: "agent/ruth-gary"', text)
            self.assertIn("Created worktree instance for Ruth.", output)
            self.assertIn(f"Worktree: {instance.resolve()}", output)

    @patch("ruth.cli.model_summary", return_value="AI model: gpt-5-codex")
    def test_status_uses_lineage_parent_before_identity_ancestor(self, model_summary: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lineage = root / ".agent" / "lineage.yaml"
            lineage.parent.mkdir()
            lineage.write_text(
                "\n".join(["parent:", "  name: Adam", "  repo: our-ark/adam"]),
                encoding="utf-8",
            )

            output = _run_repl_commands("status", "exit", root=root)

        self.assertIn("Ancestor: Adam", output)
        self.assertNotIn("Ancestor: Lucy", output)

    @patch("ruth.cli.mission_command", return_value="Mission: ok")
    def test_mission_command_uses_shared_command(self, mission_command: MagicMock) -> None:
        output = _run_repl_commands("mission", "exit")

        mission_command.assert_called_once()
        self.assertEqual(mission_command.call_args.args[0], "mission")
        self.assertEqual(mission_command.call_args.args[2], ROOT)
        self.assertEqual(mission_command.call_args.kwargs, {"prefix": ""})
        self.assertIn("Mission: ok", output)

    @patch("ruth.cli.lineage_command", return_value="Ancestors: no direct parent configured.")
    def test_ancestors_command_uses_shared_command(self, lineage_command: MagicMock) -> None:
        output = _run_repl_commands("ancestors", "exit")

        lineage_command.assert_called_once_with("ancestors", ROOT, prefix="", command_name="ancestors")
        self.assertIn("Ancestors: no direct parent configured.", output)

    @patch("ruth.cli.skills_command", return_value="Ruth skills:")
    def test_skills_command_uses_shared_command(self, skills_command: MagicMock) -> None:
        output = _run_repl_commands("skills lucy", "exit")

        skills_command.assert_called_once_with("skills lucy", ROOT, prefix="")
        self.assertIn("Ruth skills:", output)

    def test_teach_command_is_not_user_facing(self) -> None:
        output = _run_repl_commands("teach natural agency", "exit")

        self.assertIn("Ruth CLI is admin-only now.", output)
        self.assertNotIn("Ruth created a lesson.", output)

    @patch("ruth.cli.learn_command", return_value="Ruth inspected Lucy's teach skill.")
    def test_learn_command_uses_shared_command(self, learn_command: MagicMock) -> None:
        output = _run_repl_commands("learn teach from lucy", "exit")

        learn_command.assert_called_once_with("learn teach from lucy", ROOT, prefix="")
        self.assertIn("Ruth inspected Lucy's teach skill.", output)

    @patch("ruth.cli._schedule_daemon_restart")
    @patch("ruth.cli._record_direct_action")
    @patch("ruth.cli.update_from_authoritative")
    def test_update_records_and_restarts_from_shared_result(
        self,
        update_from_authoritative: MagicMock,
        record_direct_action: MagicMock,
        schedule_restart: MagicMock,
    ) -> None:
        update_from_authoritative.return_value.message = "Ruth pulled latest main and doctor passed."
        update_from_authoritative.return_value.direct_action_result = "Updating 1111111..2222222"
        update_from_authoritative.return_value.restart_required = True

        output = _run_repl_commands("update", "exit")

        update_from_authoritative.assert_called_once_with(ROOT)
        record_direct_action.assert_called_once_with(
            "update from authoritative repository",
            "Updating 1111111..2222222",
            ROOT,
        )
        schedule_restart.assert_called_once_with(ROOT)
        self.assertIn("Ruth pulled latest main and doctor passed.", output)

    def test_unknown_input_is_admin_only_message(self) -> None:
        output = _run_repl_commands("add test4 to README", "commit this", "exit")

        self.assertEqual(output.count("Ruth CLI is admin-only now."), 2)
        self.assertIn(
            "Use the configured chat provider for conversation, repository edits, and self-evolution.",
            output,
        )
        self.assertNotIn("Input tokens:", output)

    def test_setup_interactively_saves_token_without_printing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands("setup", "123456:secret-token", "exit", root=root)

            self.assertEqual(read_section("telegram", root)["bot_token"], "123456:secret-token")
            self.assertIn("Telegram bot token saved", output)
            self.assertIn("bin/ruth-daemon start", output)
            self.assertEqual(output.count("Next:"), 1)
            self.assertNotIn("123456:secret-token", output)

    def test_setup_token_command_shows_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = StringIO()

            with patch("ruth.cli.Path.cwd", return_value=root), redirect_stdout(output):
                main(["setup", "token", "123456:secret-token"])

            self.assertEqual(read_section("telegram", root)["bot_token"], "123456:secret-token")
            self.assertIn("Telegram bot token saved", output.getvalue())
            self.assertIn("Next:", output.getvalue())
            self.assertIn("bin/ruth-daemon start", output.getvalue())
            self.assertNotIn("123456:secret-token", output.getvalue())

    def test_setup_chat_command_saves_chat_lock_from_direct_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = StringIO()

            with patch("ruth.cli.Path.cwd", return_value=root), redirect_stdout(output):
                main(["setup", "chat", "42"])

            self.assertEqual(read_section("telegram", root)["allowed_chat_id"], "42")
            self.assertIn("Telegram chat lock saved", output.getvalue())
            self.assertIn("bin/ruth-daemon restart", output.getvalue())

    def test_setup_aliases_are_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = _run_repl_commands(
                "setup-token 123456:secret-token",
                "setup-chat 42",
                "exit",
                root=root,
            )

        self.assertEqual(output.count("Ruth CLI is admin-only now."), 2)
        self.assertFalse((root / ".ruth" / "config.yaml").exists())

    def test_setup_ancestor_writes_repo_side_lineage_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands(
                "setup ancestor https://github.com/our-ark/ruth",
                "setup ancestor show",
                "exit",
                root=root,
            )

            lineage = root / ".agent" / "lineage.yaml"
            self.assertIn("Lineage parent saved", output)
            self.assertIn("Parent: Ruth (our-ark/ruth@main)", output)
            self.assertIn("Lineage parent: Ruth (our-ark/ruth@main)", output)
            self.assertIn("repo-side lineage metadata", output)
            self.assertIn("name: Ruth", lineage.read_text(encoding="utf-8"))
            self.assertIn("repo: our-ark/ruth", lineage.read_text(encoding="utf-8"))
            self.assertIn("branch: main", lineage.read_text(encoding="utf-8"))

    def test_setup_ancestor_rejects_non_link_forms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands(
                "setup ancestor our-ark/research-agent",
                "setup ancestor https://github.com/our-ark/ruth dev",
                "setup ancestor https://github.com/our-ark/ruth --name Ruth",
                "exit",
                root=root,
            )

            self.assertFalse((root / ".agent" / "lineage.yaml").exists())
            self.assertEqual(output.count("Use bin/ruth setup ancestor <repo-url>."), 3)

    def test_setup_ancestor_clear_removes_lineage_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands(
                "setup ancestor https://github.com/our-ark/ruth",
                "setup ancestor clear",
                "setup ancestor show",
                "exit",
                root=root,
            )

            self.assertFalse((root / ".agent" / "lineage.yaml").exists())
            self.assertIn("Removed lineage parent", output)
            self.assertIn("No lineage parent configured", output)

    @patch("ruth.cli.model_summary", return_value="AI model: gpt-5-codex")
    def test_thinking_command_uses_cli_command_names(self, model_summary: MagicMock) -> None:
        output = _run_repl_commands("thinking", "exit")

        model_summary.assert_called_once_with(ROOT)
        self.assertIn("Ruth thinking status:", output)
        self.assertIn("thinking xhigh", output)
        self.assertIn("thinking max", output)
        self.assertIn("thinking ultra", output)
        self.assertIn("or thinking default.", output)
        self.assertNotIn("/thinking low", output)

    @patch("ruth.cli.run_immune_system")
    def test_doctor_runs_local_health_checks(self, run_immune_system: MagicMock) -> None:
        run_immune_system.return_value.command = "python3 -m unittest"
        run_immune_system.return_value.passed = True
        run_immune_system.return_value.output = "ok"
        run_immune_system.return_value.checks = [
            DoctorCheckResult(
                name="tests",
                passed=True,
                command="python3 -m unittest",
                output="ok",
                category="code health",
                summary="OK",
            )
        ]
        run_immune_system.return_value.diagnosis = DoctorDiagnosis(
            summary="All configured health checks passed.",
            failing_tests=[],
            likely_files=[],
            suggested_action="No repair needed.",
        )

        output = _run_repl_commands("doctor", "exit")

        run_immune_system.assert_called_once_with(ROOT)
        self.assertIn("Doctor passed.", output)
        self.assertIn("Code health:", output)
        self.assertIn("- tests: passed (OK)", output)
        self.assertIn("Diagnosis: All configured health checks passed.", output)
        self.assertIn("Suggested next action: No repair needed.", output)

    @patch("ruth.cli.run_immune_system")
    def test_doctor_prints_failure_diagnosis(self, run_immune_system: MagicMock) -> None:
        run_immune_system.return_value.command = "python3 -m unittest"
        run_immune_system.return_value.passed = False
        run_immune_system.return_value.output = "FAILED (failures=1)"
        run_immune_system.return_value.checks = [
            DoctorCheckResult(
                name="tests",
                passed=False,
                command="python3 -m unittest",
                output="FAILED (failures=1)",
                category="code health",
                summary="FAILED (failures=1)",
            )
        ]
        run_immune_system.return_value.diagnosis = DoctorDiagnosis(
            summary="1 test(s) failed.",
            failing_tests=["tests.test_ruth_cli.RuthCliTests.test_help"],
            likely_files=["tests/test_ruth_cli.py"],
            suggested_action="Inspect the failing tests, make one focused repair pass, then run doctor again.",
        )

        output = _run_repl_commands("doctor", "exit")

        self.assertIn("Doctor failed.", output)
        self.assertIn("- tests: failed (FAILED (failures=1))", output)
        self.assertIn("Diagnosis: 1 test(s) failed.", output)
        self.assertIn("- tests.test_ruth_cli.RuthCliTests.test_help", output)
        self.assertIn("- tests/test_ruth_cli.py", output)
        self.assertIn("Failed check: tests", output)
        self.assertIn("Check output:", output)

    def test_state_command_validates_and_dry_runs_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands(
                "state validate",
                "state migrate --dry-run",
                "exit",
                root=root,
            )

            self.assertFalse((root / ".ruth").exists())
            self.assertIn("Private state validation passed.", output)
            self.assertIn("Manifest: missing", output)
            self.assertIn("Private state migration dry run.", output)

    def test_state_command_applies_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            output = _run_repl_commands("state migrate", "exit", root=root)

            manifest = root / ".ruth" / "state_manifest.json"
            self.assertTrue(manifest.exists())
            self.assertIn("Private state migration completed.", output)
            self.assertIn("Manifest: current", output)


def _run_repl_commands(*commands: str, root: Path = ROOT) -> str:
    identity = load_identity()
    output = StringIO()
    with patch("builtins.input", side_effect=commands), redirect_stdout(output):
        _repl(identity, root)
    return output.getvalue()


def _git(root: Path, *args: str) -> None:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Ruth Test",
            "-c",
            "user.email=ruth-test@example.com",
            *args,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
