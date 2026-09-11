"""Reference HTTP adapter for a single preconnected demo account per app.

The store owns its catalog, sessions, message snapshots and mock orders. Agents
only initiate outbound requests. SQLite transactions make retries idempotent.
This loopback demo adapter is not a production identity or payment service.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
from socketserver import TCPServer
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
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


class CollaborationStore:
    def __init__(self, path: Path, app_id: str, catalog: list[dict]):
        self.path, self.app_id = Path(path), identifier(app_id)
        self.catalog = {identifier(p["id"]): p for p in catalog}
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
                CREATE TABLE IF NOT EXISTS orders(key TEXT PRIMARY KEY, request TEXT NOT NULL, body TEXT NOT NULL);
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

    def product(self, product_id):
        if product_id not in self.catalog:
            raise APIError(404, "Product not found")
        p = dict(self.catalog[product_id])
        p["app_id"] = self.app_id
        p["total_cents"] = p["price_cents"] + (p["price_cents"] + 5) // 10
        p["simulated"] = True
        return p

    def products(self, query):
        words = query.get("q", [""])[0].lower().split()
        size = query.get("size", [""])[0]
        try:
            budget = int(query.get("max_price_cents", ["100000000"])[0])
        except (TypeError, ValueError):
            raise APIError(400, "max_price_cents must be an integer")
        return [self.product(p["id"]) for p in self.catalog.values()
                if all(w in json.dumps(p).lower() for w in words)
                and p["price_cents"] <= budget and (not size or size in p["sizes"])]

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
        context = body.get("context")
        if not isinstance(context, dict):
            raise APIError(400, "A context snapshot is required")
        product = self.product(identifier(context.get("product_id")))
        size = context.get("selected_size", "")
        if size and size not in product["sizes"]:
            raise APIError(400, "Selected size is unavailable")
        snapshot = {"revision": identifier(context.get("revision")), "page_type": "product",
                    "product_id": product["id"], "selected_size": size,
                    "product": product}
        event = {"event_id": message_id, "session_id": session_id,
                 "message": {"id": message_id, "text": text}, "context": snapshot,
                 "share_preferences": body.get("share_preferences") is True}
        with self.transaction() as db:
            self.require_session(db, session_id, owner)
            old = db.execute("SELECT body FROM events WHERE id=?", (message_id,)).fetchone()
            if old:
                saved = json.loads(old["body"])
                if any(saved[k] != event[k] for k in event):
                    raise APIError(409, "Message id reused with different content")
                return saved
            event["created_at"] = time.time()
            db.execute("INSERT INTO events(id, session, body) VALUES (?, ?, ?)",
                       (message_id, session_id, json.dumps(event)))
        return event

    def events(self, after):
        with self.transaction() as db:
            rows = db.execute("SELECT cursor, body FROM events WHERE cursor>? ORDER BY cursor LIMIT 20", (after,)).fetchall()
        events = [dict(json.loads(r["body"]), cursor=r["cursor"]) for r in rows]
        return {"events": events, "cursor": rows[-1]["cursor"] if rows else after}

    def output(self, session_id, body):
        identifier(body.get("id"))
        identifier(body.get("in_reply_to"))
        bounded_text(body.get("text"), 24000)
        shared = body.get("shared_context", {})
        if not isinstance(shared, dict) or set(shared) - {"budget_cents", "size", "purpose"}:
            raise APIError(400, "Unsupported shared context")
        if len(json.dumps(body)) > 32000:
            raise APIError(400, "Output too large")
        with self.transaction() as db:
            self.require_session(db, session_id)
            source = db.execute("SELECT body FROM events WHERE id=? AND session=?",
                                (body["in_reply_to"], session_id)).fetchone()
            if not source:
                raise APIError(400, "Reply does not belong to this session")
            if shared and not json.loads(source["body"])["share_preferences"]:
                raise APIError(403, "This message did not authorize preference disclosure")
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

    def order(self, body):
        key = identifier(body.get("idempotency_key"))
        request = {k: body.get(k) for k in ("product_id", "size", "quantity", "max_total_cents")}
        encoded = json.dumps(request, sort_keys=True)
        # BEGIN IMMEDIATE serializes duplicate submissions before checking the key.
        with self.transaction() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT request, body FROM orders WHERE key=?", (key,)).fetchone()
            if old:
                if old["request"] != encoded:
                    raise APIError(409, "Order key reused with different details")
                return json.loads(old["body"])
            p = self.product(identifier(request["product_id"]))
            if request["size"] not in p["sizes"] or request["quantity"] != 1:
                raise APIError(400, "Choose an available size and quantity 1 for this demo")
            ceiling = request["max_total_cents"]
            if type(ceiling) is not int or ceiling < p["total_cents"]:
                raise APIError(409, "Current total exceeds the authorized amount")
            receipt = {"order_id": self.app_id.upper() + "-" + uuid4().hex[:8].upper(),
                       "app_id": self.app_id, "product_id": p["id"], "product_name": p["name"],
                       "size": request["size"], "total_cents": p["total_cents"], "currency": "USD",
                       "status": "confirmed", "simulated": True}
            db.execute("INSERT INTO orders VALUES (?, ?, ?)", (key, encoded, json.dumps(receipt)))
            return receipt


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        # HTTPServer's reverse DNS lookup can stall local/offline demos for minutes.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def __init__(self, address, *, store, agent_token, connect_token, static_dir, public_origin, static_files=None):
        self.store, self.agent_token, self.connect_token = store, agent_token, connect_token
        self.static_dir = Path(static_dir).resolve()
        self.static_files = static_files or {}
        self.public_origin = public_origin.rstrip("/")
        self.cookie_name = "ark_" + store.app_id
        # The cookie is a different credential from the agent's API token.
        self.browser_token = secrets.token_urlsafe(32)
        super().__init__(address, AppHandler)


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Avoid logging account capabilities or message contents.

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def dispatch(self, method):
        try:
            parsed = urlsplit(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            # Prevent alternate Host access (including DNS rebinding) on loopback.
            if self.headers.get("Host") != urlsplit(self.server.public_origin).netloc:
                raise APIError(403, "Unrecognized host")
            body = {}
            if method == "POST":
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 40000:
                    raise APIError(413, "Invalid request size")
                if self.headers.get_content_type() != "application/json":
                    raise APIError(415, "Use application/json")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise APIError(400, "Expected a JSON object")
            agent_route = path.startswith("/collaboration/") or path == "/orders"
            if agent_route:
                if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.agent_token):
                    raise APIError(401, "Agent account credential required")
            if path.startswith("/ui/"):
                if method == "POST" and self.headers.get("Origin") != self.server.public_origin:
                    raise APIError(403, "Same-origin browser request required")
                if path == "/ui/connect" and method == "POST":
                    token = body.get("token", "")
                    if not isinstance(token, str) or not secrets.compare_digest(token, self.server.connect_token):
                        raise APIError(401, "Open a store link from Ruth to connect")
                    cookie = f"{self.server.cookie_name}={self.server.browser_token}; HttpOnly; SameSite=Strict; Path=/"
                    if self.server.public_origin.startswith("https:"):
                        cookie += "; Secure"
                    return self.send_json({"connected": True}, cookie=cookie)
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
                cookie = cookies.get(self.server.cookie_name)
                if not cookie or not secrets.compare_digest(cookie.value, self.server.browser_token):
                    raise APIError(401, "Open a store link from Ruth to connect")
            store = self.server.store
            if method == "GET" and path == "/health":
                return self.send_json({"app_id": store.app_id, "protocol": "our-ark-app/0.1", "simulated": True})
            if method == "GET" and path == "/products":
                return self.send_json({"products": store.products(query)})
            if method == "GET" and path.startswith("/products/"):
                return self.send_json(store.product(path.removeprefix("/products/")))
            if method == "GET" and path == "/collaboration/events":
                after = int(query.get("after", ["0"])[0])
                if after < 0:
                    raise APIError(400, "Invalid cursor")
                return self.send_json(store.events(after))
            match = re.fullmatch(r"/collaboration/sessions/([a-zA-Z0-9_-]+)/outputs", path)
            if method == "POST" and match:
                return self.send_json(store.output(match[1], body))
            if method == "POST" and path == "/orders":
                return self.send_json(store.order(body))
            if method == "POST" and path == "/ui/sessions":
                return self.send_json(store.session("demo-account"))
            if method == "POST" and path == "/ui/messages":
                return self.send_json(store.message("demo-account", body))
            if method == "GET" and path == "/ui/transcript":
                return self.send_json(store.transcript("demo-account", query.get("session_id", [""])[0]))
            if method == "GET":
                return self.static(path)
            raise APIError(404, "Route not found")
        except APIError as error:
            self.send_json({"error": error.message}, error.status)
        except (ValueError, TypeError, KeyError):
            self.send_json({"error": "Malformed request"}, 400)
        except Exception:
            self.send_json({"error": "Application request failed; retry later"}, 500)

    def send_json(self, value, status=200, cookie=None):
        self.send_bytes(json.dumps(value).encode(), "application/json", status, cookie)

    def send_bytes(self, data, content_type, status=200, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def static(self, path):
        if path in self.server.static_files:
            file = Path(self.server.static_files[path])
            return self.send_bytes(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        if path.startswith("/sdk/"):
            base = Path(__file__).parent / "static"
            name = path.removeprefix("/sdk/")
        else:
            base, name = self.server.static_dir, path.lstrip("/") or "index.html"
        file = (base / name).resolve()
        if not file.is_relative_to(base.resolve()) or not file.is_file():
            raise APIError(404, "Page not found")
        self.send_bytes(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
