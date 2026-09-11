"""Telegram photo delivery for the shopping demo; no public image host needed.

Kept in Ruth because the shared chat contract currently supports text output only.
The caller owns authorization, epoch fencing and durable delivery receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from uuid import uuid4

from .client import NoRedirect, ShoppingError


@dataclass(frozen=True)
class PhotoDelivery:
    delivered: bool = False
    error: str = ""


def _units(text):
    return len(text.encode("utf-16-le")) // 2


def _clip(text, limit):
    if _units(text) <= limit:
        return text
    # Keep Unicode characters intact and count Telegram's UTF-16 entity offsets.
    return text.encode("utf-16-le")[:max(0, limit - 1) * 2].decode("utf-16-le", errors="ignore") + "…"


def recommendation_caption(cards, intro="", view_all_url=""):
    """One album caption; photo order matches numbered, linked product entries."""
    heading = f"{len(cards)} shopping option" + ("s" if len(cards) != 1 else "")
    html, visible = [], []
    for number, card in enumerate(cards, 1):
        title = f"{number}. {_clip(card['app_name'], 24)} · {_clip(card['name'], 40)}"
        price = f"${card['price_cents'] / 100:.2f} · ${card['total_cents'] / 100:.2f} total"
        label = f"Open option {number}"
        html.append(f'<b>{escape(title)}</b>\n{price}\n<a href="{escape(card["link"], quote=True)}">{label}</a>')
        visible.append(f"{title}\n{price}\n{label}")
    footer = "Totals include mock tax; shipping included."
    all_label = "View all options ↗"
    base = heading + "\n\n" + "\n\n".join(visible) + "\n\n" + footer
    if view_all_url:
        base += "\n\n" + all_label
    room = min(320, 1024 - _units(base) - 2)
    summary = _clip(intro.strip(), room) if intro and room > 1 else ""
    all_link = f'<a href="{escape(view_all_url, quote=True)}">{all_label}</a>\n\n' if view_all_url else ""
    return (f"<b>{heading}</b>\n\n" + all_link + (escape(summary) + "\n\n" if summary else "")
            + "\n\n".join(html) + "\n\n" + footer)


def order_caption(text):
    """Keep the authoritative receipt intact, with a bold confirmation heading."""
    if _units(text) > 1024:
        raise ShoppingError("Order receipt exceeds the photo caption limit")
    heading, _, details = text.partition("\n")
    return f"<b>{escape(heading)}</b>\n{escape(details)}"


def send_product_photos(token, chat_id, photos, caption):
    """One album upload (or one photo), with one shared HTML caption."""
    if not 1 <= len(photos) <= 6:
        raise ShoppingError("Expected 1–6 product photos")
    for content, mime in photos:
        if mime not in {"image/png", "image/jpeg"} or not content or len(content) > 8_000_000:
            raise ShoppingError("Unsupported product photo")
    multiple = len(photos) > 1
    method = "sendMediaGroup" if multiple else "sendPhoto"
    fields = {"chat_id": str(chat_id)}
    names = [f"product_{i}" for i in range(len(photos))] if multiple else ["photo"]
    if multiple:
        media = [{"type": "photo", "media": "attach://" + name} for name in names]
        # Only the first item has a caption, so the album has one shared description.
        media[0].update(caption=caption, parse_mode="HTML")
        fields["media"] = json.dumps(media)
    else:
        fields.update(caption=caption, parse_mode="HTML")
    boundary = "ruth-photo-" + uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")
    for name, (content, mime) in zip(names, photos):
        extension = "png" if mime == "image/png" else "jpg"
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                     f'filename="{name}.{extension}"\r\nContent-Type: {mime}\r\n\r\n').encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    request = Request(f"https://api.telegram.org/bot{token}/{method}", data=bytes(body),
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            result = json.loads(response.read(1_000_000))
    except HTTPError as error:
        raise ShoppingError(f"Telegram rejected the photo message (HTTP {error.code})") from None
    except (OSError, ValueError):
        raise ShoppingError("Telegram photo delivery could not be confirmed") from None
    payload = result.get("result") if isinstance(result, dict) else None
    messages = payload if multiple else [payload]
    if (not isinstance(result, dict) or not result.get("ok") or not isinstance(messages, list)
            or len(messages) != len(photos) or any(not isinstance(m, dict) or type(m.get("message_id")) is not int for m in messages)):
        raise ShoppingError("Telegram photo delivery could not be confirmed")
    groups = {m.get("media_group_id") for m in messages}
    if multiple and (len(groups) != 1 or not next(iter(groups))):
        raise ShoppingError("Telegram album delivery could not be confirmed")
    return {"message_ids": [m["message_id"] for m in messages],
            "media_group_id": messages[0].get("media_group_id")}
