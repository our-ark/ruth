from email import policy
from email.parser import BytesParser
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from ruth.shopping.client import ShoppingError
from ruth.shopping.photos import product_caption, send_product_photo


class ShoppingPhotoTransportTests(unittest.TestCase):
    def test_photo_upload_is_multipart_bytes_with_plain_caption(self):
        image = b"\x89PNG\r\n\x1a\nexample-image"
        caption = "DAYFORM · Day One\n$107.80 total\nhttp://127.0.0.1:8011/?product=day-one#connect=demo"
        with patch("ruth.shopping.photos.build_opener") as factory:
            opener = factory.return_value
            opener.open.return_value.__enter__.return_value = BytesIO(json.dumps({
                "ok": True, "result": {"message_id": 31}}).encode())
            self.assertEqual(send_product_photo("test-token", 42, image, "image/png", caption), 31)
            req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.telegram.org/bottest-token/sendPhoto")
        message = BytesParser(policy=policy.default).parsebytes(
            ("Content-Type: " + req.get_header("Content-type") + "\r\n\r\n").encode() + req.data)
        parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
        self.assertEqual(parts["photo"].get_payload(decode=True), image)
        self.assertEqual(parts["photo"].get_content_type(), "image/png")
        self.assertEqual(parts["caption"].get_payload(decode=True).decode(), caption)
        self.assertEqual(parts["chat_id"].get_payload(decode=True), b"42")
        self.assertNotIn("parse_mode", parts)

    def test_upload_errors_do_not_disclose_token_or_trigger_a_retry(self):
        token = "123456789:secret-token-for-test"
        for error in (URLError("https://api.telegram.org/bot" + token),
                      HTTPError("https://api.telegram.org/bot" + token, 400, "Bad request", {}, None)):
            with patch("ruth.shopping.photos.build_opener") as factory:
                factory.return_value.open.side_effect = error
                with self.assertRaises(ShoppingError) as caught:
                    send_product_photo(token, 42, b"png", "image/png", "caption")
                self.assertNotIn(token, str(caught.exception))
                self.assertEqual(factory.return_value.open.call_count, 1)

    def test_long_caption_keeps_link_intact_or_falls_back_to_text_reply(self):
        card = {"app_name": "DAYFORM", "name": "Day One", "price_cents": 9800, "total_cents": 10780,
                "description": "x" * 2000, "link": "https://example.com/product#connect=complete"}
        self.assertIn(card["link"], product_caption(card))
        card["link"] = "https://example.com/product#connect=" + "x" * 2000
        caption = product_caption(card)
        self.assertLessEqual(len(caption.encode("utf-16-le")) // 2, 1024)
        self.assertNotIn("#connect=", caption)
        self.assertIn("link in my recommendation", caption)


if __name__ == "__main__":
    unittest.main()
