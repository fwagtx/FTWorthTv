"""Three logo concepts that are neither a TV set nor a monogram:

  T  "Texas, dot"      the state outline with a gold dot exactly where Fort Worth is (32.75 N, 97.33 W)
  H  "The courthouse"  the Tarrant County Courthouse front elevation, traced from a public-domain 1900s postcard
  E  "Emblem"          a broadcast-style roundel: the name around a lone star

Flat, two colours, vector SVG rendered by scripts/render_svg.js into assets/brand/concepts/.
    python scripts/make_logo_concepts2.py --name "Fort Worth Daily"
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand" / "concepts"
NAVY, GOLD, PAPER, INK = "#14182B", "#F2B134", "#FFFFFF", "#0F1419"
FAM = "Inter Display, Inter, Arial, sans-serif"
WAYS = {"light": (NAVY, GOLD, PAPER), "dark": (PAPER, GOLD, NAVY), "mono": (INK, INK, PAPER)}   # figure, accent, ground

# Texas border, simplified (lon, lat), clockwise from the panhandle's north-west corner
TEXAS = [(-103.04, 36.50), (-100.00, 36.50), (-100.00, 34.56), (-99.20, 34.40), (-98.10, 34.15), (-97.15, 33.90), (-96.50, 33.80),
         (-95.80, 33.85), (-95.20, 33.95), (-94.48, 33.64), (-94.04, 33.55), (-94.04, 32.00), (-93.90, 31.50), (-93.70, 31.00),
         (-93.55, 30.50), (-93.85, 29.90), (-93.84, 29.69), (-94.70, 29.35), (-95.20, 28.90), (-96.00, 28.50), (-96.50, 28.20),
         (-97.00, 27.90), (-97.30, 27.20), (-97.30, 26.50), (-97.15, 25.95), (-97.50, 25.90), (-98.20, 26.05), (-99.00, 26.40),
         (-99.50, 27.30), (-99.50, 27.50), (-100.00, 28.00), (-100.40, 28.60), (-100.65, 29.10), (-101.00, 29.50), (-101.40, 29.75),
         (-102.20, 29.85), (-102.70, 29.75), (-103.10, 29.00), (-103.50, 29.10), (-104.00, 29.30), (-104.50, 29.65), (-104.70, 30.00),
         (-105.00, 30.60), (-105.50, 31.00), (-106.00, 31.40), (-106.50, 31.75), (-106.60, 32.00), (-103.06, 32.00)]
FORT_WORTH = (-97.33, 32.75)


def project(points, box):
    """Equirectangular with the longitude scaled by cos(31°), fitted into box=(x, y, w, h)."""
    k = math.cos(math.radians(31))
    xs = [lon * k for lon, _ in points]; ys = [-lat for _, lat in points]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    bx, by, bw, bh = box
    s = min(bw / (maxx - minx), bh / (maxy - miny))
    ox = bx + (bw - (maxx - minx) * s) / 2; oy = by + (bh - (maxy - miny) * s) / 2
    def P(lon, lat):
        return (ox + (lon * k - minx) * s, oy + (-lat - miny) * s)
    return P


def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>'


def star(cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.4
        pts.append(f"{cx + rr * math.cos(ang):.1f},{cy + rr * math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def caption(y, name, fill, size=74, spacing=0.12):
    return (f'<text x="500" y="{y}" text-anchor="middle" font-family="{FAM}" font-weight="800" font-size="{size}" '
            f'letter-spacing="{size * spacing:.1f}" fill="{fill}">{name.upper()}</text>')


# ---------------------------------------------------------------------------------------------------- T  Texas, dot
def concept_t(name, way, with_name):
    fig, acc, ground = WAYS[way]
    box = (130, 90, 740, 620) if with_name else (110, 110, 780, 780)
    P = project(TEXAS, box)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (P(lon, lat) for lon, lat in TEXAS))
    fx, fy = P(*FORT_WORTH)
    r = 34 if with_name else 40
    body = f'<polygon points="{pts}" fill="{fig}"/>'
    body += f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="{r + 14}" fill="{ground}"/><circle cx="{fx:.1f}" cy="{fy:.1f}" r="{r}" fill="{acc}"/>'
    if with_name:
        body += caption(880, name, fig, 66, 0.14)
    return svg(1000, 1000, body)


# ---------------------------------------------------------------------------------------------------- H  Courthouse
def concept_h(name, way, with_name):
    """The Tarrant County Courthouse as a flat icon: proportions taken from the 1900s postcard (tower width 14% of the
    facade, dome at the top, clock at 70% height, pediment over the central block, pavilions with small domes at the ends)."""
    fig, acc, ground = WAYS[way]
    x0, y0, w, h = (110, 150, 780, 560) if with_name else (90, 140, 820, 660)
    base = y0 + h
    def X(fx): return x0 + w * fx
    def Y(fh): return base - h * fh          # fh = height above the base, as a fraction of h
    def rect(fx0, fx1, fh0, fh1, fill=None, rx=0):
        return f'<rect x="{X(fx0):.1f}" y="{Y(fh1):.1f}" width="{w * (fx1 - fx0):.1f}" height="{h * (fh1 - fh0):.1f}" rx="{rx}" fill="{fill or fig}"/>'
    b = []
    b.append(rect(0.0, 1.0, 0.0, 0.34))                                   # wings
    for fx0, fx1 in ((0.0, 0.17), (0.83, 1.0)):                          # end pavilions + small domes
        b.append(rect(fx0, fx1, 0.0, 0.44))
        cx = X((fx0 + fx1) / 2)
        b.append(f'<path d="M {X(fx0) + w * 0.02:.1f} {Y(0.44):.1f} Q {cx:.1f} {Y(0.56):.1f} {X(fx1) - w * 0.02:.1f} {Y(0.44):.1f} Z" fill="{fig}"/>')
        b.append(f'<rect x="{cx - 3:.1f}" y="{Y(0.60):.1f}" width="6" height="{h * 0.10:.1f}" fill="{fig}"/>')
    b.append(rect(0.30, 0.70, 0.0, 0.46))                                 # central block
    b.append(f'<polygon points="{X(0.32):.1f},{Y(0.46):.1f} {X(0.68):.1f},{Y(0.46):.1f} {X(0.50):.1f},{Y(0.58):.1f}" fill="{fig}"/>')   # pediment
    b.append(rect(0.43, 0.57, 0.40, 0.78))                                # tower shaft
    b.append(rect(0.445, 0.555, 0.78, 0.88))                              # belfry
    b.append(f'<path d="M {X(0.445):.1f} {Y(0.88):.1f} Q {X(0.5):.1f} {Y(1.02):.1f} {X(0.555):.1f} {Y(0.88):.1f} Z" fill="{fig}"/>')   # dome
    b.append(f'<rect x="{X(0.5) - 4:.1f}" y="{Y(1.06):.1f}" width="8" height="{h * 0.08:.1f}" fill="{fig}"/>')                      # finial
    b.append(f'<circle cx="{X(0.5):.1f}" cy="{Y(0.70):.1f}" r="{w * 0.036:.1f}" fill="{ground}"/>')                                # clock
    b.append(f'<circle cx="{X(0.5):.1f}" cy="{Y(0.70):.1f}" r="{w * 0.008:.1f}" fill="{fig}"/>')
    b.append(f'<rect x="{X(0.5) - 2:.1f}" y="{Y(0.70) - w * 0.026:.1f}" width="4" height="{w * 0.026:.1f}" fill="{fig}"/>')       # clock hands
    b.append(f'<rect x="{X(0.5):.1f}" y="{Y(0.70) - 2:.1f}" width="{w * 0.02:.1f}" height="4" fill="{fig}"/>')
    b.append(f'<rect x="{X(0.47):.1f}" y="{Y(0.58):.1f}" width="{w * 0.06:.1f}" height="{h * 0.09:.1f}" rx="{w * 0.03:.1f}" fill="{ground}"/>')   # belfry arch
    for fx in (0.045, 0.19, 0.24, 0.71, 0.76, 0.905):                    # arched windows on the wings
        b.append(f'<rect x="{X(fx):.1f}" y="{Y(0.28):.1f}" width="{w * 0.045:.1f}" height="{h * 0.17:.1f}" rx="{w * 0.0225:.1f}" fill="{ground}"/>')
    b.append(f'<rect x="{X(0.44):.1f}" y="{Y(0.36):.1f}" width="{w * 0.12:.1f}" height="{h * 0.24:.1f}" rx="{w * 0.06:.1f}" fill="{ground}"/>')  # grand arch
    b.append(f'<rect x="{X(0.455):.1f}" y="{Y(0.30):.1f}" width="{w * 0.09:.1f}" height="{h * 0.18:.1f}" fill="{fig}"/>')
    b.append(f'<rect x="{X(-0.04):.1f}" y="{base + 14:.1f}" width="{w * 1.08:.1f}" height="16" fill="{acc}"/>')
    body = "".join(b)
    if with_name:
        body += caption(900, name, fig, 66, 0.14)
    return svg(1000, 1000, body)


# ---------------------------------------------------------------------------------------------------- E  Emblem
def concept_e(name, way, with_name):
    fig, acc, ground = WAYS[way]
    top, bottom = name.upper().rsplit(" ", 1) if " " in name else (name.upper(), "")
    body = f'<circle cx="500" cy="500" r="480" fill="{fig}"/><circle cx="500" cy="500" r="392" fill="none" stroke="{acc}" stroke-width="10"/>'
    body += star(500, 470, 150, acc)
    body += ('<defs><path id="arc" d="M 500 500 m -395 0 a 395 395 0 0 1 790 0"/>'
             '<path id="arcb" d="M 500 500 m -440 0 a 440 440 0 0 0 880 0"/></defs>')
    body += (f'<text font-family="{FAM}" font-weight="800" font-size="84" letter-spacing="10" fill="{ground}">'
             f'<textPath href="#arc" startOffset="50%" text-anchor="middle">{top}</textPath></text>')
    if bottom:
        body += (f'<text font-family="{FAM}" font-weight="800" font-size="84" letter-spacing="10" fill="{ground}">'
                 f'<textPath href="#arcb" startOffset="50%" text-anchor="middle">{bottom}</textPath></text>')
    body += f'<text x="500" y="730" text-anchor="middle" font-family="{FAM}" font-weight="700" font-size="46" letter-spacing="8" fill="{ground}">TEXAS</text>'
    return svg(1000, 1000, body)


def sheet(labels):
    from PIL import Image, ImageDraw, ImageFont
    navy, paper = (20, 24, 43), (255, 255, 255)
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf", 30)
    tile = 420
    rows = list(labels.items())
    sheet = Image.new("RGB", (4 * (tile + 20) + 20, len(rows) * (tile + 70) + 20), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    for r, (key, label) in enumerate(rows):
        y = 20 + r * (tile + 70)
        for c, (name, bg) in enumerate([(f"{key}-light-name-1024.png", paper), (f"{key}-dark-name-1024.png", navy), (f"{key}-mono-mark-1024.png", paper)]):
            x = 20 + c * (tile + 20)
            im = Image.open(OUT / name).convert("RGBA").resize((tile, tile), Image.LANCZOS)
            cell = Image.new("RGBA", (tile, tile), bg + (255,)); cell.alpha_composite(im)
            sheet.paste(cell.convert("RGB"), (x, y))
        x = 20 + 3 * (tile + 20)
        cell = Image.new("RGB", (tile, tile), (240, 242, 245)); cd = ImageDraw.Draw(cell)
        for size, pos in ((200, (30, 30)), (96, (260, 60)), (48, (260, 190)), (32, (330, 190))):
            mark = Image.open(OUT / f"{key}-light-mark-1024.png").convert("RGBA").resize((int(size * 0.84), int(size * 0.84)), Image.LANCZOS)
            cd.ellipse([pos[0], pos[1], pos[0] + size, pos[1] + size], fill=paper, outline=(200, 205, 212))
            off = (size - mark.width) // 2
            cell.paste(mark, (pos[0] + off, pos[1] + off), mark)
        cd.text((30, 300), "as an avatar: 200 / 96 / 48 / 32 px", font=f, fill=(90, 90, 90))
        sheet.paste(cell, (x, y))
        d.text((20, y + tile + 18), label, font=f, fill=(30, 30, 30))
    sheet.save(OUT / "concepts-sheet.jpg", quality=90)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", default="Fort Worth Daily")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    files = []
    for key, fn in (("t-texas", concept_t), ("h-courthouse", concept_h), ("e-emblem", concept_e)):
        for way in WAYS:
            for shape, with_name in (("name", True), ("mark", False)):
                p = OUT / f"{key}-{way}-{shape}.svg"
                p.write_text(fn(a.name, way, with_name)); files.append(str(p))
    subprocess.run(["node", str(ROOT / "scripts" / "render_svg.js"), "1024", str(OUT), *files], check=True, stdout=subprocess.DEVNULL)
    sheet({"t-texas": "T  Texas, with the dot on Fort Worth", "h-courthouse": "H  The Tarrant County Courthouse", "e-emblem": "E  Emblem"})
    print("wrote", len(files), "concepts to", OUT)


if __name__ == "__main__":
    main()
