"""Custom marks with a story, in a signature palette (brick red / cream / warm black):

  F  "The Fort"        a crenellated fort badge with the lone star: the city is literally named after a fort
  P  "Sleeping panther" Panther City: the 1870s joke that Fort Worth was so quiet a panther slept in the street,
                        which the city then adopted (it is on the police badge). A curled, sleeping cat silhouette.
  S  "Talking star"     a lone star with a speech-bubble tail: the page is where the city talks

    python scripts/make_logo_concepts3.py --name "Fort Worth Daily"
Output: assets/brand/concepts3/
"""
from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand" / "concepts3"
RED, CREAM, INK, TEAL = "#E8412F", "#F6EFE3", "#15110F", "#1B998B"
FAM = "Inter Display, Inter, Arial, sans-serif"
# figure, detail (cut-outs / eye), background the mark is meant for, caption colour
WAYS = {"light": (RED, CREAM, CREAM, INK), "dark": (CREAM, INK, INK, CREAM), "mono": (INK, CREAM, CREAM, INK)}


def svg(w, h, body, bg=None):
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{rect}{body}</svg>'


def star(cx, cy, r, fill, rot=0.0):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + rot + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + rr * math.cos(ang):.1f},{cy + rr * math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def caption(y, name, fill, size=64, spacing=0.14):
    return (f'<text x="500" y="{y}" text-anchor="middle" font-family="{FAM}" font-weight="800" font-size="{size}" '
            f'letter-spacing="{size * spacing:.1f}" fill="{fill}">{name.upper()}</text>')


# ------------------------------------------------------------------------------------------------------ F  The Fort
def concept_f(name, way, with_name):
    fig, detail, bg, cap = WAYS[way]
    s = 0.78 if with_name else 0.92
    cx, cy = 500, (470 if with_name else 500)
    W = 640 * s; H = 600 * s
    x0, y0 = cx - W / 2, cy - H / 2
    merlon_w, gap = W / 7, W / 7
    # badge body: flat top with three merlons, rounded bottom corners
    d = [f"M {x0:.1f} {y0 + H * 0.16:.1f}"]
    xs = x0
    for i in range(7):
        if i % 2 == 0:  # merlon up
            d.append(f"L {xs:.1f} {y0:.1f} L {xs + merlon_w:.1f} {y0:.1f} L {xs + merlon_w:.1f} {y0 + H * 0.16:.1f}")
        else:
            d.append(f"L {xs + gap:.1f} {y0 + H * 0.16:.1f}")
        xs += merlon_w if i % 2 == 0 else gap
    r = W * 0.18
    d.append(f"L {x0 + W:.1f} {y0 + H - r:.1f} Q {x0 + W:.1f} {y0 + H:.1f} {x0 + W - r:.1f} {y0 + H:.1f} "
             f"L {x0 + r:.1f} {y0 + H:.1f} Q {x0:.1f} {y0 + H:.1f} {x0:.1f} {y0 + H - r:.1f} Z")
    body = f'<path d="{" ".join(d)}" fill="{fig}"/>'
    # the gate: an arch cut out at the bottom centre, and the star above it
    gw, gh = W * 0.22, H * 0.30
    body += (f'<path d="M {cx - gw / 2:.1f} {y0 + H:.1f} L {cx - gw / 2:.1f} {y0 + H - gh + gw / 2:.1f} '
             f'A {gw / 2:.1f} {gw / 2:.1f} 0 0 1 {cx + gw / 2:.1f} {y0 + H - gh + gw / 2:.1f} L {cx + gw / 2:.1f} {y0 + H:.1f} Z" fill="{detail}"/>')
    body += star(cx, y0 + H * 0.40, W * 0.17, detail)
    if with_name:
        body += caption(880, name, cap, 62, 0.16)
    return svg(1000, 1000, body)


# ------------------------------------------------------------------------------------------------------ P  Sleeping panther
def concept_p(name, way, with_name):
    fig, detail, bg, cap = WAYS[way]
    s = 0.80 if with_name else 0.95
    cx, cy = 500, (450 if with_name else 500)
    def P(x, y):  # local coords (0..1000 box centred at 500,500) -> canvas
        return f"{cx + (x - 500) * s:.1f} {cy + (y - 500) * s:.1f}"
    # body: a low, rounded loaf; head tucked at the left front; tail wrapping underneath and up the front
    body_path = (f"M {P(250, 600)} C {P(250, 420)} {P(400, 330)} {P(580, 330)} C {P(760, 330)} {P(800, 450)} {P(800, 560)} "
                 f"C {P(800, 640)} {P(740, 690)} {P(640, 690)} L {P(330, 690)} C {P(280, 690)} {P(250, 650)} {P(250, 600)} Z")
    head = f'<circle cx="{cx + (300 - 500) * s:.1f}" cy="{cy + (560 - 500) * s:.1f}" r="{112 * s:.1f}" fill="{fig}"/>'
    ears = (f'<polygon points="{P(222, 480).replace(" ", ",")} {P(262, 420).replace(" ", ",")} {P(300, 468).replace(" ", ",")}" fill="{fig}"/>'
            f'<polygon points="{P(318, 460).replace(" ", ",")} {P(366, 418).replace(" ", ",")} {P(386, 480).replace(" ", ",")}" fill="{fig}"/>')
    tail = (f'<path d="M {P(770, 620)} C {P(860, 680)} {P(840, 790)} {P(700, 790)} C {P(560, 790)} {P(420, 790)} {P(330, 720)}" '
            f'fill="none" stroke="{fig}" stroke-width="{54 * s:.1f}" stroke-linecap="round"/>')
    # a closed eye and the nose, in the detail colour
    eye = (f'<path d="M {P(236, 566)} Q {P(268, 592)} {P(300, 566)}" fill="none" stroke="{detail}" stroke-width="{10 * s:.1f}" stroke-linecap="round"/>'
           f'<circle cx="{cx + (206 - 500) * s:.1f}" cy="{cy + (600 - 500) * s:.1f}" r="{9 * s:.1f}" fill="{detail}"/>')
    body = f'<path d="{body_path}" fill="{fig}"/>' + tail + head + ears + eye
    if with_name:
        body += caption(880, name, cap, 62, 0.16)
    return svg(1000, 1000, body)


# ------------------------------------------------------------------------------------------------------ S  Talking star
def concept_s(name, way, with_name):
    fig, detail, bg, cap = WAYS[way]
    r = 300 if with_name else 350
    cx, cy = 500, (430 if with_name else 480)
    body = star(cx, cy, r, fig)
    # speech-bubble tail: hangs from the bottom edge of the lower-left arm, like a comic balloon
    a6 = -math.pi / 2 + 6 * math.pi / 5          # lower-left point
    a5 = -math.pi / 2 + 5 * math.pi / 5          # inner notch at the bottom
    p6 = (cx + r * math.cos(a6), cy + r * math.sin(a6))
    p5 = (cx + r * 0.42 * math.cos(a5), cy + r * 0.42 * math.sin(a5))
    base_a = (p6[0] + (p5[0] - p6[0]) * 0.15, p6[1] + (p5[1] - p6[1]) * 0.15)
    base_b = (p6[0] + (p5[0] - p6[0]) * 0.75, p6[1] + (p5[1] - p6[1]) * 0.75)
    tip = (cx - r * 0.34, cy + r * 1.18)
    body += f'<polygon points="{base_a[0]:.1f},{base_a[1]:.1f} {base_b[0]:.1f},{base_b[1]:.1f} {tip[0]:.1f},{tip[1]:.1f}" fill="{fig}"/>'
    if with_name:
        body += caption(880, name, cap, 62, 0.16)
    return svg(1000, 1000, body)


def sheet(labels):
    from PIL import Image, ImageDraw, ImageFont
    red, cream, ink = (232, 65, 47), (246, 239, 227), (21, 17, 15)
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf", 30)
    tile = 420
    rows = list(labels.items())
    sheet = Image.new("RGB", (4 * (tile + 20) + 20, len(rows) * (tile + 70) + 160), (235, 232, 226))
    d = ImageDraw.Draw(sheet)
    for r, (key, label) in enumerate(rows):
        y = 20 + r * (tile + 70)
        for c, (name, bgc) in enumerate([(f"{key}-light-name-1024.png", cream), (f"{key}-dark-name-1024.png", ink), (f"{key}-mono-mark-1024.png", cream)]):
            x = 20 + c * (tile + 20)
            im = Image.open(OUT / name).convert("RGBA").resize((tile, tile), Image.LANCZOS)
            cell = Image.new("RGBA", (tile, tile), bgc + (255,)); cell.alpha_composite(im)
            sheet.paste(cell.convert("RGB"), (x, y))
        x = 20 + 3 * (tile + 20)
        cell = Image.new("RGB", (tile, tile), (240, 242, 245)); cd = ImageDraw.Draw(cell)
        for size, pos in ((200, (30, 30)), (96, (260, 60)), (48, (260, 190)), (32, (330, 190))):
            mark = Image.open(OUT / f"{key}-light-mark-1024.png").convert("RGBA").resize((int(size * 0.84), int(size * 0.84)), Image.LANCZOS)
            cd.ellipse([pos[0], pos[1], pos[0] + size, pos[1] + size], fill=cream, outline=(200, 205, 212))
            off = (size - mark.width) // 2
            cell.paste(mark, (pos[0] + off, pos[1] + off), mark)
        cd.text((30, 300), "as an avatar: 200 / 96 / 48 / 32 px", font=f, fill=(90, 90, 90))
        sheet.paste(cell, (x, y))
        d.text((20, y + tile + 18), label, font=f, fill=(30, 30, 30))
    y = 20 + len(rows) * (tile + 70)
    for i, (n, hx, c) in enumerate((("Brick red", "#E8412F", red), ("Cream", "#F6EFE3", cream), ("Warm black", "#15110F", ink), ("Trinity teal (sparingly)", "#1B998B", (27, 153, 139)))):
        x = 20 + i * 440
        d.rounded_rectangle([x, y, x + 120, y + 90], radius=14, fill=c, outline=(180, 180, 180))
        d.text((x + 140, y + 10), n, font=f, fill=(30, 30, 30)); d.text((x + 140, y + 50), hx, font=f, fill=(110, 110, 110))
    sheet.save(OUT / "concepts3-sheet.jpg", quality=90)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", default="Fort Worth Daily")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    files = []
    for key, fn in (("f-fort", concept_f), ("p-panther", concept_p), ("s-star", concept_s)):
        for way in WAYS:
            for shape, with_name in (("name", True), ("mark", False)):
                p = OUT / f"{key}-{way}-{shape}.svg"
                p.write_text(fn(a.name, way, with_name)); files.append(str(p))
    subprocess.run(["node", str(ROOT / "scripts" / "render_svg.js"), "1024", str(OUT), *files], check=True, stdout=subprocess.DEVNULL)
    sheet({"f-fort": "F  The Fort (with the gate and the star)", "p-panther": "P  The sleeping panther of Panther City", "s-star": "S  The star that talks"})
    print("wrote", len(files), "to", OUT)


if __name__ == "__main__":
    main()
