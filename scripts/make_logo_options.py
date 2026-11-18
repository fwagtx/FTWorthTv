"""Three logo directions for Fort Worth Texas TV as clean vector SVG (rendered to PNG by scripts/render_svg.js).

  A  "Longhorn TV"   a TV whose antennae are longhorn horns, FTW on screen        -> Fort Worth, where the West begins
  B  "Sunset skyline" a TV showing the Fort Worth skyline against a sunset         -> the Dallas page's idea, done better
  C  "Badge"          a round seal: FORT WORTH TEXAS TV around a TV with a lone star -> works as a stamp / watermark

Each comes in three colourways (light = navy on transparent, dark = white + gold, mono = black) and two shapes
(with the caption under the TV, and mark-only for small avatars). Output: assets/brand/logo-options/*.svg + *.png
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand" / "logo-options"

NAVY, GOLD, PAPER, INK, ORANGE, SKY = "#14182B", "#F2B134", "#FFFFFF", "#0F1419", "#E8743B", "#2B3A7A"
FONT = "Inter Display, Inter, Liberation Sans, Arial, sans-serif"

# colourways: body (TV), screen fill, text/skyline on screen, accent, caption colour
WAYS = {
    "light": dict(body=NAVY, screen=PAPER, fg=NAVY, accent=GOLD, caption=NAVY),
    "dark": dict(body=PAPER, screen=NAVY, fg=PAPER, accent=GOLD, caption=PAPER),
    "mono": dict(body=INK, screen=PAPER, fg=INK, accent=INK, caption=INK),
}

SKYLINE = [  # stylised Fort Worth: (x, w, h, style) fractions of the screen box
    (0.03, 0.08, 0.30, "box"), (0.13, 0.07, 0.46, "step"), (0.22, 0.10, 0.34, "box"), (0.34, 0.08, 0.64, "crown"),
    (0.44, 0.11, 0.50, "step"), (0.57, 0.06, 0.40, "box"), (0.65, 0.07, 0.74, "spire"), (0.74, 0.09, 0.36, "box"),
    (0.85, 0.05, 0.56, "dome"), (0.92, 0.05, 0.24, "box"),
]


def skyline_svg(x0: float, y0: float, w: float, h: float, fill: str) -> str:
    base = y0 + h
    parts = []
    for x, bw, bh, style in SKYLINE:
        bx0, bx1, top = x0 + w * x, x0 + w * (x + bw), base - h * bh
        if style == "step":
            parts.append(f'<rect x="{bx0:.1f}" y="{top + h * 0.08:.1f}" width="{bx1 - bx0:.1f}" height="{base - top - h * 0.08:.1f}" fill="{fill}"/>')
            parts.append(f'<rect x="{bx0 + (bx1 - bx0) * 0.25:.1f}" y="{top:.1f}" width="{(bx1 - bx0) * 0.5:.1f}" height="{base - top:.1f}" fill="{fill}"/>')
        elif style in ("crown", "spire"):
            k = 0.07 if style == "crown" else 0.12
            parts.append(f'<rect x="{bx0:.1f}" y="{top + h * k:.1f}" width="{bx1 - bx0:.1f}" height="{base - top - h * k:.1f}" fill="{fill}"/>')
            parts.append(f'<polygon points="{bx0:.1f},{top + h * k:.1f} {bx1:.1f},{top + h * k:.1f} {(bx0 + bx1) / 2:.1f},{top:.1f}" fill="{fill}"/>')
            if style == "spire":
                parts.append(f'<rect x="{(bx0 + bx1) / 2 - w * 0.006:.1f}" y="{top - h * 0.09:.1f}" width="{w * 0.012:.1f}" height="{h * 0.1:.1f}" fill="{fill}"/>')
        elif style == "dome":
            parts.append(f'<rect x="{bx0:.1f}" y="{top + h * 0.1:.1f}" width="{bx1 - bx0:.1f}" height="{base - top - h * 0.1:.1f}" fill="{fill}"/>')
            parts.append(f'<ellipse cx="{(bx0 + bx1) / 2:.1f}" cy="{top + h * 0.1:.1f}" rx="{(bx1 - bx0) / 2:.1f}" ry="{h * 0.1:.1f}" fill="{fill}"/>')
        else:
            parts.append(f'<rect x="{bx0:.1f}" y="{top:.1f}" width="{bx1 - bx0:.1f}" height="{base - top:.1f}" fill="{fill}"/>')
    return "".join(parts)


def tv_body(x: float, y: float, w: float, h: float, body: str, screen: str, r: float = 64, inset: float = 34) -> str:
    """Rounded TV cabinet with an inset screen and two feet."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{body}"/>'
            f'<rect x="{x + inset}" y="{y + inset}" width="{w - 2 * inset}" height="{h - 2 * inset}" rx="{r * 0.6}" fill="{screen}"/>'
            f'<rect x="{x + w * 0.2}" y="{y + h - 2}" width="{w * 0.1}" height="{h * 0.07}" fill="{body}"/>'
            f'<rect x="{x + w * 0.7}" y="{y + h - 2}" width="{w * 0.1}" height="{h * 0.07}" fill="{body}"/>')


