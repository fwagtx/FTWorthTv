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


# ---------------------------------------------------------------------------------------------- Fort Worth, specifically
def fort_worth_skyline(x0: float, y0: float, w: float, h: float, fill: str) -> str:
    """The downtown Fort Worth silhouette as locals know it, left to right from the Trinity side: the Tarrant County
    Courthouse clock tower, Carter Burgess Plaza's setbacks, The Tower's pyramid crown and spire, Burnett Plaza's notched
    top (the tallest), D.R. Horton Tower's chamfered crown, the two City Center towers, Wells Fargo Tower's steps and the
    Frost Tower's slanted roof, with low blocks between them."""
    base = y0 + h
    out = []
    def rect(x, wd, ht, dy=0.0):
        out.append(f'<rect x="{x0 + w * x:.1f}" y="{base - h * ht - h * dy:.1f}" width="{w * wd:.1f}" height="{h * ht:.1f}" fill="{fill}"/>')
    def poly(pts):
        out.append('<polygon points="' + " ".join(f"{x0 + w * px:.1f},{base - h * py:.1f}" for px, py in pts) + f'" fill="{fill}"/>')
    # courthouse: wide block, central tower, dome, finial
    rect(0.00, 0.17, 0.20); rect(0.065, 0.04, 0.34)
    out.append(f'<ellipse cx="{x0 + w * 0.085:.1f}" cy="{base - h * 0.34:.1f}" rx="{w * 0.024:.1f}" ry="{h * 0.045:.1f}" fill="{fill}"/>')
    rect(0.081, 0.008, 0.42)
    rect(0.18, 0.05, 0.16)
    # Carter Burgess Plaza: three setbacks
    rect(0.24, 0.10, 0.46); rect(0.255, 0.07, 0.52); rect(0.27, 0.04, 0.56)
    rect(0.35, 0.04, 0.22)
    # The Tower: shaft, setback, pyramid, spire
    rect(0.40, 0.09, 0.62); rect(0.41, 0.07, 0.66)
    poly([(0.41, 0.66), (0.48, 0.66), (0.445, 0.76)])
    rect(0.442, 0.006, 0.86)
    # Burnett Plaza: tallest, notched crown
    rect(0.50, 0.12, 0.78); rect(0.50, 0.03, 0.84); rect(0.59, 0.03, 0.84)
    rect(0.63, 0.03, 0.26)
    # D.R. Horton Tower: chamfered crown
    rect(0.665, 0.10, 0.64)
    poly([(0.665, 0.64), (0.765, 0.64), (0.765, 0.69), (0.745, 0.72), (0.685, 0.72), (0.665, 0.69)])
    # City Center I & II: stepped glass boxes
    rect(0.775, 0.06, 0.56); rect(0.785, 0.04, 0.60)
    rect(0.84, 0.05, 0.50); rect(0.848, 0.034, 0.54)
    # Wells Fargo Tower: two steps
    rect(0.895, 0.06, 0.48); rect(0.905, 0.04, 0.52)
    # Frost Tower: slanted roof
    poly([(0.955, 0.0), (1.0, 0.0), (1.0, 0.44), (0.955, 0.40)])
    return "".join(out)


