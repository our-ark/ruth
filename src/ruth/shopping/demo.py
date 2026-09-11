"""Two independent demo app servers, or a local console for Ruth's real runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import sys
import threading
from uuid import uuid4

from ruth.paths import private_state_path
from ruth.state import atomic_write
from .client import load_registry, registry_path
from .service import ShoppingService


SOURCE = Path(__file__).resolve().parents[3]
EXAMPLES = SOURCE / "examples" / "shopping"


def prepare(root, host="127.0.0.1", ports=(8011, 8012), options_port=8010):
    path = registry_path(root)
    if not path.exists():
        apps = [{"app_id": app_id, "name": name, "base_url": f"http://{host}:{port}",
                 "token": secrets.token_urlsafe(32), "connect_token": secrets.token_urlsafe(32)}
                for app_id, name, port in zip(("dayform", "stride"), ("DAYFORM", "STRIDE STUDIO"), ports)]
        atomic_write(path, json.dumps({"apps": apps}, indent=2) + "\n")
    registry = json.loads(path.read_text())
    options_url = f"http://{host}:{options_port}"
    if registry.get("options_url", options_url) != options_url:
        raise ValueError("Existing options page uses a different port; reuse --options-port.")
    if "options_url" not in registry:
        registry["options_url"] = options_url
        atomic_write(path, json.dumps(registry, indent=2) + "\n")
    return load_registry(root)


def servers(root, host="127.0.0.1", ports=(8011, 8012), options_port=8010):
    # Only the demo runner needs the SDK; Ruth's agent client has no SDK dependency.
    sys.path.insert(0, str(SOURCE / "libraries" / "app-sdk" / "src"))
    from our_ark_app_sdk import AppServer, CollaborationStore

    from .options import OptionsServer

    apps = prepare(root, host, ports, options_port)
    built = []
    try:
        for app_id, port in zip(("dayform", "stride"), ports):
            app = apps[app_id]
            if app.base_url != f"http://{host}:{port}":
                raise ValueError("Existing registry uses different ports. Reuse those ports or a new demo root.")
            catalog = json.loads((EXAMPLES / app_id / "catalog.json").read_text())
            store = CollaborationStore(private_state_path(f"demo-apps/{app_id}.sqlite", root), app_id, catalog)
            built.append(AppServer((host, port), store=store, agent_token=app.token,
                                   connect_token=app.connect_token, static_dir=EXAMPLES / app_id,
                                   public_origin=app.base_url, static_files={"/store.js": EXAMPLES / "store.js"}))
        built.append(OptionsServer((host, options_port), [app.base_url for app in apps.values()]))
    except BaseException:
        for server in built:
            server.server_close()
        raise
    return built


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["serve", "console"])
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Ruth instance root (stores state in its .ruth directory)")
    parser.add_argument("--host", choices=["127.0.0.1", "localhost"], default="127.0.0.1")
    parser.add_argument("--dayform-port", type=int, default=8011)
    parser.add_argument("--stride-port", type=int, default=8012)
    parser.add_argument("--options-port", type=int, default=8010)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "console":
        return console(root)
    running = servers(root, args.host, (args.dayform_port, args.stride_port), args.options_port)
    for server in running:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print("Mock stores running. No payments or real orders.", flush=True)
    for app in load_registry(root).values():
        print(f"{app.name}: {app.base_url}", flush=True)
    print(f"View all options: http://{args.host}:{args.options_port}", flush=True)
    print("Send /shop work sneakers, US 9, under $120 total to Ruth, or use the console runner.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for server in running:
            server.shutdown()
            server.server_close()


def console(root):
    from ruth.identity import load_identity
    from ruth.logs import log_conversation_turn
    from ruth.providers.contracts import RuntimeExecutionControl
    from ruth.providers.registry import load_provider
    from ruth.providers.runtime import invoke_runtime_respond

    identity, runtime = load_identity(), load_provider("runtime", root)
    lock, stop = threading.RLock(), threading.Event()
    def respond(prompt, key):
        return invoke_runtime_respond(runtime, identity, prompt, cwd=root,
            execution=RuntimeExecutionControl(session_key=key, cancellation_event=stop)).final_text
    def notify(_chat, message, _key):
        print("\nRuth notification: " + message, flush=True)
        return True
    service = ShoppingService(root, respond=respond, notify=notify,
        record=lambda chat, text, reply: log_conversation_turn(chat_id=chat, message=text, reply=reply, root=root))
    def poll():
        while not stop.wait(1):
            try:
                with lock:
                    errors = service.poll_once("demo-console")
                for error in errors:
                    print(error, flush=True)
            except Exception as error:
                print(f"Shopping poll: {error}", flush=True)
    worker = threading.Thread(target=poll, daemon=True)
    worker.start()
    print("Ruth console uses the configured model, not scripted replies. /quit exits. Use a separate demo root from a live Telegram instance.")
    try:
        while True:
            message = input("You: ").strip()
            if message == "/quit":
                break
            if not message:
                continue
            with lock:
                try:
                    if message.split(maxsplit=1)[0] == "/shop":
                        reply = service.command("demo-console", "console:demo", message[5:].strip(), uuid4().hex)
                    elif service.active_for("demo-console"):
                        reply = service.telegram("demo-console", message, uuid4().hex)
                    else:
                        reply = respond(message, "console:demo")
                    print("Ruth: " + reply, flush=True)
                    log_conversation_turn(chat_id="demo-console", message=message, reply=reply, root=root)
                except Exception as error:
                    print(f"Ruth: {error}", flush=True)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        stop.set()
        worker.join(timeout=6)


if __name__ == "__main__":
    main()
