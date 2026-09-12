"""Independent, model-free consumption of the optional UAAP activity feed."""
from __future__ import annotations

import json
import time
from datetime import datetime
from uuid import uuid4

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
        return self._snapshot(self.load(), time.time())

    def _snapshot(self, state, now):
        sessions = []
        for app_id, app in state["apps"].items():
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

    def announce(self, chat_id, notify):
        """Announce stable app changes using the chat's durable notification sender.

        The pending text/key is saved before sending. A retry reports the original
        observation time, even if the user has since moved to another app.
        """
        with file_transaction(self.path):
            state, now = self.load(), time.time()
            announcements = state.setdefault("announcements", {})
            delivery = announcements.setdefault(str(chat_id), {})
            pending = delivery.get("pending")
            if pending:
                if not notify(chat_id, pending["text"], pending["key"]):
                    return False
                delivery["last_app"] = pending["app_id"]
                delivery.pop("pending")
                self.save(state)
                return True

            snapshot = self._snapshot(state, now)
            current = snapshot["current_session"]
            active = snapshot["active_sessions"]
            if current is None and active and len({s["app_id"] for s in active}) == 1:
                # Several sessions can leave the exact page uncertain while
                # agreeing on the app. Do not guess a product in that case.
                current = dict(active[0], context={})
            if not current or current["app_id"] == delivery.get("last_app"):
                if delivery.pop("candidate", None) is not None:
                    self.save(state)
                return True
            candidate = delivery.get("candidate")
            if not candidate or candidate["app_id"] != current["app_id"]:
                delivery["candidate"] = {"app_id": current["app_id"], "since": now}
                self.save(state)
                return True
            if now - candidate["since"] < 2:
                return True

            previous = self.apps.get(delivery.get("last_app"))
            route = f"{previous.name} → {current['app_name']}" if previous else current["app_name"]
            label = "App switch" if previous else "Active app"
            context = current["context"]
            product = context.get("product", {})
            product_name = product.get("name") if isinstance(product, dict) else None
            product_name = product_name or context.get("product_id")
            text = f"👣 {label}: {route}"
            if isinstance(product_name, str) and product_name:
                text += f"\nViewing: {product_name[:200]}"
            text += "\nObserved: " + datetime.fromtimestamp(now).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
            delivery["pending"] = {"app_id": current["app_id"], "text": text,
                                   "key": "shopping-app-switch-" + uuid4().hex}
            delivery.pop("candidate", None)
            self.save(state)
            pending = delivery["pending"]
            if not notify(chat_id, pending["text"], pending["key"]):
                return False
            delivery["last_app"] = pending["app_id"]
            delivery.pop("pending")
            self.save(state)
            return True

    def summary(self):
        activity = self.snapshot()
        if not activity["active_sessions"]:
            return "Current app: unknown (no fresh focused session)."
        descriptions = [s["app_name"] + (" · " + s["context"]["product_id"] if s["context"].get("product_id") else "")
                        for s in activity["active_sessions"]]
        label = "Current app: " if activity["status"] == "active" else "Multiple sessions report active: "
        return label + "; ".join(descriptions) + "."