def caption(y: float, text: str, color: str, size: int = 118, spacing: int = 6) -> str:
    return (f'<text x="500" y="{y}" text-anchor="middle" font-family="{FONT}" font-weight="900" font-size="{size}" '
            f'letter-spacing="{spacing}" fill="{color}">{text}</text>')


def option_a(c: dict, with_caption: bool) -> str:
    """Longhorn TV: the horns are the antennae."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    ty = 300 if with_caption else 250
    th = 470 if with_caption else 520
    # a longhorn horn: thick at the head, sweeping out sideways, tip turned up (mirrored for the right side)
    horn = ('<path d="M 500 {b0} C 400 {b1}, 290 {b2}, 190 {b3} C 120 {b4}, 70 {b5}, 60 {b6} '
            'C 95 {b7}, 150 {b8}, 215 {b9} C 300 {b10}, 400 {b11}, 500 {b12} Z"/>'
            .format(b0=ty - 10, b1=ty - 60, b2=ty - 50, b3=ty - 95, b4=ty - 130, b5=ty - 200, b6=ty - 300,
                    b7=ty - 205, b8=ty - 120, b9=ty - 40, b10=ty + 10, b11=ty + 40, b12=ty + 50))
    horns = f'<g fill="{body}">{horn}<g transform="translate(1000,0) scale(-1,1)">{horn}</g></g>'
    # the horn mount: a small rounded cap on the cabinet top
    mount = f'<rect x="440" y="{ty - 48}" width="120" height="70" rx="22" fill="{body}"/>'
    text = (f'<text x="500" y="{ty + th * 0.62}" text-anchor="middle" font-family="{FONT}" font-weight="900" '
            f'font-size="{th * 0.50:.0f}" letter-spacing="-6" fill="{fg}">FTW</text>')
    star = f'<polygon points="{star_points(500, ty + th * 0.80, 22)}" fill="{accent}"/>'
    svg = tv_body(140, ty, 720, th, body, screen) + text + star + mount + horns
    if with_caption:
        svg += caption(945, "TEXAS TV", cap, size=108, spacing=10)
    return wrap(svg)


def option_b(c: dict, with_caption: bool) -> str:
    """Sunset skyline TV."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    ty = 250 if with_caption else 200
    th = 500 if with_caption else 600
    mono = c["body"] == INK
    grad = ('<defs><linearGradient id="sun" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{SKY}"/><stop offset="0.55" stop-color="{GOLD}"/><stop offset="1" stop-color="{ORANGE}"/>'
            '</linearGradient></defs>')
    screen_fill = screen if mono else "url(#sun)"
    sx, sy, sw, sh = 140 + 34, ty + 34, 720 - 68, th - 68
    sun = "" if mono else f'<circle cx="{sx + sw * 0.72:.0f}" cy="{sy + sh * 0.46:.0f}" r="{sh * 0.16:.0f}" fill="{PAPER}" opacity="0.85"/>'
    city = skyline_svg(sx + 36, sy + sh * 0.18, sw - 72, sh * 0.70, body if not mono else INK)
    ground = f'<rect x="{sx + 24}" y="{sy + sh * 0.88:.0f}" width="{sw - 48}" height="{sh * 0.03:.0f}" fill="{accent if mono else body}"/>'
    ant = (f'<g stroke="{body}" stroke-width="30" stroke-linecap="round" fill="none">'
           f'<path d="M 500 {ty} L 380 {ty - 150}"/><path d="M 500 {ty} L 620 {ty - 150}"/></g>'
           f'<circle cx="500" cy="{ty}" r="30" fill="{body}"/>')
    svg = grad + f'<rect x="140" y="{ty}" width="720" height="{th}" rx="64" fill="{body}"/>' \
        + f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="38" fill="{screen_fill}"/>' + sun + city + ground \
        + f'<rect x="284" y="{ty + th - 2}" width="72" height="34" fill="{body}"/><rect x="644" y="{ty + th - 2}" width="72" height="34" fill="{body}"/>' + ant
    if with_caption:
        svg += caption(930, "FTWTV", cap, size=150, spacing=-2)
    return wrap(svg)


