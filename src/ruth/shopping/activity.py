"""Independent, model-free consumption of the optional UAAP activity feed."""
from __future__ import annotations

import json
import time

from ruth.paths import private_state_path
from ruth.state import atomic_write, file_transaction, load_json_object
from .client import ShoppingError


class AppActivity:
    def __init__(self, root, apps, effect=lambda fn, *a, **kw: fn(*a, **kw)):
        self.path = private_state_path("shopping/activity.json", root)
        self.apps, self.effect = apps, effect
        self.capabilities = {}

    def load(self):
        return load_json_object(self.path, default_factory=lambda: {"version": 1, "apps": {}})

    def save(self, state):
        self.effect(atomic_write, self.path, json.dumps(state, indent=2) + "\n")

    def poll_once(self):
        errors = []
        # Never acquire the shopping conversation lock or call its model/outbox.
        with file_transaction(self.path):
            state = self.load()
            for app_id, app in self.apps.items():
                try:
                    cached_at, supported = self.capabilities.get(app_id, (0, False))
                    if time.monotonic() - cached_at > 60 or app_id not in self.capabilities:
                        supported = "context-presence/1" in self.effect(app.capabilities)["extensions"]
                        self.capabilities[app_id] = (time.monotonic(), supported)
                    if not supported:
                        continue
                    saved = state["apps"].setdefault(app_id, {"cursor": 0, "sessions": {}})
                    started = time.monotonic()
                    batch = self.effect(app.activity, saved["cursor"])
                    elapsed, now = time.monotonic() - started, time.time()
                    for event in batch["events"]:
                        session = saved["sessions"].setdefault(event["session_id"], {})
                        kind = event["type"].split(".")[0]
                        if event["sequence"] <= session.get(kind + "_sequence", 0):
                            continue
                        session[kind + "_sequence"] = event["sequence"]
                        if kind == "context":
                            session["context"] = event["context"]
                        else:
                            # Server-relative lease age handles clock skew and delayed reads.
                            remaining = max(0, min(120, event["expires_at"] - batch["server_time"]) - elapsed)
                            session.update(state=event["state"], expires_at=now + remaining,
                                           observed_at=now - max(0, batch["server_time"] - event["received_at"]))
                    if batch["cursor"] != saved["cursor"]:
                        saved["cursor"] = batch["cursor"]
                        self.save(state)
                except ShoppingError as error:
                    errors.append(str(error))
        return errors

    def snapshot(self):
        now, sessions = time.time(), []
        for app_id, app in self.load()["apps"].items():
            if app_id not in self.apps:
                continue
            for session_id, session in app["sessions"].items():
                presence = session.get("state", "unknown") if session.get("expires_at", 0) > now else "unknown"
                sessions.append({"app_id": app_id, "app_name": self.apps[app_id].name,
                                 "session_id": session_id, "presence": presence,
                                 "observed_at": session.get("observed_at"),
                                 "context": session.get("context", {})})
        active = [s for s in sessions if s["presence"] == "active"]
        return {"status": "active" if len(active) == 1 else "ambiguous" if active else "unknown",
                "active_sessions": active,
                "current_session": active[0] if len(active) == 1 else None}

    def summary(self):
        activity = self.snapshot()
        if not activity["active_sessions"]:
            return "Current app: unknown (no fresh focused session)."
        descriptions = [s["app_name"] + (" · " + s["context"]["product_id"] if s["context"].get("product_id") else "")
                        for s in activity["active_sessions"]]
        label = "Current app: " if activity["status"] == "active" else "Multiple sessions report active: "
        return label + "; ".join(descriptions) + "."
