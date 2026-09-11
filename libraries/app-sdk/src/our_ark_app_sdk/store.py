"""UI-independent, domain-independent UAAP message and context storage."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value):
        raise APIError(400, "Invalid identifier")
    return value


def bounded_text(value, maximum=8000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise APIError(400, "Missing or oversized text")
    return value.strip()


class MessageStore:
    """Reference persistence; applications supply domain and disclosure policies.

    Browser/account authentication belongs to the application's HTTP adapter.
    Use its authenticated account identity as owner for session/message reads.
    """

    def __init__(self, path: Path, app_id: str):
        self.path, self.app_id = Path(path), identifier(app_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, owner TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                    cursor INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    session TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outputs(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    session TEXT NOT NULL, body TEXT NOT NULL);
            """)
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def snapshot_context(self, context):
        """Override to validate/enrich domain facts before they enter the feed."""
        if not isinstance(context, dict):
            raise APIError(400, "A context snapshot is required")
        return json.loads(json.dumps(context, allow_nan=False))

    def message_metadata(self, body):
        """Override to record app-validated, per-message disclosure permissions."""
        return {}

    def validate_shared_context(self, source, shared):
        """An app must provide a disclosure policy before accepting user context."""
        if shared:
            raise APIError(403, "Shared context requires an application disclosure policy")

    def session(self, owner):
        session_id = uuid4().hex
        with self.transaction() as db:
            db.execute("INSERT INTO sessions VALUES (?, ?)", (session_id, owner))
        return {"session_id": session_id, "app_id": self.app_id}

    def require_session(self, db, session_id, owner=None):
        row = db.execute("SELECT owner FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row or (owner is not None and row["owner"] != owner):
            raise APIError(404, "Session not found")

    def message(self, owner, body):
        session_id, message_id = identifier(body.get("session_id")), identifier(body.get("id"))
        text = bounded_text(body.get("text"))
        event = {"event_id": message_id, "session_id": session_id,
                 "message": {"id": message_id, "text": text},
                 "context": self.snapshot_context(body.get("context")),
                 **self.message_metadata(body)}
        with self.transaction() as db:
            self.require_session(db, session_id, owner)
            old = db.execute("SELECT body FROM events WHERE id=?", (message_id,)).fetchone()
            if old:
                saved = json.loads(old["body"])
                if any(saved.get(k) != event[k] for k in event):
                    raise APIError(409, "Message id reused with different content")
                return saved
            event["created_at"] = time.time()
            db.execute("INSERT INTO events(id, session, body) VALUES (?, ?, ?)",
                       (message_id, session_id, json.dumps(event)))
        return event

    def events(self, after):
        if type(after) is not int or after < 0:
            raise APIError(400, "Invalid cursor")
        with self.transaction() as db:
            rows = db.execute("SELECT cursor, body FROM events WHERE cursor>? ORDER BY cursor LIMIT 20", (after,)).fetchall()
        events = [dict(json.loads(r["body"]), cursor=r["cursor"]) for r in rows]
        return {"events": events, "cursor": rows[-1]["cursor"] if rows else after}

    def output(self, session_id, body):
        identifier(body.get("id"))
        identifier(body.get("in_reply_to"))
        bounded_text(body.get("text"), 24000)
        shared = body.get("shared_context", {})
        if not isinstance(shared, dict):
            raise APIError(400, "Unsupported shared context")
        if len(json.dumps(body)) > 32000:
            raise APIError(400, "Output too large")
        with self.transaction() as db:
            self.require_session(db, session_id)
            source = db.execute("SELECT body FROM events WHERE id=? AND session=?",
                                (body["in_reply_to"], session_id)).fetchone()
            if not source:
                raise APIError(400, "Reply does not belong to this session")
            self.validate_shared_context(json.loads(source["body"]), shared)
            old = db.execute("SELECT session, body FROM outputs WHERE id=?", (body["id"],)).fetchone()
            encoded = json.dumps(body, sort_keys=True)
            if old:
                if old["session"] != session_id or old["body"] != encoded:
                    raise APIError(409, "Output id reused with different content")
            else:
                db.execute("INSERT INTO outputs(id, session, body) VALUES (?, ?, ?)",
                           (body["id"], session_id, encoded))
        return body

    def transcript(self, owner, session_id):
        with self.transaction() as db:
            self.require_session(db, session_id, owner)
            messages = [json.loads(r[0]) for r in db.execute("SELECT body FROM events WHERE session=? ORDER BY cursor", (session_id,))]
            outputs = [json.loads(r[0]) for r in db.execute("SELECT body FROM outputs WHERE session=? ORDER BY seq", (session_id,))]
        return {"messages": messages, "outputs": outputs}
