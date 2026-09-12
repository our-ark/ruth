"""Real HTTP/SQLite integration tests. The reasoning fixture is deliberately not an LLM.

These check collaboration mechanics, not model quality or live Telegram delivery.
"""
from dataclasses import replace
from http.cookiejar import CookieJar
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libraries/app-sdk/src"))
from our_ark_app_sdk import AppServer, CollaborationStore
from ruth.shopping.client import AppConnection, ShoppingError
from ruth.shopping.service import ShoppingService


class ReasoningFixture:
    def __init__(self):
        self.calls = []

    def __call__(self, prompt, session_key):
        payload = json.loads(prompt.split("Turn data (JSON):\n", 1)[1])
        self.calls.append((session_key, payload))
        result = payload.get("tool_result", {})
        if isinstance(result, dict) and result.get("order_id"):
            return json.dumps({"reply": "Your mock order is ready."})
        turn = payload["turn"]
        if "place a simulated order" in turn["message"]["text"]:
            telegram = turn["source"] == "telegram"
            return json.dumps({"tool": "orderProduct", "app_id": "dayform" if telegram else turn["source"],
                               "arguments": {"product_id": "day-one-lite" if telegram else turn["context"]["product_id"],
                                             "size": "9", "quantity": 1, "max_total_cents": 12000}})
        if turn["source"] == "telegram":
            return json.dumps({"reply": "Two options for your workday.", "recommendations": [
                {"app_id": "dayform", "product_id": "day-one"},
                {"app_id": "stride", "product_id": "arc-02"}]})
        previous = [t["context"].get("product_id") for t in payload.get("recent_collaboration", []) if t["source"] != "telegram"]
        return json.dumps({"reply": f"Viewing {turn['context']['product_id']}; earlier pairs: {previous}.",
                           "shared_context": {"budget_cents": 12000, "size": "9", "purpose": "walk to work", "private_email": "must not escape"}})


class ShoppingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.servers, self.apps, self.browsers, self.sessions = {}, {}, {}, {}
        for app_id in ("dayform", "stride"):
            folder = ROOT / "examples/shopping" / app_id
            store = CollaborationStore(self.root / f"{app_id}.sqlite", app_id, json.loads((folder / "catalog.json").read_text()))
            server = AppServer(("127.0.0.1", 0), store=store, agent_token=f"agent-{app_id}",
                connect_token=f"browser-{app_id}", static_dir=folder, public_origin="http://127.0.0.1:0")
            server.public_origin = f"http://127.0.0.1:{server.server_port}"
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            self.servers[app_id] = server
            self.apps[app_id] = AppConnection(app_id, app_id, server.public_origin, f"agent-{app_id}", f"browser-{app_id}")
            self.browsers[app_id] = build_opener(HTTPCookieProcessor(CookieJar()))
            self.ui(app_id, "/ui/connect", {"token": f"browser-{app_id}"})
            self.sessions[app_id] = self.ui(app_id, "/ui/sessions", {})["session_id"]
        self.brain, self.notifications, self.records = ReasoningFixture(), [], []
        self.service = self.new_service()

    def new_service(self, effect=lambda fn, *a, **kw: fn(*a, **kw), notify=None, send_photos=None):
        def sent(chat, message, key):
            self.notifications.append((chat, message, key))
            return True
        return ShoppingService(self.root, apps=self.apps, respond=self.brain, notify=notify or sent,
                               record=lambda *a: self.records.append(a), effect=effect, send_photos=send_photos)

    def ui(self, app_id, path, body=None, origin=None):
        app = self.apps[app_id]
        req = Request(app.base_url + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json", "Origin": origin or app.base_url})
        with self.browsers[app_id].open(req, timeout=3) as response:
            return json.loads(response.read())

    def message(self, app_id, product_id, text="What about this pair?", share=False, message_id=None, session=None):
        body = {"id": message_id or uuid4().hex, "session_id": session or self.sessions[app_id], "text": text,
                "context": {"revision": uuid4().hex, "product_id": product_id, "selected_size": "9"},
                "share_preferences": share}
        return self.ui(app_id, "/ui/messages", body)

    def transcript(self, app_id, session=None):
        return self.ui(app_id, "/ui/transcript?session_id=" + (session or self.sessions[app_id]))

    def kickoff(self):
        return self.service.command(42, "telegram:42", "work sneakers, US 9, under $120 total", "telegram-1")

    def activity(self, app, kind, sequence, **fields):
        return self.ui(app, "/ui/activity", {"event_id": uuid4().hex, "session_id": self.sessions[app],
                                             "type": kind + ".updated", "sequence": sequence, **fields})

    def test_activity_expiry_switching_and_ambiguous_sessions_do_not_invoke_model(self):
        from unittest.mock import patch
        self.kickoff()
        with patch('ruth.shopping.activity.time.time', return_value=1000):
            self.activity('dayform', 'context', 1,
                          context={'revision': 'r1', 'product_id': 'day-one', 'selected_size': '9'})
            self.activity('dayform', 'presence', 1, state='active')
            self.assertEqual(self.service.activity.poll_once(), [])
            self.assertEqual(self.service.activity.snapshot()['current_session']['app_id'], 'dayform')
            self.activity('stride', 'presence', 1, state='active')
            self.service.activity.poll_once()
            self.assertEqual(self.service.activity.snapshot()['status'], 'ambiguous')
            self.activity('dayform', 'presence', 2, state='inactive')
            self.service.activity.poll_once()
            self.assertEqual(self.service.activity.snapshot()['current_session']['app_id'], 'stride')
            self.assertIn('stride', self.service.command(42, 'telegram:42', 'status', 'status'))
        with patch('ruth.shopping.activity.time.time', return_value=1046):
            self.assertEqual(self.new_service().activity.snapshot()['status'], 'unknown')
            # Restart/re-reading old state must never renew an expired lease.
            self.new_service().activity.poll_once()
            self.assertEqual(self.service.activity.snapshot()['status'], 'unknown')
        self.assertEqual(len(self.brain.calls), 1)
        self.assertEqual(self.notifications, [])
        self.assertEqual(self.transcript('dayform')['messages'], [])

    def test_active_task_announces_to_owner_without_model_calls_and_cancel_stops_it(self):
        from unittest.mock import patch
        self.kickoff()
        with patch('ruth.shopping.activity.time.time', return_value=1000):
            self.activity('dayform', 'presence', 1, state='active')
            self.assertEqual(self.service.poll_activity(43), [])
            self.assertFalse(self.service.activity.path.exists(), 'another chat must not consume activity')
            self.assertEqual(self.service.poll_activity(42), [])
        with patch('ruth.shopping.activity.time.time', return_value=1003):
            self.assertEqual(self.service.poll_activity(42), [])
            self.assertEqual(len(self.notifications), 1)
            self.assertEqual(self.notifications[0][0], 42)
            self.assertIn('Active app: dayform', self.notifications[0][1])
            self.assertEqual(self.new_service().poll_activity(42), [])
            self.assertEqual(len(self.notifications), 1)
            self.service.command(42, 'telegram:42', 'cancel', 'cancel')
            self.activity('dayform', 'presence', 2, state='inactive')
            self.activity('stride', 'presence', 1, state='active')
        with patch('ruth.shopping.activity.time.time', return_value=1006):
            self.service.poll_activity(42)
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(len(self.brain.calls), 1)

    def test_activity_keeps_up_during_reasoning_without_changing_message_context(self):
        self.kickoff()
        self.message('dayform', 'day-one', 'Question on the first pair')
        entered, release = threading.Event(), threading.Event()
        failures = []
        def respond(prompt, key):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test did not release model')
            return self.brain(prompt, key)
        self.service.respond = respond
        def run():
            try:
                failures.extend(self.service.poll_once(42))
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.activity('stride', 'context', 1,
                          context={'revision': 'r2', 'product_id': 'arc-02', 'selected_size': '9'})
            self.activity('stride', 'presence', 1, state='active')
            self.assertEqual(self.service.activity.poll_once(), [])
            self.assertEqual(self.service.activity.snapshot()['current_session']['app_id'], 'stride')
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertIn('Viewing day-one;', self.transcript('dayform')['outputs'][0]['text'])
        self.assertEqual(self.transcript('stride')['outputs'], [])
        self.service.telegram(42, 'What am I looking at?', 'current-page')
        observed = self.brain.calls[-1][1]['app_activity']['current_session']
        self.assertEqual(observed['context']['product_id'], 'arc-02')

    def test_activity_browser_routes_require_authentication_and_same_origin(self):
        body = {'event_id': 'p1', 'session_id': self.sessions['dayform'], 'sequence': 1,
                'type': 'presence.updated', 'state': 'active'}
        with self.assertRaises(HTTPError) as caught:
            self.ui('dayform', '/ui/activity', body, origin='https://elsewhere.example')
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()
        request = Request(self.apps['dayform'].base_url + '/ui/activity', data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'Origin': self.apps['dayform'].base_url})
        with self.assertRaises(HTTPError) as caught:
            build_opener().open(request, timeout=3)
        self.assertEqual(caught.exception.code, 401)
        caught.exception.close()

    def test_delayed_activity_reads_use_server_lease_age_across_clock_skew(self):
        from unittest.mock import patch
        with patch('our_ark_app_sdk.store.time.time', return_value=1000):
            self.activity('dayform', 'presence', 1, state='active')
            batch = self.apps['dayform'].activity()
        batch['server_time'] = 1040  # Five seconds remain when the agent reads it.
        tracker = self.service.activity
        tracker.apps = {'dayform': self.apps['dayform']}
        with patch.object(AppConnection, 'activity', return_value=batch), \
                patch('ruth.shopping.activity.time.time', return_value=90000):
            tracker.poll_once()
            self.assertEqual(tracker.snapshot()['status'], 'active')
        with patch('ruth.shopping.activity.time.time', return_value=90006):
            self.assertEqual(tracker.snapshot()['status'], 'unknown')
        # Even if only first observed after expiry, it must start out unknown.
        batch['cursor'] += 1
        batch['events'][0].update(cursor=batch['cursor'], sequence=2)
        batch['server_time'] = 1050
        with patch.object(AppConnection, 'activity', return_value=batch), \
                patch('ruth.shopping.activity.time.time', return_value=90007):
            tracker.poll_once()
            self.assertEqual(tracker.snapshot()['status'], 'unknown')

    def test_three_surfaces_share_runtime_session_and_message_time_context(self):
        reply = self.kickoff()
        self.assertIn("#connect=browser-dayform", reply)
        self.assertIn("#connect=browser-stride", reply)
        self.service.poll_once(42)
        self.assertEqual(len(self.brain.calls), 1, "empty polls must not invoke the model")
        first = self.message("dayform", "day-one")
        # User switches product/session/app before the first reply exists.
        other = self.ui("dayform", "/ui/sessions", {})["session_id"]
        self.message("stride", "arc-02", "Better than the first?", share=True)
        self.message("dayform", "day-one-lite", "Now this one?", session=other)
        self.assertEqual(self.service.poll_once(42), [])
        a, b, returned = self.transcript("dayform"), self.transcript("stride"), self.transcript("dayform", other)
        self.assertIn("Viewing day-one;", a["outputs"][0]["text"])
        self.assertEqual(a["outputs"][0]["in_reply_to"], first["message"]["id"])
        self.assertIn("day-one", b["outputs"][0]["text"])
        self.assertIn("arc-02", returned["outputs"][0]["text"])
        self.assertEqual(a["outputs"][0]["shared_context"], {})
        self.assertEqual(b["outputs"][0]["shared_context"], {"budget_cents": 12000, "size": "9", "purpose": "walk to work"})
        self.assertEqual({key for key, _ in self.brain.calls}, {"telegram:42"})
        self.assertNotIn("#connect=", json.dumps(self.brain.calls))
        self.assertEqual(len(self.service.load()["conversation"]), 4)
        self.assertEqual(len(self.records), 3)
        calls = len(self.brain.calls)
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.brain.calls), calls)
        self.assertEqual(self.kickoff(), reply, "redelivery of /shop must reuse its answer")

    def test_website_transcripts_include_both_speakers_and_source_once(self):
        self.kickoff()
        self.message("dayform", "day-one", "这双适合通勤吗？")
        self.message("stride", "arc-02", "Compare with DAYFORM.")
        self.assertEqual(self.service.poll_once(42), [])
        self.assertEqual(len(self.notifications), 2)
        for (chat, text, key), app, question in zip(self.notifications,
                ("dayform", "stride"), ("这双适合通勤吗？", "Compare with DAYFORM.")):
            self.assertEqual(chat, 42)
            self.assertIn(f"[{app} · Website", text)
            self.assertIn("You:\n" + question, text)
            self.assertIn("Ruth:\n" + self.transcript(app)["outputs"][0]["text"], text)
            self.assertTrue(key.startswith("shopping-transcript-app-"))
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.notifications), 2)

    def test_transcript_failure_retries_same_text_and_key_after_restart(self):
        self.kickoff()
        self.message("dayform", "day-one")
        attempts = []
        def unavailable(*args):
            attempts.append(args)
            return False
        self.assertTrue(self.new_service(notify=unavailable).poll_once(42))
        self.assertEqual(len(self.transcript("dayform")["outputs"]), 1)
        calls = len(self.brain.calls)
        self.assertEqual(self.service.load()["cursors"].get("dayform", 0), 0)
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.brain.calls), calls)
        self.assertEqual(self.notifications, attempts)
        self.assertEqual(len(self.transcript("dayform")["outputs"]), 1)
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.notifications), 1)

    def test_reply_retry_uses_durable_output_not_a_second_model_turn(self):
        self.kickoff()
        self.message("dayform", "day-one")
        dropped = []
        def effect(fn, *a, **kw):
            result = fn(*a, **kw)
            if getattr(fn, "__name__", "") == "output" and not dropped:
                dropped.append(True)
                raise ShoppingError("simulated connection loss after commit", retryable=True)
            return result
        service = self.new_service(effect=effect)
        self.assertTrue(service.poll_once(42))
        calls = len(self.brain.calls)
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.brain.calls), calls)
        self.assertEqual(len(self.transcript("dayform")["outputs"]), 1)

    def test_order_timeout_recovers_one_purchase_then_notifies_telegram(self):
        self.kickoff()
        self.message("dayform", "day-one", "Please place a simulated order in US 9, up to $120 total.")
        dropped = []
        def effect(fn, *a, **kw):
            result = fn(*a, **kw)
            if a and a[0] == "/orders" and not dropped:
                dropped.append(True)
                raise ShoppingError("lost order response", retryable=True)
            return result
        self.assertTrue(self.new_service(effect=effect).poll_once(42))
        self.assertEqual(self.transcript("dayform")["outputs"], [])
        self.assertEqual(self.new_service().poll_once(42), [])
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 1)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("$107.80", self.notifications[0][1])
        self.assertEqual(self.notifications[0][0], 42)
        self.assertIn("Simulated order confirmed", self.transcript("dayform")["outputs"][0]["text"])
        self.assertTrue(self.service.active_for(42))

    def test_notification_failure_does_not_end_task_or_repeat_order(self):
        self.kickoff()
        self.message("dayform", "day-one", "Please place a simulated order in US 9, up to $120 total.")
        self.assertTrue(self.new_service(notify=lambda *_: False).poll_once(42))
        self.assertTrue(self.service.active_for(42))
        calls = len(self.brain.calls)
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.brain.calls), calls)
        self.assertEqual(len(self.transcript("dayform")["outputs"]), 1)
        self.assertTrue(self.service.active_for(42))

    def test_cancel_stops_connections_but_retains_conversation_and_queued_messages(self):
        self.kickoff()
        self.service.command(42, "telegram:42", "cancel", "cancel-1")
        self.assertFalse(self.service.active_for(42))
        self.message("dayform", "day-one")
        self.assertEqual(self.service.poll_once(42), [])
        self.assertEqual(len(self.brain.calls), 1)
        self.service.command(42, "telegram:42", "Continue our shoe search", "telegram-2")
        self.assertEqual(self.service.poll_once(42), [])
        self.assertEqual(len(self.service.load()["conversation"]), 3)
        with self.assertRaises(ShoppingError):
            self.service.command(99, "telegram:99", "shoes", "wrong-owner")

    def test_order_does_not_disconnect_followups_in_either_store_or_telegram(self):
        self.kickoff()
        self.message("dayform", "day-one-lite", "Please place a simulated order in US 9, up to $120 total.")
        self.message("dayform", "day-one-lite", "Remind me which size I selected?")
        self.message("stride", "arc-01", "How does this compare to the pair I ordered?")
        self.assertEqual(self.service.poll_once(42), [])
        outputs = self.transcript("dayform")["outputs"]
        self.assertEqual(len(outputs), 2, "messages queued after an order must still be handled")
        self.assertEqual(outputs[0]["order"]["product_id"], "day-one-lite")
        self.assertEqual(outputs[0]["order"]["size"], "9")
        self.assertIn("day-one-lite", self.transcript("stride")["outputs"][0]["text"])
        self.assertTrue(self.new_service().active_for(42), "restart must preserve the connection")
        self.service.telegram(42, "Thanks. Show me the options again.", "post-order")
        self.assertEqual({key for key, _ in self.brain.calls}, {"telegram:42"})
        self.assertEqual(len(self.notifications), 3, "each website turn is mirrored, including follow-ups")
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 1)
        self.service.command(42, "telegram:42", "cancel", "done")
        self.message("stride", "arc-01", "This stays queued until I resume.")
        calls = len(self.brain.calls)
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(len(self.brain.calls), calls)

    def test_new_shop_can_order_same_product_without_losing_history_or_replaying_purchases(self):
        self.kickoff()
        first_task = self.service.load()["task"]["id"]
        order_text = "Please place a simulated order for this pair in US 9, quantity 1, up to $85.80 total."
        self.message("dayform", "day-one-lite", order_text)
        self.assertEqual(self.service.poll_once(42), [])
        first_order = self.transcript("dayform")["outputs"][-1]["order"]
        reply = self.service.command(42, "telegram:42", "work sneakers, US 9, under $120 total", "telegram-2")
        second_task = self.service.load()["task"]["id"]
        self.assertNotEqual(first_task, second_task)
        kickoff = self.brain.calls[-1][1]
        self.assertEqual(kickoff["current_task"], {"id": second_task,
                         "request": "work sneakers, US 9, under $120 total", "is_new_task": True})
        self.assertEqual(kickoff["prior_orders"], [{"task_id": first_task, "order": first_order}])
        self.assertIsNone(kickoff["current_request_order"])
        second = self.message("dayform", "day-one-lite", order_text)
        self.assertEqual(self.new_service().poll_once(42), [])
        second_order = self.transcript("dayform")["outputs"][-1]["order"]
        self.assertNotEqual(first_order["order_id"], second_order["order_id"])
        self.assertEqual(first_order["product_id"], second_order["product_id"])
        self.assertEqual(second_order["total_cents"], 8580)
        turns = [p for _, p in self.brain.calls if p["turn"]["message"]["id"] == second["message"]["id"]]
        self.assertGreaterEqual(len(turns), 2)
        for turn in turns:
            self.assertEqual(turn["current_task"]["id"], second_task)
            self.assertEqual(turn["prior_orders"][0]["order"]["order_id"], first_order["order_id"])
        self.assertIsNone(turns[0]["current_request_order"])
        self.assertEqual(turns[-1]["current_request_order"], second_order)
        # Re-delivering the same message and /shop events must not buy again or reset the task.
        self.ui("dayform", "/ui/messages", {"id": second["message"]["id"], "session_id": second["session_id"],
                "text": second["message"]["text"], "context": second["context"], "share_preferences": False})
        self.assertEqual(self.new_service().poll_once(42), [])
        self.assertEqual(self.service.command(42, "telegram:42", "work sneakers, US 9, under $120 total", "telegram-2"), reply)
        self.kickoff()
        self.assertEqual(self.service.load()["task"]["id"], second_task)
        self.assertEqual({p[0] for p in self.brain.calls}, {"telegram:42"})
        self.assertEqual({t["task_id"] for t in self.service.load()["conversation"]}, {first_task, second_task})
        self.assertEqual(len(self.notifications), 2)
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 2)

    def test_explicit_repeat_order_in_one_task_is_distinct_from_delivery_retry(self):
        self.kickoff()
        first = self.service.telegram(42, "Please place a simulated order for Day One Lite, US 9, under $120 total.", "order-one")
        task_id = self.service.load()["task"]["id"]
        second = self.service.telegram(42, "Please place a simulated order for another pair of Day One Lite, US 9, under $120 total.", "order-two")
        self.assertNotEqual(first, second)
        self.assertEqual(task_id, self.service.load()["task"]["id"])
        self.assertEqual(self.service.telegram(42, "Please place a simulated order for another pair of Day One Lite, US 9, under $120 total.", "order-two"), second)
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 2)

    def test_shop_retry_after_runtime_failure_keeps_one_task_identity(self):
        service = self.new_service()
        def unavailable(*_):
            raise RuntimeError("runtime unavailable")
        service.respond = unavailable
        with self.assertRaises(ShoppingError):
            service.command(42, "telegram:42", "work sneakers", "kickoff-retry")
        task_id = service.load()["task"]["id"]
        self.new_service().command(42, "telegram:42", "work sneakers", "kickoff-retry")
        self.assertEqual(self.service.load()["task"]["id"], task_id)
        self.assertEqual(self.brain.calls[-1][1]["current_task"]["id"], task_id)

    def test_web_order_photo_survives_restart_without_duplicate_confirmation(self):
        from unittest.mock import patch
        self.kickoff()
        self.message("dayform", "day-one-lite", "Please place a simulated order in US 9, up to $120 total.")
        photos = []
        def sent(*args):
            photos.append(args)
            return {"message_ids": [36], "media_group_id": None}
        service = self.new_service(send_photos=sent)
        save = service.save
        def crash_after_photo(state):
            if any(r.get("notified") for r in state["receipts"].values()):
                raise OSError("crash before notification flag was saved")
            save(state)
        with patch.object(service, "save", side_effect=crash_after_photo), self.assertRaises(OSError):
            service.poll_once(42)
        self.assertEqual(self.new_service(send_photos=sent).poll_once(42), [])
        self.assertEqual(len(photos), 1)
        chat, images, caption = photos[0]
        self.assertEqual(chat, 42)
        self.assertEqual(images, [((ROOT / "examples/shopping/dayform/shoe.png").read_bytes(), "image/png")])
        order = next(r["order"] for r in service.load()["receipts"].values() if "order" in r)
        for fact in (order["order_id"], "Day One Lite / Ink", "US 9", "$85.80", "No payment was taken."):
            self.assertIn(fact, caption)
        self.assertEqual(len(self.notifications), 1, "website transcript accompanies the order photo")
        self.assertTrue(service.active_for(42))
        self.assertEqual(len(self.transcript("dayform")["outputs"]), 1)
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 1)

    def test_failed_order_photo_and_text_retry_never_repeat_upload_or_purchase(self):
        self.kickoff()
        self.message("dayform", "day-one-lite", "Please place a simulated order in US 9, up to $120 total.")
        attempts = []
        def uncertain(*args):
            attempts.append(args)
            raise ShoppingError("Telegram photo delivery could not be confirmed")
        self.assertTrue(self.new_service(send_photos=uncertain, notify=lambda *_: False).poll_once(42))
        self.assertTrue(self.service.active_for(42))
        calls = len(self.brain.calls)
        self.assertEqual(self.new_service(send_photos=uncertain).poll_once(42), [])
        self.assertEqual(len(attempts), 1)
        self.assertEqual(len(self.brain.calls), calls)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("$85.80", self.notifications[0][1])
        self.assertTrue(self.service.active_for(42))
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 1)

    def test_unavailable_order_image_falls_back_to_full_confirmation(self):
        self.kickoff()
        self.message("dayform", "day-one-lite", "Please place a simulated order in US 9, up to $120 total.")
        photos = []
        def missing_image(fn, *a, **kw):
            if fn.__name__ == "image":
                raise ShoppingError("Product image is unavailable")
            return fn(*a, **kw)
        self.assertEqual(self.new_service(effect=missing_image, send_photos=lambda *a: photos.append(a)).poll_once(42), [])
        self.assertEqual(photos, [])
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("Simulated order confirmed", self.notifications[0][1])
        self.assertIn("$85.80", self.notifications[0][1])
        self.assertTrue(self.service.active_for(42))

    def test_telegram_order_photo_uses_order_facts_and_keeps_conversation_active(self):
        from unittest.mock import patch
        self.kickoff()
        text = self.service.telegram(42, "Please place a simulated order for Day One Lite, US 9, up to $120 total.", "telegram-order")
        self.assertTrue(self.service.active_for(42))
        photos = []
        def sent(*args):
            photos.append(args)
            return {"message_ids": [37], "media_group_id": None}
        product = dict(self.apps["dayform"].product("day-one-lite"), name="Changed catalog name", total_cents=99999)
        with patch.object(AppConnection, "product", return_value=product):
            self.assertFalse(self.service.deliver_photos(99, "telegram-order", sent).delivered)
            self.assertTrue(self.service.deliver_photos(42, "telegram-order", sent).delivered)
        self.assertTrue(self.new_service().deliver_photos(42, "telegram-order", sent).delivered)
        self.assertEqual(len(photos), 1)
        self.assertIn("Day One Lite / Ink", photos[0][2])
        self.assertIn("$85.80", photos[0][2])
        self.assertNotIn("Changed catalog name", photos[0][2])
        self.assertIn("$85.80", text)

    def test_account_auth_session_routing_and_disclosure_boundaries(self):
        with self.assertRaises(ShoppingError):
            replace(self.apps["dayform"], token="wrong").request("/collaboration/events")
        with self.assertRaises(HTTPError) as error:
            self.ui("dayform", "/ui/messages", {}, origin="https://unrelated.example")
        self.assertEqual(error.exception.code, 403)
        event = self.message("dayform", "day-one")
        output = {"id": "output-1", "in_reply_to": event["message"]["id"], "text": "Hello", "shared_context": {}}
        app = self.apps["dayform"]
        other = self.ui("dayform", "/ui/sessions", {})["session_id"]
        with self.assertRaises(ShoppingError):
            app.request(f"/collaboration/sessions/{other}/outputs", output)
        path = f"/collaboration/sessions/{event['session_id']}/outputs"
        with self.assertRaises(ShoppingError):
            app.request(path, dict(output, shared_context={"size": "9"}))
        self.assertEqual(app.request(path, output), app.request(path, output))
        with self.assertRaises(ShoppingError):
            app.request(path, dict(output, text="changed"))
        with self.assertRaises(HTTPError):
            self.ui("stride", "/ui/transcript?session_id=" + event["session_id"])

    def test_product_filter_and_mock_order_price_authority(self):
        app = self.apps["dayform"]
        products = app.products(q="sneakers", max_price_cents=8000, size="9")
        self.assertEqual([p["id"] for p in products], ["day-one-lite"])
        body = {"idempotency_key": "one-order", "product_id": "day-one", "size": "9", "quantity": 1, "max_total_cents": 10000}
        with self.assertRaises(ShoppingError):
            app.request("/orders", body)
        body["max_total_cents"] = 12000
        one = app.request("/orders", body)
        self.assertEqual(one, app.request("/orders", body))
        self.assertEqual(one["total_cents"], 10780)
        with self.assertRaises(ShoppingError):
            app.request("/orders", dict(body, size="10"))

    def test_recommendation_photos_use_catalog_facts_and_survive_replay(self):
        reply = self.kickoff()
        photos = []
        def sent(chat, images, caption):
            photos.append((chat, images, caption))
            return {"message_ids": [1, 2], "media_group_id": "album-1"}
        self.assertFalse(self.service.deliver_photos(99, "telegram-1", sent).delivered)
        self.assertEqual(photos, [], "only the registry's owner can receive photos")
        self.assertTrue(self.service.deliver_photos(42, "telegram-1", sent).delivered)
        self.assertEqual(len(photos), 1, "all recommended products use one upload")
        self.assertEqual(photos[0][0], 42)
        self.assertEqual(photos[0][1][0][0], (ROOT / "examples/shopping/dayform/shoe.png").read_bytes())
        self.assertEqual(photos[0][1][0][1], "image/png")
        self.assertIn("$107.80 total", photos[0][2])
        self.assertIn("$123.20 total", photos[0][2])
        self.assertIn("#connect=browser-dayform", photos[0][2])
        self.assertIn("Two options for your workday", photos[0][2])
        self.assertEqual(self.kickoff(), reply)
        self.assertTrue(self.new_service().deliver_photos(42, "telegram-1", sent).delivered)
        self.assertEqual(len(photos), 1)
        self.assertEqual(len(self.brain.calls), 1)

    def test_failed_or_ambiguous_photo_upload_retains_text_and_does_not_replay(self):
        reply = self.kickoff()
        attempts = []
        def uncertain(*args):
            attempts.append(args)
            raise ShoppingError("Telegram photo delivery could not be confirmed")
        self.assertTrue(self.service.deliver_photos(42, "telegram-1", uncertain).error)
        self.assertFalse(self.new_service().deliver_photos(42, "telegram-1", uncertain).delivered)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.kickoff(), reply)
        self.assertIn("#connect=browser-dayform", reply)
        self.assertTrue(self.service.active_for(42))

    def test_duplicate_recommendations_produce_one_photo_and_missing_image_falls_back(self):
        self.service.respond = lambda *_: json.dumps({"reply": "This pair.", "recommendations": [
            {"app_id": "dayform", "product_id": "day-one"},
            {"app_id": "dayform", "product_id": "day-one"}]})
        self.kickoff()
        state = self.service.load()
        receipt = next(iter(state["receipts"].values()))
        self.assertEqual(len(receipt["output"]["recommendations"]), 1)
        receipt["output"]["recommendations"][0]["image"] = "/missing.png"
        self.service.save(state)
        photos = []
        self.assertTrue(self.service.deliver_photos(42, "telegram-1", lambda *a: photos.append(a)).error)
        self.assertEqual(photos, [])
        self.assertIn("This pair.", self.kickoff())

    def test_photo_reader_rejects_other_origins_and_non_images(self):
        from unittest.mock import patch
        app = self.apps["dayform"]
        with patch("ruth.shopping.client.build_opener") as opener:
            for path in ("https://unrelated.example/shoe.png", "//unrelated.example/shoe.png",
                         "file:///etc/passwd", "http://user:pass@127.0.0.1/shoe.png"):
                with self.assertRaises(ShoppingError):
                    app.image(path)
            opener.assert_not_called()
        with self.assertRaises(ShoppingError):
            app.image("/")

    def test_ruth_command_dispatch_uses_telegram_session_for_app_turns(self):
        from unittest.mock import patch
        from ruth.app.core import RuthApplication
        from our_ark_provider_kit import BranchlessRepositoryFixture, IndependentReviewFixture
        from ruth.identity import load_identity
        from ruth.providers import ChatEvent
        from ruth.shopping.client import registry_path
        from ruth.state import atomic_write
        from tests.test_ruth_application import _Chat, _Runtime

        brain = self.brain
        class Chat(_Chat):
            name = "telegram"
            from types import SimpleNamespace
            config = SimpleNamespace(token="test-token")
            @property
            def allowed_conversation_id(self):
                return 42
        class Runtime(_Runtime):
            def respond(self, identity, message, execution=None, **kwargs):
                return brain(message, execution.session_key)

        atomic_write(registry_path(self.root), json.dumps({"apps": [app.__dict__ for app in self.apps.values()]}))
        chat = Chat()
        photos = []
        def send_photos(token, chat_id, images, caption):
            self.assertTrue(all("· Website" in text for _, text in chat.sent),
                            "albums replace Telegram recommendations; website turns are mirrored")
            photos.append((chat_id, images, caption))
            return {"message_ids": [len(photos) * 2, len(photos) * 2 + 1], "media_group_id": f"album-{len(photos)}"}
        with patch("ruth.app.core.ensure_long_term_memory"), patch("ruth.app.core.RuthApplication._maybe_start_lineage_worker"), \
                patch("ruth.shopping.photos.send_product_photos", side_effect=send_photos) as sender:
            bot = RuthApplication(load_identity(), self.root, chat, runtime=Runtime(),
                                  repository=BranchlessRepositoryFixture(), review=IndependentReviewFixture())
            bot.handle_event(ChatEvent(cursor="1", conversation_id=42, message_id="1", text="/shop work sneakers under $120, US 9"))
            self.assertIn("Two options", photos[-1][2])
            self.assertEqual(len(photos), 1)
            bot.handle_event(ChatEvent(cursor="1", conversation_id=42, message_id="1", text="/shop work sneakers under $120, US 9"))
            self.assertEqual(len(photos), 1, "duplicate events must not resend the album")
            self.message("dayform", "day-one")
            with bot._conversation_lock:
                self.assertEqual(bot._shopping_service().poll_once(42), [])
            bot.handle_event(ChatEvent(cursor="2", conversation_id=42, message_id="2", text="Comfort matters most."))
            self.assertEqual({key for key, _ in brain.calls}, {"telegram:42"})
            self.assertEqual(len(brain.calls), 3)
            self.assertEqual(len(chat.sent), 1, "website conversation is mirrored to Telegram")
            self.assertEqual(len(photos), 2, "each Telegram recommendation turn produces one album")
            self.assertEqual(len(self.transcript("dayform")["outputs"]), 1)
            sender.side_effect = ShoppingError("Unknown album delivery outcome")
            third = ChatEvent(cursor="3", conversation_id=42, message_id="3", text="Show them again.")
            bot.handle_event(third)
            self.assertEqual(len(chat.sent), 2, "failed album falls back to one full text recommendation")
            self.assertIn("Two options", chat.sent[-1][1])
            self.assertIn("#connect=browser-dayform", chat.sent[-1][1])
            bot.handle_event(third)
            self.assertEqual(sender.call_count, 3, "ambiguous uploads must not replay")
            self.assertEqual(len(chat.sent), 2)
            sender.side_effect = None
            sender.return_value = {"message_ids": [36], "media_group_id": None}
            self.message("dayform", "day-one-lite", "Please place a simulated order in US 9, up to $120 total.")
            with bot._conversation_lock:
                self.assertEqual(bot._shopping_service().poll_once(42), [])
            self.assertEqual(sender.call_count, 4)
            self.assertEqual(len(sender.call_args.args[2]), 1)
            self.assertIn("$85.80", sender.call_args.args[3])
            self.assertEqual(len(chat.sent), 3, "web order includes a complete mirrored conversation")
            bot.handle_event(ChatEvent(cursor="4", conversation_id=42, message_id="4", text="/shop shoes"))
            order_event = ChatEvent(cursor="5", conversation_id=42, message_id="5",
                                   text="Please place a simulated order for Day One Lite, US 9, up to $120 total.")
            bot.handle_event(order_event)
            self.assertEqual(sender.call_count, 6)
            self.assertIn("$85.80", sender.call_args.args[3])
            self.assertEqual(len(chat.sent), 3, "Telegram order photo replaces text reply")
            bot.handle_event(order_event)
            self.assertEqual(sender.call_count, 6, "acknowledged order photo must not repeat")

    def test_unavailable_runtime_has_bounded_attempts_and_no_purchase(self):
        self.kickoff()
        self.message("dayform", "day-one")
        calls = []
        def unavailable(*_args):
            calls.append(1)
            raise RuntimeError("offline")
        service = self.new_service()
        service.respond = unavailable
        for _ in range(3):
            self.assertTrue(service.poll_once(42))
        self.assertEqual(service.poll_once(42), [])
        self.assertEqual(len(calls), 3)
        self.assertIn("three attempts", self.transcript("dayform")["outputs"][0]["text"])
        with self.servers["dayform"].store.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM orders").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