def option_c(c: dict, with_caption: bool) -> str:
    """Round seal: FORT WORTH · TEXAS TV around a TV with the lone star."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    ring_fill = body
    inner = screen
    svg = (f'<circle cx="500" cy="500" r="490" fill="{ring_fill}"/>'
           f'<circle cx="500" cy="500" r="370" fill="{inner}"/>'
           f'<circle cx="500" cy="500" r="395" fill="none" stroke="{accent}" stroke-width="8"/>'
           '<defs><path id="rim" d="M 500 500 m 0 -440 a 440 440 0 1 1 0 880 a 440 440 0 1 1 0 -880"/></defs>'
           f'<text font-family="{FONT}" font-weight="800" font-size="78" letter-spacing="14" fill="{screen if body != PAPER else NAVY}" '
           f'textLength="2764" lengthAdjust="spacing"><textPath href="#rim" startOffset="0" textLength="2764" lengthAdjust="spacing">'
           'FORT WORTH  ★  TEXAS TV  ★  FORT WORTH  ★  TEXAS TV  ★  </textPath></text>')
    # small TV in the centre with a star on screen
    tx, ty, tw, th = 300, 330, 400, 300
    svg += (f'<g stroke="{fg}" stroke-width="22" stroke-linecap="round" fill="none"><path d="M 500 {ty} L 430 {ty - 90}"/><path d="M 500 {ty} L 570 {ty - 90}"/></g>'
            f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="44" fill="{fg}"/>'
            f'<rect x="{tx + 26}" y="{ty + 26}" width="{tw - 52}" height="{th - 52}" rx="26" fill="{inner}"/>'
            f'<polygon points="{star_points(500, ty + th / 2 + 6, 92)}" fill="{accent}"/>'
            f'<rect x="{tx + 70}" y="{ty + th - 2}" width="50" height="26" fill="{fg}"/><rect x="{tx + tw - 120}" y="{ty + th - 2}" width="50" height="26" fill="{fg}"/>')
    if with_caption:
        svg += (f'<text x="500" y="760" text-anchor="middle" font-family="{FONT}" font-weight="900" font-size="96" letter-spacing="2" fill="{fg}">FTWTV</text>')
    return wrap(svg)


def star_points(cx: float, cy: float, r: float) -> str:
    import math
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + rr * math.cos(ang):.1f},{cy + rr * math.sin(ang):.1f}")
    return " ".join(pts)


def wrap(inner: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1000" height="1000">{inner}</svg>'


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for key, fn in (("a-longhorn", option_a), ("b-sunset", option_b), ("c-badge", option_c)):
        for way, colors in WAYS.items():
            for shape, with_cap in (("full", True), ("mark", False)):
                p = OUT / f"{key}-{way}-{shape}.svg"
                p.write_text(fn(colors, with_cap), encoding="utf-8")
                files.append(str(p))
    for size in (1024, 128):
        subprocess.run(["node", str(ROOT / "scripts" / "render_svg.js"), str(size), str(OUT), *files], check=True, stdout=subprocess.DEVNULL)
    print("rendered", len(files), "svgs at 1024 and 128 px into", OUT)
    contact_sheet()


def contact_sheet() -> None:
    """Side by side: light, dark, mono, and the mark as a 200/96/48/32 px avatar."""
    from PIL import Image, ImageDraw, ImageFont
    NAVY, PAPER = (20, 24, 43), (255, 255, 255)
    f = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "LiberationSans-Bold.ttf"), 30)
    rows = [("a-longhorn", "A  Longhorn TV"), ("b-sunset", "B  Sunset skyline"), ("c-badge", "C  Badge")]
    tile = 420
    sheet = Image.new("RGB", (4 * (tile + 20) + 20, len(rows) * (tile + 70) + 20), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    for r, (key, label) in enumerate(rows):
        y = 20 + r * (tile + 70)
        for c, (name, bg) in enumerate([(f"{key}-light-full-1024.png", PAPER), (f"{key}-dark-full-1024.png", NAVY), (f"{key}-mono-mark-1024.png", PAPER)]):
            x = 20 + c * (tile + 20)
            im = Image.open(OUT / name).convert("RGBA").resize((tile, tile), Image.LANCZOS)
            cell = Image.new("RGBA", (tile, tile), bg + (255,)); cell.alpha_composite(im)
            sheet.paste(cell.convert("RGB"), (x, y))
        x = 20 + 3 * (tile + 20)
        cell = Image.new("RGB", (tile, tile), (240, 242, 245)); cd = ImageDraw.Draw(cell)
        for size, pos in ((200, (30, 30)), (96, (260, 60)), (48, (260, 190)), (32, (330, 190))):
            mark = Image.open(OUT / f"{key}-light-mark-1024.png").convert("RGBA").resize((int(size * 0.82), int(size * 0.82)), Image.LANCZOS)
            cd.ellipse([pos[0], pos[1], pos[0] + size, pos[1] + size], fill=PAPER, outline=(200, 205, 212))
            off = (size - mark.width) // 2
            cell.paste(mark, (pos[0] + off, pos[1] + off), mark)
        cd.text((30, 300), "as an avatar: 200 / 96 / 48 / 32 px", font=f, fill=(90, 90, 90))
        sheet.paste(cell, (x, y))
        d.text((20, y + tile + 18), label, font=f, fill=(30, 30, 30))
    sheet.save(OUT / "options-sheet.jpg", quality=90)


if __name__ == "__main__":
    main()
