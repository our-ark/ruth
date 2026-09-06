from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ruth.instance import instance_branch
from ruth.tasks.worktree import prepare_task_worktree, remove_task_worktree


class RuthWorktreeLifecycleTests(unittest.TestCase):
    def test_task_branch_uses_main_commit_without_checking_out_main(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "ruth"
            instance = Path(directory) / "ruth-gary"
            source.mkdir()
            _git(source, "init", "-b", "main")
            _git(source, "config", "user.name", "Ruth Test")
            _git(source, "config", "user.email", "ruth@example.com")
            (source / ".gitignore").write_text(".agent/instance.yaml\n.ruth/\n", encoding="utf-8")
            (source / "README.md").write_text("first\n", encoding="utf-8")
            _git(source, "add", ".")
            _git(source, "commit", "-m", "first")
            _git(source, "worktree", "add", "-b", "agent/ruth-gary", str(instance), "main")

            (source / "README.md").write_text("latest main\n", encoding="utf-8")
            _git(source, "add", "README.md")
            _git(source, "commit", "-m", "advance main")
            main_head = _git(source, "rev-parse", "main").stdout.strip()
            resident_head = _git(instance, "rev-parse", "agent/ruth-gary").stdout.strip()
            self.assertNotEqual(main_head, resident_head)

            metadata = instance / ".agent" / "instance.yaml"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(
                "\n".join(
                    [
                        "schema_version: 1",
                        "worktree:",
                        f'  path: "{instance}"',
                        f'  source_repo: "{source}"',
                        '  branch: "agent/ruth-gary"',
                        "  kind: agent-instance",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            task = prepare_task_worktree(
                instance,
                1,
                "Update README",
                start_point="main",
                resident_branch="agent/ruth-gary",
                created_at="2026-07-18T20:14:54+00:00",
            )

            self.assertEqual(instance_branch(instance), "agent/ruth-gary")
            self.assertTrue(task.branch.startswith("ruth/"))
            self.assertEqual(_git(task.path, "rev-parse", "HEAD").stdout.strip(), main_head)
            self.assertEqual(_git(source, "branch", "--show-current").stdout.strip(), "main")
            self.assertEqual(
                _git(instance, "branch", "--show-current").stdout.strip(),
                "agent/ruth-gary",
            )

            cleanup = remove_task_worktree(
                instance,
                task,
                force_delete_branch=True,
            )

            self.assertEqual(
                _git(instance, "branch", "--show-current").stdout.strip(),
                "agent/ruth-gary",
            )
            self.assertEqual(_git(source, "branch", "--show-current").stdout.strip(), "main")
            self.assertNotIn(task.branch, _git(instance, "branch", "--list", task.branch).stdout)
            self.assertIn("Removed task #1 worktree.", cleanup)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )


if __name__ == "__main__":
    unittest.main()
