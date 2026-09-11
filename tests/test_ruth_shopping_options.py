from base64 import urlsafe_b64decode
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ruth.shopping.client import AppConnection, registry_path
from ruth.shopping.options import OptionsServer, options_link
from ruth.shopping.photos import recommendation_caption
from ruth.state import atomic_write


class ShoppingOptionsTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.app = AppConnection("dayform", "DAYFORM", "http://127.0.0.1:8011", "private-agent-token", "browser-only-token")
        self.server = OptionsServer(("127.0.0.1", 0), [self.app.base_url])
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        atomic_write(registry_path(self.root), json.dumps({"options_url": self.server.origin, "apps": [self.app.__dict__]}))
        self.card = {"app_id": "dayform", "app_name": "DAYFORM", "name": "Day One", "price_cents": 9800,
                     "total_cents": 10780, "image": "/shoe.png", "link": self.app.link("day-one")}

    def test_shortlist_keeps_connected_links_in_fragment_and_out_of_server_responses(self):
        link = options_link(self.root, [self.card], {"dayform": self.app})
        self.assertTrue(link.startswith(self.server.origin + "/#options="))
        encoded = link.split("#options=")[1]
        payload = json.loads(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        self.assertEqual(payload["options"][0]["url"], self.app.link("day-one"))
        self.assertEqual(payload["options"][0]["image"], self.app.base_url + "/shoe.png")
        self.assertNotIn(self.app.token, json.dumps(payload))
        with urlopen(link, timeout=3) as response:
            html = response.read().decode()
            self.assertIn("All your options.", html)
            self.assertNotIn(self.app.connect_token, html)
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        with urlopen(self.server.origin + "/config.json", timeout=3) as response:
            self.assertEqual(json.load(response), {"origins": [self.app.base_url]})
        caption = recommendation_caption([self.card], "Compare these.", link)
        self.assertIn("View all options", caption)
        self.assertIn(link, caption)

    def test_launcher_is_read_only_and_does_not_expose_agent_state(self):
        for path, expected in (("/.ruth/config.yaml", 404), ("/collaboration/events", 404)):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.server.origin + path, timeout=3)
            self.assertEqual(caught.exception.code, expected)
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.server.origin, data=b"{}"), timeout=3)
        self.assertEqual(caught.exception.code, 405)
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.server.origin, headers={"Host": "unrelated.example"}), timeout=3)
        self.assertEqual(caught.exception.code, 403)

    def test_unconfigured_launcher_does_not_create_a_broken_link(self):
        registry_path(self.root).unlink()
        self.assertEqual(options_link(self.root, [self.card], {"dayform": self.app}), "")
