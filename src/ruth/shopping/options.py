"""Read-only, user-side launcher for the local demo's product tabs.

The server serves static assets and public app origins only. Recommendation data
and browser connection links travel in the URL fragment, never in HTTP requests.
There is no agent endpoint or access to Ruth's conversation on this server.
"""
from base64 import urlsafe_b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from socketserver import TCPServer
from urllib.parse import urljoin, urlsplit

from .client import registry_path


ASSETS = Path(__file__).resolve().parents[3] / "examples/shopping/options"


def options_link(root, cards, apps):
    path = registry_path(root)
    if not cards or not path.exists():
        return ""
    origin = json.loads(path.read_text()).get("options_url", "")
    parsed = urlsplit(origin)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
            or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})):
        return ""
    options = []
    for card in cards[:6]:
        app = apps[card["app_id"]]
        image = urljoin(app.base_url + "/", card.get("image", ""))
        if urlsplit(image).netloc != urlsplit(app.base_url).netloc:
            image = ""
        options.append({"store": card["app_name"], "name": card["name"],
                        "price_cents": card["price_cents"], "total_cents": card["total_cents"],
                        "url": card["link"], "image": image})
    payload = json.dumps({"version": 1, "options": options}, separators=(",", ":")).encode()
    return origin.rstrip("/") + "/#options=" + urlsafe_b64encode(payload).decode().rstrip("=")


class OptionsServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def __init__(self, address, origins):
        self.origins = list(origins)
        super().__init__(address, OptionsHandler)
        self.origin = f"http://{address[0]}:{self.server_port}"


class OptionsHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            return self.respond(b"Unrecognized host", "text/plain", 403)
        path = urlsplit(self.path).path
        if path == "/config.json":
            return self.respond(json.dumps({"origins": self.server.origins}).encode(), "application/json")
        files = {"/": "index.html", "/index.html": "index.html", "/options.js": "options.js", "/options.css": "options.css"}
        if path not in files:
            return self.respond(b"Not found", "text/plain", 404)
        file = ASSETS / files[path]
        return self.respond(file.read_bytes(), mimetypes.guess_type(file.name)[0])

    def do_POST(self):
        self.respond(b"Read-only page", "text/plain", 405)

    def respond(self, content, mime, status=200):
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src "
                         + " ".join(self.server.origins) + "; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)
