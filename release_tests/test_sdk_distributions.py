"""Verify installable SDK artifacts rather than checkout-only imports."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class SDKDistributionTests(unittest.TestCase):
    def wheels(self):
        directory = Path(os.environ.get("RUTH_RELEASE_WHEELS", ROOT / ".ruth/test-wheels"))
        wheels = []
        for name in ("our_ark_agent_sdk", "our_ark_app_sdk"):
            matches = list(directory.glob(f"{name}-*.whl"))
            self.assertEqual(len(matches), 1, f"Run scripts/prepare_tests.py for {name}")
            wheels.append(matches[0])
        return wheels

    def test_wheels_include_license_metadata_and_browser_assets(self):
        license_text = (ROOT / "LICENSE").read_text()
        for wheel in self.wheels():
            with self.subTest(wheel=wheel.name), zipfile.ZipFile(wheel) as archive:
                license_paths = [name for name in archive.namelist() if name.endswith("/licenses/LICENSE")]
                self.assertEqual(len(license_paths), 1)
                self.assertEqual(archive.read(license_paths[0]).decode(), license_text)
                metadata_path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
                metadata = archive.read(metadata_path).decode()
                self.assertIn("License-Expression: Apache-2.0", metadata)
                self.assertIn("License-File: LICENSE", metadata)
                self.assertNotIn("Requires-Dist:", metadata, "SDKs remain independent of Ruth and providers")
                if wheel.name.startswith("our_ark_app_sdk"):
                    sources = ROOT / "libraries/app-sdk/src/our_ark_app_sdk/static"
                    for asset in sources.iterdir():
                        if asset.suffix in {".js", ".css"}:
                            self.assertEqual(archive.read(f"our_ark_app_sdk/static/{asset.name}"), asset.read_bytes())

    def test_installed_sdks_exchange_messages_context_and_presence_without_ruth(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = base / "packages"
            environment = {**os.environ, "PIP_NO_INDEX": "1"}
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps",
                            "--target", str(target), *(str(w) for w in self.wheels())],
                           env=environment, cwd=base, check=True, capture_output=True, timeout=120)
            # -I -S excludes source paths, user packages, and the test venv's Ruth
            # installation. Only the two wheel installations are added below.
            completed = subprocess.run([sys.executable, "-I", "-S", "-c", ROUND_TRIP, str(target)],
                                       env=environment, cwd=base, capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


ROUND_TRIP = r'''
import importlib.util
from pathlib import Path
import sys
import threading
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec("ruth") is None
from our_ark_agent_sdk import AppClient
from our_ark_app_sdk import AppServer, MessageStore

class NotesStore(MessageStore):
    def validate_shared_context(self, source, shared):
        if set(shared) - {"language"}:
            raise ValueError("Unexpected disclosure")

store = NotesStore(Path("notes.sqlite"), "notes", activity_enabled=True)
session = store.session("test-user")["session_id"]
server = AppServer(("127.0.0.1", 0), store=store, agent_token="test-token",
                   public_origin="http://127.0.0.1:0")
server.public_origin = f"http://127.0.0.1:{server.server_port}"
thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
thread.start()
try:
    app = AppClient("notes", "Notes", server.public_origin, "test-token")
    store.message("test-user", {"id": "m1", "session_id": session, "text": "Explain this",
                                "context": {"document_id": "doc-1"}})
    batch = app.events()
    assert batch["events"][0]["context"] == {"document_id": "doc-1"}
    output = {"id": "r1", "in_reply_to": "m1", "text": "An explanation",
              "shared_context": {"language": "en"}}
    assert app.output(session, output) == output
    assert app.output(session, output) == output
    assert store.transcript("test-user", session)["outputs"] == [output]
    assert app.events(batch["cursor"])["events"] == []
    assert "context-presence/1" in app.capabilities()["extensions"]
    store.activity("test-user", {"event_id": "p1", "session_id": session, "sequence": 1,
                                 "type": "presence.updated", "state": "active"})
    activity = app.activity()
    assert activity["events"][0]["state"] == "active"
    assert app.activity(activity["cursor"])["events"] == []
    assert "ruth" not in sys.modules
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
'''
