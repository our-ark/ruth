from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ruth.automatic_learning import learning_dir
from ruth.config import config_path
from ruth.cron import cron_path
from ruth.evolution.curation import curation_index_path
from ruth.evolution.core import evolve_brainstorm_schedule_path
from ruth.evolution.events import evolve_event_path
from ruth.extensions import ExtensionTaskEvent, extension_storage
from ruth.extensions.events import (
    acknowledge_extension_task_event,
    extension_task_event_receipt_path,
)
from ruth.logs import conversation_log_dir, log_system_event
from ruth.memory.paths import memory_dir
from ruth.paths import (
    artifact_path,
    repo_root,
    private_state_path,
    software_body_path,
    storage_layout,
)
from ruth.storage import STORAGE_API_VERSION, StorageLayout, StorageLayoutError
from ruth.tasks.events import load_task_events, task_event_path
from ruth.tasks.queue import enqueue_task, task_queue_path


class RuthStorageTests(unittest.TestCase):
    def test_default_layout_separates_body_state_and_artifacts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            layout = storage_layout(root)

        self.assertEqual(layout.api_version, STORAGE_API_VERSION)
        self.assertEqual(layout.software_body, root.resolve())
        self.assertEqual(layout.private_state, root.resolve() / ".ruth")
        self.assertEqual(layout.artifacts, root.resolve() / ".ruth" / "artifacts")
        self.assertTrue(layout.contains("software-body", root / "src" / "agent.py"))
        self.assertTrue(layout.contains("private-state", root / ".ruth" / "config.yaml"))
        self.assertTrue(
            layout.contains("artifacts", root / ".ruth" / "artifacts" / "task.json")
        )
        self.assertFalse(
            layout.contains("software-body", root / ".ruth" / "config.yaml")
        )
        self.assertFalse(
            layout.contains(
                "private-state",
                root / ".ruth" / "artifacts" / "task.json",
            )
        )

    def test_classified_paths_reject_escape_and_cross_boundary_access(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                private_state_path("config.yaml", root),
                root.resolve() / ".ruth" / "config.yaml",
            )
            self.assertEqual(
                artifact_path("task_events.jsonl", root),
                root.resolve() / ".ruth" / "artifacts" / "task_events.jsonl",
            )
            self.assertEqual(
                software_body_path("src/ruth", root),
                root.resolve() / "src" / "ruth",
            )
            with self.assertRaises(StorageLayoutError):
                private_state_path("artifacts/task_events.jsonl", root)
            with self.assertRaises(StorageLayoutError):
                private_state_path("../outside", root)
            with self.assertRaises(StorageLayoutError):
                artifact_path("/tmp/outside", root)
            with self.assertRaises(StorageLayoutError):
                software_body_path(".ruth/config.yaml", root)

    def test_artifact_home_can_be_independent(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as artifacts:
            root = Path(directory)
            with patch.dict(os.environ, {"RUTH_ARTIFACT_HOME": artifacts}):
                layout = storage_layout(root)
                path = log_system_event("test", root=root)

        self.assertEqual(layout.artifacts, Path(artifacts).resolve())
        self.assertEqual(path.parent.parent.parent, Path(artifacts).resolve())

    def test_explicit_sibling_roots_are_not_captured_by_ancestor_repo(self) -> None:
        with TemporaryDirectory() as directory:
            ancestor = Path(directory)
            ancestor.joinpath(".git").mkdir()
            ancestor.joinpath("pyproject.toml").write_text(
                "[project]\nname = \"unrelated\"\nversion = \"0\"\n",
                encoding="utf-8",
            )
            first = ancestor / "instances" / "first"
            second = ancestor / "instances" / "second"
            first.mkdir(parents=True)
            second.mkdir(parents=True)

            first_layout = storage_layout(first)
            second_layout = storage_layout(second)
            first_queue = task_queue_path(first)
            second_queue = task_queue_path(second)
            first_events = task_event_path(first)
            second_events = task_event_path(second)
            first_receipts = extension_task_event_receipt_path(
                extension_storage(first_layout, "manager")
            )
            enqueue_task(1, "first task", first)
            enqueue_task(2, "second task", second)
            acknowledge_extension_task_event(
                extension_storage(first_layout, "manager"),
                ExtensionTaskEvent(
                    id="first-extension-event",
                    extension_name="manager",
                    task_id=1,
                    event="queued",
                    occurred_at="2026-07-30T00:00:00+00:00",
                    request="first task",
                ),
            )
            written_paths = tuple(
                path.is_file()
                for path in (
                    first_queue,
                    second_queue,
                    first_events,
                    second_events,
                    first_receipts,
                )
            )
            ancestor_state_exists = ancestor.joinpath(".ruth").exists()

        self.assertEqual(repo_root(first), first.resolve())
        self.assertEqual(first_layout.software_body, first.resolve())
        self.assertEqual(second_layout.software_body, second.resolve())
        self.assertEqual(first_queue, first.resolve() / ".ruth" / "task_queue.json")
        self.assertEqual(second_queue, second.resolve() / ".ruth" / "task_queue.json")
        self.assertEqual(
            first_events,
            first.resolve() / ".ruth" / "artifacts" / "task_events.jsonl",
        )
        self.assertEqual(
            second_events,
            second.resolve() / ".ruth" / "artifacts" / "task_events.jsonl",
        )
        self.assertEqual(
            first_receipts,
            first.resolve()
            / ".ruth"
            / "extensions"
            / "manager"
            / "task_event_receipts.jsonl",
        )
        self.assertNotEqual(first_layout.private_state, second_layout.private_state)
        self.assertTrue(all(written_paths))
        self.assertFalse(ancestor_state_exists)
        self.assertFalse(first_queue.is_relative_to(ancestor / ".ruth"))

    def test_implicit_root_discovery_still_finds_ancestor_repo(self) -> None:
        with TemporaryDirectory() as directory:
            ancestor = Path(directory)
            ancestor.joinpath("pyproject.toml").write_text(
                "[project]\nname = \"ancestor\"\nversion = \"0\"\n",
                encoding="utf-8",
            )
            nested = ancestor / "nested" / "working"
            nested.mkdir(parents=True)
            previous = Path.cwd()
            try:
                os.chdir(nested)
                discovered = repo_root()
                layout = storage_layout()
            finally:
                os.chdir(previous)

        self.assertEqual(discovered, ancestor.resolve())
        self.assertEqual(layout.software_body, ancestor.resolve())
        self.assertEqual(layout.private_state, ancestor.resolve() / ".ruth")

    def test_state_redirect_matches_only_the_explicit_software_body(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as redirected:
            ancestor = Path(directory)
            ancestor.joinpath(".git").mkdir()
            configured = ancestor / "configured"
            sibling = ancestor / "sibling"
            configured.mkdir()
            sibling.mkdir()
            with patch.dict(
                os.environ,
                {
                    "RUTH_STATE_REDIRECT_ROOT": str(configured),
                    "RUTH_STATE_HOME": redirected,
                },
            ):
                configured_layout = storage_layout(configured)
                sibling_layout = storage_layout(sibling)

        self.assertEqual(
            configured_layout.private_state,
            Path(redirected).resolve(),
        )
        self.assertEqual(
            sibling_layout.private_state,
            sibling.resolve() / ".ruth",
        )

    def test_core_paths_are_owned_by_their_declared_area(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            layout = storage_layout(root)
            private_paths = (
                config_path(root),
                cron_path(root),
                memory_dir(root),
                task_queue_path(root),
                evolve_brainstorm_schedule_path(root),
            )
            artifact_paths = (
                conversation_log_dir(root),
                curation_index_path(root),
                evolve_event_path(root),
                learning_dir(root),
                task_event_path(root),
            )

        self.assertTrue(
            all(layout.contains("private-state", path) for path in private_paths)
        )
        self.assertTrue(
            all(layout.contains("artifacts", path) for path in artifact_paths)
        )

    def test_invalid_layout_overlap_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with self.assertRaises(StorageLayoutError):
                StorageLayout(root, root, root / "artifacts")
            with self.assertRaises(StorageLayoutError):
                StorageLayout(root / "body", root, root / "artifacts")

    def test_legacy_artifact_events_remain_readable(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".ruth" / "task_events.jsonl"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps(
                    {
                        "schema_version": 5,
                        "id": "event-legacy",
                        "task_id": 7,
                        "occurred_at": "2026-07-25T00:00:00+00:00",
                        "event": "completed",
                        "source": "task",
                        "initiated_by": "human",
                        "event_actor": "agent",
                        "trigger": "/task",
                        "request": "legacy task",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            events = load_task_events(root)

        self.assertEqual([event.id for event in events], ["event-legacy"])
        self.assertEqual(
            task_event_path(root),
            root.resolve() / ".ruth" / "artifacts" / "task_events.jsonl",
        )
