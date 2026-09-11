from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ruth.paths import private_state_path


class ShoppingError(RuntimeError):
    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None  # Never forward account credentials to a redirected host.


def registry_path(root: Path) -> Path:
    return private_state_path("shopping/registry.json", root)


@dataclass(frozen=True)
class AppConnection:
    app_id: str
    name: str
    base_url: str
    token: str = field(repr=False)
    connect_token: str = field(repr=False)

    def request(self, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base_url + path, data=data,
                          headers={"Authorization": "Bearer " + self.token,
                                   "Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=5) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ShoppingError(f"{self.name} returned too much data")
                return json.loads(raw)
        except HTTPError as error:
            try:
                detail = json.loads(error.read(2000)).get("error", "Request rejected")
            except (ValueError, TypeError):
                detail = "Request rejected"
            raise ShoppingError(f"{self.name}: {detail} (HTTP {error.code})", retryable=error.code >= 500 or error.code == 429) from None
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise ShoppingError(f"{self.name} is unavailable ({type(error).__name__}); retry later", retryable=True) from None

    def products(self, **filters):
        return self.request("/products?" + urlencode(filters))["products"]

    def product(self, product_id):
        return self.request("/products/" + quote(product_id, safe=""))

    def image(self, path):
        """Read a public catalog image from this app, without account credentials."""
        if not isinstance(path, str) or not path or any(ord(c) < 32 for c in path):
            raise ShoppingError("Missing or invalid product image")
        url = urlsplit(urljoin(self.base_url + "/", path))
        origin = urlsplit(self.base_url)
        if ((url.scheme, url.netloc) != (origin.scheme, origin.netloc)
                or url.username or url.password or url.fragment):
            raise ShoppingError("Product images must belong to the registered app")
        limit = 8_000_000
        try:
            with build_opener(NoRedirect()).open(Request(url.geturl()), timeout=5) as response:
                content = response.read(limit + 1)
                mime = response.headers.get_content_type()
        except (URLError, TimeoutError, OSError, ValueError):
            raise ShoppingError(f"{self.name}'s product image is unavailable") from None
        valid = ((mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
                 or (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")))
        if not valid or len(content) > limit:
            raise ShoppingError("Product image must be a PNG or JPEG under 8 MB")
        return content, mime

    def link(self, product_id):
        return self.base_url + "/?" + urlencode({"product": product_id}) + "#" + urlencode({"connect": self.connect_token})


def load_registry(root: Path) -> dict[str, AppConnection]:
    path = registry_path(root)
    if not path.exists():
        raise ShoppingError("Shopping is not configured. Run bin/ruth-shopping-demo serve for this instance first.")
    try:
        raw = json.loads(path.read_text())
        entries = raw["apps"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
            raise ValueError("Expected 1–8 registered apps")
        apps = {}
        for entry in entries:
            app = AppConnection(**entry)
            url = urlsplit(app.base_url)
            if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
                raise ValueError("Expected an application origin")
            if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
                raise ValueError("Use HTTPS outside loopback")
            if not app.token or not app.connect_token or app.app_id in apps:
                raise ValueError("Missing credentials or duplicate app id")
            apps[app.app_id] = app
        return apps
    except (ValueError, TypeError, KeyError):
        raise ShoppingError("Invalid shopping registry; see docs/shopping-demo.md") from None