def option_b2(c: dict, with_caption: bool) -> str:
    """Sunset skyline, Fort Worth edition."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    ty = 250 if with_caption else 200
    th = 500 if with_caption else 600
    mono = c["body"] == INK
    grad = ('<defs><linearGradient id="sun" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{SKY}"/><stop offset="0.55" stop-color="{GOLD}"/><stop offset="1" stop-color="{ORANGE}"/>'
            '</linearGradient></defs>')
    sx, sy, sw, sh = 140 + 34, ty + 34, 720 - 68, th - 68
    sun = "" if mono else f'<circle cx="{sx + sw * 0.30:.0f}" cy="{sy + sh * 0.50:.0f}" r="{sh * 0.15:.0f}" fill="{PAPER}" opacity="0.85"/>'
    city = fort_worth_skyline(sx + 30, sy + sh * 0.12, sw - 60, sh * 0.76, body if not mono else INK)
    ground = f'<rect x="{sx + 22}" y="{sy + sh * 0.88:.0f}" width="{sw - 44}" height="{sh * 0.03:.0f}" fill="{accent if mono else body}"/>'
    ant = (f'<g stroke="{body}" stroke-width="30" stroke-linecap="round" fill="none">'
           f'<path d="M 500 {ty} L 380 {ty - 150}"/><path d="M 500 {ty} L 620 {ty - 150}"/></g><circle cx="500" cy="{ty}" r="30" fill="{body}"/>')
    svg = grad + f'<rect x="140" y="{ty}" width="720" height="{th}" rx="64" fill="{body}"/>' \
        + f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="38" fill="{screen if mono else "url(#sun)"}"/>' + sun + city + ground \
        + f'<rect x="284" y="{ty + th - 2}" width="72" height="34" fill="{body}"/><rect x="644" y="{ty + th - 2}" width="72" height="34" fill="{body}"/>' + ant
    if with_caption:
        svg += caption(930, "FTWTV", cap, size=150, spacing=-2)
    return wrap(svg)


def taper(p0, p1, p2, p3, w0: float, w1: float, n: int = 28) -> str:
    """A filled polygon that follows a cubic Bezier, w0 thick at the start tapering to w1 at the tip."""
    import math
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        dx = 3 * (1 - t) ** 2 * (p1[0] - p0[0]) + 6 * (1 - t) * t * (p2[0] - p1[0]) + 3 * t ** 2 * (p3[0] - p2[0])
        dy = 3 * (1 - t) ** 2 * (p1[1] - p0[1]) + 6 * (1 - t) * t * (p2[1] - p1[1]) + 3 * t ** 2 * (p3[1] - p2[1])
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        wdt = (w0 + (w1 - w0) * t) / 2
        pts.append(((x + nx * wdt, y + ny * wdt), (x - nx * wdt, y - ny * wdt)))
    left = [a for a, _ in pts]
    right = [b for _, b in pts][::-1]
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in left + right)


def longhorn(cx: float, cy: float, scale: float, fill: str) -> str:
    """A longhorn head: wide tapered horns that sweep out and turn up, ears, a long face and muzzle."""
    s = scale
    horn_l = taper((cx - 30 * s, cy - 20 * s), (cx - 170 * s, cy - 95 * s), (cx - 330 * s, cy - 30 * s), (cx - 405 * s, cy - 200 * s), 96 * s, 12 * s)
    horn_r = taper((cx + 30 * s, cy - 20 * s), (cx + 170 * s, cy - 95 * s), (cx + 330 * s, cy - 30 * s), (cx + 405 * s, cy - 200 * s), 96 * s, 12 * s)
    return (f'<g fill="{fill}"><polygon points="{horn_l}"/><polygon points="{horn_r}"/>'
            f'<ellipse cx="{cx - 72 * s:.1f}" cy="{cy + 10 * s:.1f}" rx="{46 * s:.1f}" ry="{22 * s:.1f}" transform="rotate(-20 {cx - 72 * s:.1f} {cy + 10 * s:.1f})"/>'
            f'<ellipse cx="{cx + 72 * s:.1f}" cy="{cy + 10 * s:.1f}" rx="{46 * s:.1f}" ry="{22 * s:.1f}" transform="rotate(20 {cx + 72 * s:.1f} {cy + 10 * s:.1f})"/>'
            f'<ellipse cx="{cx:.1f}" cy="{cy + 30 * s:.1f}" rx="{70 * s:.1f}" ry="{105 * s:.1f}"/>'
            f'<ellipse cx="{cx:.1f}" cy="{cy + 120 * s:.1f}" rx="{54 * s:.1f}" ry="{46 * s:.1f}"/></g>')


def option_d(c: dict, with_caption: bool) -> str:
    """Cowtown: a longhorn on the sunset screen with the lone star."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    ty = 250 if with_caption else 200
    th = 500 if with_caption else 600
    mono = c["body"] == INK
    grad = ('<defs><linearGradient id="sun" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{SKY}"/><stop offset="0.55" stop-color="{GOLD}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient></defs>')
    sx, sy, sw, sh = 174, ty + 34, 652, th - 68
    star = f'<polygon points="{star_points(sx + sw * 0.15, sy + sh * 0.2, 26)}" fill="{PAPER if not mono else INK}"/>'
    head = longhorn(500, sy + sh * 0.50, sh / 600 * 1.05, body if not mono else INK)
    ant = (f'<g stroke="{body}" stroke-width="30" stroke-linecap="round" fill="none">'
           f'<path d="M 500 {ty} L 380 {ty - 150}"/><path d="M 500 {ty} L 620 {ty - 150}"/></g><circle cx="500" cy="{ty}" r="30" fill="{body}"/>')
    svg = grad + f'<rect x="140" y="{ty}" width="720" height="{th}" rx="64" fill="{body}"/>' \
        + f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="38" fill="{screen if mono else "url(#sun)"}"/>' + star + head \
        + f'<rect x="284" y="{ty + th - 2}" width="72" height="34" fill="{body}"/><rect x="644" y="{ty + th - 2}" width="72" height="34" fill="{body}"/>' + ant
    if with_caption:
        svg += caption(930, "FTWTV", cap, size=150, spacing=-2)
    return wrap(svg)


def option_e(c: dict, with_caption: bool) -> str:
    """The Tarrant County Courthouse on the screen: the building every local recognises."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    ty = 250 if with_caption else 200
    th = 500 if with_caption else 600
    mono = c["body"] == INK
    grad = ('<defs><linearGradient id="sun" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{SKY}"/><stop offset="0.55" stop-color="{GOLD}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient></defs>')
    sx, sy, sw, sh = 174, ty + 34, 652, th - 68
    ink = body if not mono else INK
    base = sy + sh * 0.86
    cx = 500
    parts = [f'<rect x="{sx + sw * 0.12:.0f}" y="{base - sh * 0.30:.0f}" width="{sw * 0.76:.0f}" height="{sh * 0.30:.0f}" fill="{ink}"/>',     # main block
             f'<rect x="{sx + sw * 0.08:.0f}" y="{base - sh * 0.34:.0f}" width="{sw * 0.84:.0f}" height="{sh * 0.05:.0f}" fill="{ink}"/>',     # cornice
             f'<rect x="{cx - sw * 0.09:.0f}" y="{base - sh * 0.62:.0f}" width="{sw * 0.18:.0f}" height="{sh * 0.32:.0f}" fill="{ink}"/>',    # clock tower
             f'<circle cx="{cx}" cy="{base - sh * 0.50:.0f}" r="{sw * 0.045:.0f}" fill="{PAPER if not mono else PAPER}"/>',                   # clock face
             f'<path d="M {cx - sw * 0.10:.0f} {base - sh * 0.62:.0f} Q {cx} {base - sh * 0.86:.0f} {cx + sw * 0.10:.0f} {base - sh * 0.62:.0f} Z" fill="{ink}"/>',  # dome
             f'<rect x="{cx - 4}" y="{base - sh * 0.92:.0f}" width="8" height="{sh * 0.14:.0f}" fill="{ink}"/>',                                # finial
             f'<rect x="{sx + sw * 0.08:.0f}" y="{base:.0f}" width="{sw * 0.84:.0f}" height="{sh * 0.03:.0f}" fill="{accent if mono else ink}"/>']
    for i in range(7):   # arched windows
        wx = sx + sw * (0.17 + i * 0.11)
        parts.append(f'<rect x="{wx:.0f}" y="{base - sh * 0.22:.0f}" width="{sw * 0.05:.0f}" height="{sh * 0.14:.0f}" rx="{sw * 0.025:.0f}" fill="{PAPER if not mono else PAPER}"/>')
    ant = (f'<g stroke="{body}" stroke-width="30" stroke-linecap="round" fill="none">'
           f'<path d="M 500 {ty} L 380 {ty - 150}"/><path d="M 500 {ty} L 620 {ty - 150}"/></g><circle cx="500" cy="{ty}" r="30" fill="{body}"/>')
    svg = grad + f'<rect x="140" y="{ty}" width="720" height="{th}" rx="64" fill="{body}"/>' \
        + f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="38" fill="{screen if mono else "url(#sun)"}"/>' + "".join(parts) \
        + f'<rect x="284" y="{ty + th - 2}" width="72" height="34" fill="{body}"/><rect x="644" y="{ty + th - 2}" width="72" height="34" fill="{body}"/>' + ant
    if with_caption:
        svg += caption(930, "FTWTV", cap, size=150, spacing=-2)
    return wrap(svg)


def option_g(c: dict, with_caption: bool) -> str:
    """Stockyards-style sign: a western marquee with bulbs, FORT WORTH big, TEXAS TV under it, a small TV on top."""
    body, screen, fg, accent, cap = c["body"], c["screen"], c["fg"], c["accent"], c["caption"]
    mono = c["body"] == INK
    gold = accent
    sign_fill = body
    text_main = gold if not mono else PAPER
    text_sub = PAPER if body != PAPER else NAVY
    svg = (f'<rect x="60" y="330" width="880" height="420" rx="48" fill="{sign_fill}"/>'
           f'<rect x="92" y="362" width="816" height="356" rx="30" fill="none" stroke="{gold}" stroke-width="8"/>')
    # marquee bulbs along the frame
    bulbs = []
    for i in range(16):
        x = 110 + i * 52
        bulbs.append(f'<circle cx="{x}" cy="345" r="9" fill="{gold}"/><circle cx="{x}" cy="735" r="9" fill="{gold}"/>')
    for j in range(7):
        y = 395 + j * 52
        bulbs.append(f'<circle cx="75" cy="{y}" r="9" fill="{gold}"/><circle cx="925" cy="{y}" r="9" fill="{gold}"/>')
    svg += "".join(bulbs)
    svg += (f'<text x="500" y="545" text-anchor="middle" font-family="{FONT}" font-weight="900" font-size="128" textLength="700" lengthAdjust="spacingAndGlyphs" fill="{text_main}">FORT WORTH</text>'
            f'<text x="500" y="672" text-anchor="middle" font-family="{FONT}" font-weight="800" font-size="88" letter-spacing="16" fill="{text_sub}">TEXAS TV</text>')
    # small TV on top of the sign
    svg += (f'<g stroke="{sign_fill}" stroke-width="22" stroke-linecap="round" fill="none"><path d="M 500 150 L 440 70"/><path d="M 500 150 L 560 70"/></g>'
            f'<rect x="400" y="150" width="200" height="150" rx="30" fill="{sign_fill}"/>'
            f'<rect x="420" y="170" width="160" height="110" rx="18" fill="{screen if mono else gold}"/>'
            f'<polygon points="{star_points(500, 228, 42)}" fill="{sign_fill}"/>')
    if with_caption:
        svg += f'<text x="500" y="880" text-anchor="middle" font-family="{FONT}" font-weight="700" font-size="54" letter-spacing="12" fill="{cap}">WHERE THE WEST BEGINS</text>'
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


OPTIONS = {"b-skyline": option_b2, "d-longhorn": option_d, "e-courthouse": option_e, "g-sign": option_g,
           "a-horns": option_a, "c-badge": option_c}
LABELS = {"b-skyline": "B  Fort Worth skyline at sunset", "d-longhorn": "D  Cowtown longhorn", "e-courthouse": "E  Tarrant County Courthouse",
          "g-sign": "G  Stockyards-style sign", "a-horns": "A  Horn antennae", "c-badge": "C  Badge"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("b-sunset-*"):
        stale.unlink()
    files = []
    for key, fn in OPTIONS.items():
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
    rows = list(LABELS.items())
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
