"""Outbound calls to one authenticated UAAP application connection."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import ClassVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class UAAPError(RuntimeError):
    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None  # Never forward account credentials to a redirected host.


@dataclass(frozen=True)
class AppClient:
    app_id: str
    name: str
    base_url: str
    token: str = field(repr=False)
    error_type: ClassVar[type[UAAPError]] = UAAPError

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if (not url.hostname or url.username or url.password or url.query or url.fragment
                or url.path not in ("", "/")):
            raise ValueError("Expected an application origin")
        if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("Use HTTPS outside loopback")
        if not isinstance(self.token, str) or not self.token or any(ord(c) < 32 for c in self.token):
            raise ValueError("An app account credential is required")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    def request(self, path: str, body=None):
        """Make an app-relative JSON call; callers retain IDs when retrying writes."""
        if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
                or urlsplit(path).fragment or any(ord(c) < 32 for c in path)):
            raise ValueError("Expected an app-relative request path")
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base_url + path, data=data,
                          headers={"Authorization": "Bearer " + self.token,
                                   "Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=5) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise self.error_type(f"{self.name} returned too much data")
                return json.loads(raw)
        except HTTPError as error:
            try:
                detail = json.loads(error.read(2000)).get("error", "Request rejected")
            except (ValueError, TypeError, AttributeError):
                detail = "Request rejected"
            raise self.error_type(f"{self.name}: {detail} (HTTP {error.code})",
                                  retryable=error.code >= 500 or error.code == 429) from None
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise self.error_type(f"{self.name} is unavailable ({type(error).__name__}); retry later",
                                  retryable=True) from None

    def events(self, after=0):
        """Read a finite event batch without acknowledging or advancing a cursor."""
        if type(after) is not int or after < 0:
            raise ValueError("after must be a non-negative integer")
        batch = self.request(f"/collaboration/events?after={after}")
        if not isinstance(batch, dict) or not isinstance(batch.get("events"), list):
            raise self.error_type(f"{self.name} returned an invalid event batch")
        cursor = after
        for event in batch["events"]:
            if (not isinstance(event, dict) or type(event.get("cursor")) is not int
                    or event["cursor"] <= cursor):
                raise self.error_type(f"{self.name} returned an invalid cursor")
            cursor = event["cursor"]
        if type(batch.get("cursor")) is not int or batch["cursor"] != cursor:
            raise self.error_type(f"{self.name} returned an invalid batch cursor")
        return batch

    def output(self, session_id, body):
        """Deliver an output containing a stable id and in_reply_to message ID."""
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", session_id):
            raise ValueError("Invalid session identifier")
        if not isinstance(body, dict):
            raise ValueError("Expected an output object")
        return self.request(f"/collaboration/sessions/{session_id}/outputs", body)
