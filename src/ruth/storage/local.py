from __future__ import annotations

import os
from pathlib import Path

from ruth.storage.contracts import StorageLayout


def local_storage_layout(root: Path) -> StorageLayout:
    body = root.expanduser().resolve()
    private_state = _private_state_root(body)
    artifact_override = os.environ.get("RUTH_ARTIFACT_HOME", "").strip()
    artifacts = (
        Path(artifact_override).expanduser().resolve()
        if artifact_override
        else private_state / "artifacts"
    )
    return StorageLayout(
        software_body=body,
        private_state=private_state,
        artifacts=artifacts,
    )


def _private_state_root(body: Path) -> Path:
    redirected_root = os.environ.get("RUTH_STATE_REDIRECT_ROOT", "").strip()
    redirected_home = os.environ.get("RUTH_STATE_HOME", "").strip()
    if redirected_root and redirected_home:
        try:
            matches = body == Path(redirected_root).expanduser().resolve()
        except OSError:
            matches = False
        if matches:
            return Path(redirected_home).expanduser().resolve()
    return body / ".ruth"
