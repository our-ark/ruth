"""Render the shopping design as PNG previews and editable, standalone SVGs.

Run with Python 3 and Pillow: python docs/diagrams/render_shopping_demo.py
Fonts: Arial on macOS, DejaVu Sans on Linux, or set RUTH_DIAGRAM_FONT_DIR to
a directory containing Arial.ttf and Arial Bold.ttf. No remote renderer is used.
"""

from html import escape
from pathlib import Path
import math
import os

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parent
SCALE = 2
INK = "#172b42"
MUTED = "#536478"
LINE = "#8799ac"
BLUE = "#2563b5"
GREEN = "#287554"
PURPLE = "#7151a3"


def font_path(bold=False):
    candidates = []
    if os.environ.get("RUTH_DIAGRAM_FONT_DIR"):
        candidates.append(Path(os.environ["RUTH_DIAGRAM_FONT_DIR"]) /
                          ("Arial Bold.ttf" if bold else "Arial.ttf"))
    candidates.extend([
        Path("/System/Library/Fonts/Supplemental") /
        ("Arial Bold.ttf" if bold else "Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") /
        ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ])
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Set RUTH_DIAGRAM_FONT_DIR to the diagram font directory")


class Canvas:
    def __init__(self, height, title, subtitle):
        self.height = height
        self.image = Image.new("RGB", (760 * SCALE, height * SCALE), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" '
            f'viewBox="0 0 760 {height}" role="img">',
            f'<title>{escape(title)}</title><desc>{escape(subtitle)}</desc>',
            f'<rect width="760" height="{height}" fill="white"/>',
        ]
        self.text(32, 43, title, 27, bold=True)
        self.text(32, 74, subtitle, 17, fill=MUTED)

    def text(self, x, baseline, text, size=17, bold=False, fill=INK, anchor="start"):
        font = ImageFont.truetype(font_path(bold), size * SCALE)
        pil_anchor = {"start": "ls", "middle": "ms", "end": "rs"}[anchor]
        bounds = self.draw.textbbox((x * SCALE, baseline * SCALE), text,
                                    font=font, anchor=pil_anchor)
        if not (0 <= bounds[0] and bounds[2] <= 760 * SCALE and
                0 <= bounds[1] and bounds[3] <= self.height * SCALE):
            raise ValueError(f"Text outside canvas: {text}")
        self.draw.text((x * SCALE, baseline * SCALE), text, fill=fill,
                       font=font, anchor=pil_anchor)
        self.svg.append(
            f'<text x="{x}" y="{baseline}" font-family="Arial, DejaVu Sans, sans-serif" '
            f'font-size="{size}" font-weight="{700 if bold else 400}" '
            f'text-anchor="{anchor}" fill="{fill}">{escape(text)}</text>'
        )

    def box(self, x, y, w, h, fill="#f7f9fc", stroke="#cbd5e1", radius=12):
        self.draw.rounded_rectangle(
            (x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE),
            radius=radius * SCALE, fill=fill, outline=stroke, width=SCALE,
        )
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                        f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def line(self, points, fill=LINE, width=2, arrow=False, dashed=False):
        if dashed:
            (x1, y1), (x2, y2) = points
            distance = math.hypot(x2 - x1, y2 - y1)
            for offset in range(0, math.ceil(distance), 10):
                a, b = offset / distance, min(offset + 5, distance) / distance
                segment = [(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
                           for t in (a, b)]
                self.draw.line([(x * SCALE, y * SCALE) for x, y in segment],
                               fill=fill, width=width * SCALE)
        else:
            self.draw.line([(x * SCALE, y * SCALE) for x, y in points],
                           fill=fill, width=width * SCALE)
        xy = " ".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="5 5"' if dashed else ""
        self.svg.append(f'<polyline points="{xy}" fill="none" stroke="{fill}" '
                        f'stroke-width="{width}"{dash}/>')
        if arrow:
            x, y = points[-1]
            px, py = points[-2]
            angle = math.atan2(y - py, x - px)
            head = [(x, y)] + [
                (x - 10 * math.cos(angle + d), y - 10 * math.sin(angle + d))
                for d in (-0.45, 0.45)
            ]
            self.draw.polygon([(a * SCALE, b * SCALE) for a, b in head], fill=fill)
            self.svg.append('<polygon points="' + " ".join(f"{a},{b}" for a, b in head)
                            + f'" fill="{fill}"/>')

    def participant(self, x, name, bottom, color=BLUE):
        self.line([(x, 139), (x, bottom)], dashed=True, width=1)
        self.box(x - 78, 99, 156, 42, fill="#f3f6fb", stroke=color, radius=8)
        self.text(x, 126, name, 18, bold=True, fill=color, anchor="middle")

    def message(self, start, end, y, label, dashed=False):
        self.text((start + end) / 2, y - 11, label, 16, anchor="middle")
        self.line([(start, y), (end, y)], fill=BLUE, arrow=True, dashed=dashed)

    def note(self, x, y, lines, w=174):
        self.box(x - w / 2, y, w, 18 + len(lines) * 21, fill="#eef4fd",
                 stroke="#c6d7f1", radius=6)
        for i, line in enumerate(lines):
            self.text(x, y + 24 + i * 21, line, 16, anchor="middle")

    def save(self, name):
        self.image.save(OUT / f"{name}.png", optimize=True)
        (OUT / f"{name}.svg").write_text("\n".join(self.svg + ["</svg>"]) + "\n")
        print(f"Rendered {name}: 760 x {self.height} (PNG at 2x)")


def architecture():
    c = Canvas(920, "Ruth shopping demo", "One agent. One conversation. Two apps.")
    c.box(160, 102, 440, 96, fill="#f0f6fd", stroke="#9dbde7")
    c.text(380, 130, "Telegram", 23, bold=True, fill=BLUE, anchor="middle")
    c.text(380, 156, "/shop + follow-up messages", 18, anchor="middle")
    c.text(380, 181, "Recommendations + order notifications", 17, anchor="middle")
    c.line([(368, 198), (368, 250)], fill=BLUE, arrow=True)
    c.line([(392, 250), (392, 198)], fill=BLUE, arrow=True)

    c.box(40, 252, 680, 286, fill="#f6f9ff", stroke=BLUE, radius=16)
    c.text(380, 290, "Ruth", 27, bold=True, fill=BLUE, anchor="middle")
    c.text(380, 320, "One continuing conversation + memory", 21, anchor="middle")
    for x, title, body in [(60, "/shop command", "Start the shopping task"),
                           (400, "Static app registry", "App A + App B connections")]:
        c.box(x, 340, 300, 74, fill="white", stroke="#cedaf0")
        c.text(x + 150, 369, title, 20, bold=True, anchor="middle")
        c.text(x + 150, 396, body, 17, anchor="middle")
    c.box(60, 430, 640, 86, fill="white", stroke="#cedaf0")
    c.text(380, 462, "Message polling · Reply routing · Shopping tools", 20,
           bold=True, anchor="middle")
    c.text(380, 491, "Reply to the message's source app session", 18, anchor="middle")

    c.line([(380, 538), (380, 593)])
    c.text(400, 570, "Ruth initiates all API calls", 17, fill=MUTED)
    c.line([(204, 593), (556, 593)])
    for x, color, name, ui in [(40, GREEN, "App A", "Storefront + chat UI A"),
                                (392, PURPLE, "App B", "Storefront + chat UI B")]:
        c.line([(x + 164, 593), (x + 164, 625)], fill=color, arrow=True)
        c.box(x, 626, 328, 235, fill="#fafcfe", stroke=color)
        c.text(x + 164, 657, name, 23, bold=True, fill=color, anchor="middle")
        c.text(x + 164, 684, ui, 18, anchor="middle")
        c.line([(x + 20, 703), (x + 308, 703)], fill="#dce3ea", width=1)
        c.text(x + 164, 730, "Two collaboration endpoints", 17, bold=True, anchor="middle")
        c.text(x + 164, 757, "GET events · POST outputs", 18, anchor="middle")
        c.text(x + 164, 792, "Three shopping operations", 17, bold=True, anchor="middle")
        c.text(x + 164, 819, "queryProduct · getProduct", 18, anchor="middle")
        c.text(x + 164, 844, "orderProduct", 18, anchor="middle")
    c.text(380, 895, "Message-time context · No dynamic app tracking", 18,
           fill=MUTED, anchor="middle")
    c.save("shopping-architecture")


def kickoff():
    c = Canvas(500, "1 · Start shopping", "Ask in Telegram; get recommendations from both apps.")
    for x, name in [(90, "Telegram"), (365, "Ruth"), (660, "Apps A + B")]:
        c.participant(x, name, 450)
    c.message(90, 365, 176, "/shop shoes under $80")
    c.note(365, 202, ["Load app registry", "Start polling"])
    c.message(365, 660, 307, "queryProduct / getProduct")
    c.message(660, 365, 363, "Products + canonical links", dashed=True)
    c.message(365, 90, 430, "Recommendations + links")
    c.text(380, 482, "Both app accounts are connected before the demo.", 17,
           fill=MUTED, anchor="middle")
    c.save("shopping-kickoff")


def conversation():
    c = Canvas(626, "2 · Continue in either app", "The same message and context exchange works in App A and App B.")
    for x, name in [(90, "App chat UI"), (365, "App backend"), (660, "Ruth")]:
        c.participant(x, name, 580)
    c.message(90, 365, 181, "Message + page context")
    c.note(365, 207, ["Queue event"])
    c.message(660, 365, 295, "GET events")
    c.message(365, 660, 354, "Message + context snapshot", dashed=True)
    c.note(650, 387, ["Use the same", "conversation"], w=166)
    c.message(660, 365, 499, "POST reply + selected context")
    c.message(365, 90, 558, "Show Ruth's reply")
    c.text(380, 609, "Reply to the source session, even if the user switches tabs.", 17,
           fill=MUTED, anchor="middle")
    c.save("shopping-conversation")


def order():
    c = Canvas(663, "3 · Order and notify", "An authorized purchase request uses the selected app's order API.")
    for x, name in [(90, "Telegram"), (365, "Ruth"), (660, "Selected app")]:
        c.participant(x, name, 610)
    c.message(660, 365, 181, "Order request + selection", dashed=True)
    c.message(365, 660, 237, "getProduct")
    c.message(660, 365, 293, "Current price + availability", dashed=True)
    c.message(365, 660, 349, "orderProduct (simulated)")
    c.message(660, 365, 405, "Order ID + status", dashed=True)
    c.message(365, 660, 461, "POST order result")
    c.message(365, 90, 517, "Order notification")
    c.note(365, 550, ["Stop app polling"], w=200)
    c.text(380, 643, "Conversation and memory persist after the task.", 17,
           fill=MUTED, anchor="middle")
    c.save("shopping-order")


if __name__ == "__main__":
    architecture()
    kickoff()
    conversation()
    order()
