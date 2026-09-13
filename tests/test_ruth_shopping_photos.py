from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from ruth.shopping.client import ShoppingError
from ruth.shopping.photos import order_caption, recommendation_caption, send_product_photos


class ShoppingPhotoTransportTests(unittest.TestCase):
    def test_order_caption_preserves_receipt_and_escapes_product_markup(self):
        text = "Simulated order confirmed: DAYFORM-123\nDay <One> & Ink · US 9\n$85.80 total. No payment was taken."
        caption = order_caption(text)
        self.assertIn("<b>Simulated order confirmed: DAYFORM-123</b>", caption)
        self.assertIn("Day &lt;One&gt; &amp; Ink · US 9", caption)
        self.assertIn("$85.80 total. No payment was taken.", caption)
        with self.assertRaises(ShoppingError):
            order_caption(text + "😀" * 600)

    def upload(self, photos, result):
        caption = '<b>Options</b>\nhttp://127.0.0.1:8011/?product=day-one#connect=demo'
        with patch("ruth.shopping.photos.build_opener") as factory:
            opener = factory.return_value
            opener.open.return_value.__enter__.return_value = BytesIO(json.dumps({"ok": True, "result": result}).encode())
            receipt = send_product_photos("test-token", 42, photos, caption)
            req = opener.open.call_args.args[0]
            self.assertEqual(opener.open.call_count, 1)
        message = BytesParser(policy=policy.default).parsebytes(
            ("Content-Type: " + req.get_header("Content-type") + "\r\n\r\n").encode() + req.data)
        parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
        self.assertEqual(parts["chat_id"].get_payload(decode=True), b"42")
        return req, parts, receipt, caption

    def test_three_photos_use_one_album_and_one_shared_caption(self):
        photos = [(b"png-one", "image/png"), (b"jpeg-two", "image/jpeg"), (b"png-three", "image/png")]
        req, parts, receipt, caption = self.upload(photos, [
            {"message_id": i, "media_group_id": "one-album"} for i in (31, 32, 33)])
        self.assertTrue(req.full_url.endswith("/sendMediaGroup"))
        self.assertEqual(receipt, {"message_ids": [31, 32, 33], "media_group_id": "one-album"})
        media = json.loads(parts["media"].get_payload(decode=True))
        self.assertEqual(len(media), 3)
        self.assertEqual(media[0]["caption"], caption)
        self.assertEqual(media[0]["parse_mode"], "HTML")
        self.assertTrue(all("caption" not in m for m in media[1:]))
        for item, (content, mime) in zip(media, photos):
            attachment = parts[item["media"].removeprefix("attach://")]
            self.assertEqual(attachment.get_payload(decode=True), content)
            self.assertEqual(attachment.get_content_type(), mime)

    def test_one_product_uses_one_photo_with_caption(self):
        req, parts, receipt, caption = self.upload([(b"png", "image/png")], {"message_id": 31})
        self.assertTrue(req.full_url.endswith("/sendPhoto"))
        self.assertEqual(receipt["message_ids"], [31])
        self.assertEqual(parts["photo"].get_payload(decode=True), b"png")
        self.assertEqual(parts["caption"].get_payload(decode=True).decode(), caption)
        self.assertNotIn("media", parts)

    def test_upload_errors_do_not_disclose_token_or_trigger_a_retry(self):
        # Construct the synthetic credential so the repository's literal-token
        # check can remain strict without exempting test files.
        token = "123456789" + ":" + "secret-token-for-test"
        for error in (URLError("https://api.telegram.org/bot" + token),
                      HTTPError("https://api.telegram.org/bot" + token, 400, "Bad request", {}, None)):
            with patch("ruth.shopping.photos.build_opener") as factory:
                factory.return_value.open.side_effect = error
                with self.assertRaises(ShoppingError) as caught:
                    send_product_photos(token, 42, [(b"png", "image/png")] * 3, "caption")
                self.assertNotIn(token, str(caught.exception))
                self.assertEqual(factory.return_value.open.call_count, 1)

    def test_partial_or_ungrouped_response_is_not_confirmed_as_an_album(self):
        for messages in ([{"message_id": 1, "media_group_id": "group"}],
                         [{"message_id": 1}, {"message_id": 2}],
                         [{"message_id": 1, "media_group_id": "a"}, {"message_id": 2, "media_group_id": "b"}]):
            with self.assertRaises(ShoppingError):
                self.upload([(b"png", "image/png")] * 2, messages)

    def test_caption_numbers_all_products_preserves_links_and_fits_telegram(self):
        class Caption(HTMLParser):
            def __init__(self):
                super().__init__()
                self.visible, self.links = [], []
            def handle_data(self, data):
                self.visible.append(data)
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.links.append(dict(attrs)["href"])
        cards = [{"app_name": "Store <&> " + "😀" * 50, "name": "Shoe " + "😀" * 80,
                  "price_cents": 9800, "total_cents": 10780,
                  "link": f"https://example.com/?product={i}&color=ink#connect=" + "x" * 43}
                 for i in range(3)]
        parsed = Caption()
        parsed.feed(recommendation_caption(cards, "My preferred option is the first. " * 100))
        self.assertEqual(parsed.links, [], "URLs must be visible text, not hidden hyperlink entities")
        visible = "".join(parsed.visible)
        self.assertLessEqual(len(visible.encode("utf-16-le")) // 2, 1024)
        for number, card in enumerate(cards, 1):
            self.assertIn(card["link"], visible, "preserve the full URL including account connection fragment")
            self.assertIn(f"{number}. Store <&>", visible)
        self.assertNotIn("Open option", visible)
        self.assertIn("$107.80 total", visible)

    def test_oversized_visible_urls_use_text_fallback_without_truncating_links(self):
        card = {"app_name": "Store", "name": "Shoe", "price_cents": 7800,
                "total_cents": 8580, "link": "https://example.com/#connect=" + "x" * 2000}
        with self.assertRaisesRegex(ShoppingError, "caption limit"):
            recommendation_caption([card])


if __name__ == "__main__":
    unittest.main()
