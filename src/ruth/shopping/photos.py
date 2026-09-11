"""Telegram photo delivery for the shopping demo; no public image host needed.

Kept in Ruth because the shared chat contract currently supports text output only.
The caller owns authorization, epoch fencing and durable delivery receipts.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from uuid import uuid4

from .client import NoRedirect, ShoppingError


def product_caption(card):
    title = f"{card['app_name'][:80]} · {card['name'][:120]}"
    price = f"${card['price_cents'] / 100:.2f} · ${card['total_cents'] / 100:.2f} total (mock tax included)"
    description = str(card.get("description", ""))[:180]
    caption = f"{title}\n{price}\n{description}\n\nOpen product:\n{card['link']}"
    # Do not truncate an account-connection link; the full link is also in the text reply.
    if len(caption.encode("utf-16-le")) // 2 > 1024:
        caption = f"{title}\n{price}\nOpen the product using the link in my recommendation."
    return caption


def send_product_photo(token, chat_id, content, mime, caption):
    """Upload bytes with sendPhoto. Never expose token-bearing request errors."""
    if mime not in {"image/png", "image/jpeg"} or not content or len(content) > 8_000_000:
        raise ShoppingError("Unsupported product photo")
    boundary = "ruth-photo-" + uuid4().hex
    body = bytearray()
    for name, value in (("chat_id", str(chat_id)), ("caption", caption), ("disable_notification", "true")):
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")
    extension = "png" if mime == "image/png" else "jpg"
    body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; '
                 f'filename="product.{extension}"\r\nContent-Type: {mime}\r\n\r\n').encode())
    body.extend(content)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = Request(f"https://api.telegram.org/bot{token}/sendPhoto", data=bytes(body),
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            result = json.loads(response.read(1_000_000))
    except HTTPError as error:
        raise ShoppingError(f"Telegram rejected the product photo (HTTP {error.code})") from None
    except (OSError, ValueError):
        raise ShoppingError("Telegram photo delivery could not be confirmed") from None
    message = result.get("result") if isinstance(result, dict) else None
    message_id = message.get("message_id") if isinstance(message, dict) else None
    if not isinstance(result, dict) or not result.get("ok") or type(message_id) is not int:
        raise ShoppingError("Telegram photo delivery could not be confirmed")
    return message_id
