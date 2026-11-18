"""A typographic identity for the page: no gradients, no skyline, no mascots. Real type (Inter Display, Bitstream Charter),
measured with the actual font files so the lockups are set, not eyeballed. Vector SVG rendered to PNG by
scripts/render_svg.js. The name is a parameter so the same system sets "Fort Worth Daily", "Fort Worth Texas TV" or
anything else.

    python scripts/make_logo_daily.py                         # Fort Worth Daily (default)
    python scripts/make_logo_daily.py --top "FORT WORTH" --main "TEXAS TV" --mono FTW

Output: assets/brand/type/  (monogram, avatar, stacked wordmark, horizontal lockup, serif masthead; light / dark / mono;
plus sheet.jpg with the avatar at 200 / 96 / 48 / 32 px and a mock Facebook page header)
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand" / "type"
FONT_DIR = Path("/usr/share/fonts/opentype/inter")
BLACK, BOLD, SEMI = FONT_DIR / "InterDisplay-Black.otf", FONT_DIR / "InterDisplay-Bold.otf", FONT_DIR / "InterDisplay-SemiBold.otf"
FAM = "Inter Display, Inter, Arial, sans-serif"
SERIF = "Bitstream Charter, Charter, Georgia, serif"
NAVY, GOLD, PAPER, INK = "#14182B", "#F2B134", "#FFFFFF", "#0F1419"
CAP = 0.727          # Inter cap height in em


def width(text: str, font: Path, size: float, tracking_em: float = 0.0) -> float:
    f = ImageFont.truetype(str(font), int(round(size)))
    return f.getlength(text) * (size / int(round(size))) + tracking_em * size * (len(text) - 1)


def size_for(text: str, font: Path, target: float, tracking_em: float = 0.0) -> float:
    base = 100.0
    return target / (width(text, font, base, tracking_em) / base)


def text(x: float, y: float, s: str, font_weight: int, size: float, fill: str, tracking_em: float = 0.0, anchor="start", family=FAM, extra="") -> str:
    ls = f' letter-spacing="{tracking_em * size:.1f}"' if tracking_em else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-weight="{font_weight}" font-size="{size:.1f}" '
            f'fill="{fill}" text-anchor="{anchor}"{ls} {extra}>{s}</text>')


def svg(w: int, h: int, body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>'


WAYS = {  # background shape colour, letters, accent letter
    "light": (NAVY, PAPER, GOLD),
    "dark": (PAPER, NAVY, GOLD),
    "mono": (INK, PAPER, PAPER),
}
TEXT_WAYS = {  # for wordmarks on a background: main colour, accent
    "light": (NAVY, GOLD),
    "dark": (PAPER, GOLD),
    "mono": (INK, INK),
}


def monogram(mono: str, way: str, circle: bool) -> str:
    bg, fg, acc = WAYS[way]
    body = (f'<circle cx="500" cy="500" r="480" fill="{bg}"/>' if circle
            else f'<rect x="40" y="40" width="920" height="920" rx="170" fill="{bg}"/>')
    track = -0.035
    target = 640 if circle else 700
    s = size_for(mono, BLACK, target, track)
    s = min(s, 520)
    baseline = 500 + CAP * s / 2
    head, last = mono[:-1], mono[-1]
    body += (f'<text x="500" y="{baseline:.1f}" font-family="{FAM}" font-weight="900" font-size="{s:.1f}" text-anchor="middle" '
             f'letter-spacing="{track * s:.1f}" fill="{fg}">{head}<tspan fill="{acc}">{last}</tspan></text>')
    return svg(1000, 1000, body)


def stacked(top: str, main: str, way: str, w: int = 1600, h: int = 900) -> str:
    fg, acc = TEXT_WAYS[way]
    margin = 100
    inner = w - 2 * margin
    s_main = size_for(main, BLACK, inner, -0.02)
    s_top = size_for(top, SEMI, inner, 0.16)
    s_top = min(s_top, s_main * 0.34)
    top_base = margin + CAP * s_top
    rule_y = top_base + 0.36 * s_top
    main_base = rule_y + 0.30 * s_top + CAP * s_main
    body = text(margin, top_base, top, 600, s_top, fg, 0.16)
    body += f'<rect x="{margin}" y="{rule_y:.1f}" width="{inner}" height="{max(8, s_main * 0.045):.1f}" fill="{acc}"/>'
    body += text(margin, main_base, main, 900, s_main, fg, -0.02)
    total_h = int(main_base + 0.08 * s_main)
    return svg(w, total_h, body)


def lockup(mono: str, top: str, main: str, way: str) -> str:
    bg, fg_m, acc = WAYS[way]
    fg, acc2 = TEXT_WAYS[way]
    H = 700
    body = f'<rect x="60" y="60" width="580" height="580" rx="110" fill="{bg}"/>'
    track = -0.035
    s = min(size_for(mono, BLACK, 440, track), 330)
    body += (f'<text x="350" y="{350 + CAP * s / 2:.1f}" font-family="{FAM}" font-weight="900" font-size="{s:.1f}" text-anchor="middle" '
             f'letter-spacing="{track * s:.1f}" fill="{fg_m}">{mono[:-1]}<tspan fill="{acc}">{mono[-1]}</tspan></text>')
    x0 = 760
    s_main = size_for(main, BLACK, 1500, -0.02)
    s_main = min(s_main, 360)
    s_top = min(size_for(top, SEMI, width(main, BLACK, s_main, -0.02), 0.16), s_main * 0.34)
    top_base = 170 + CAP * s_top
    rule_y = top_base + 0.36 * s_top
    main_base = rule_y + 0.30 * s_top + CAP * s_main
    body += text(x0, top_base, top, 600, s_top, fg, 0.16)
    body += f'<rect x="{x0}" y="{rule_y:.1f}" width="{width(main, BLACK, s_main, -0.02):.1f}" height="{s_main * 0.045:.1f}" fill="{acc2}"/>'
    body += text(x0, main_base, main, 900, s_main, fg, -0.02)
    W = int(x0 + width(main, BLACK, s_main, -0.02) + 80)
    return svg(W, H, body)


def masthead(name: str, way: str, sub: str = "FORT WORTH, TEXAS") -> str:
    fg, acc = TEXT_WAYS[way]
    W, H = 2600, 640
    body = f'<rect x="120" y="80" width="{W - 240}" height="10" fill="{acc}"/><rect x="120" y="{H - 90}" width="{W - 240}" height="10" fill="{acc}"/>'
    body += text(W / 2, 400, name, 700, 230, fg, 0.0, anchor="middle", family=SERIF)
    body += text(W / 2, 500, sub, 600, 40, fg, 0.3, anchor="middle")
    return svg(W, H, body)


def sheet(names: dict) -> None:
    from PIL import ImageFilter
    def load(n):
        return Image.open(OUT / n).convert("RGBA")
    navy, paper = (20, 24, 43), (255, 255, 255)
    f = ImageFont.truetype(str(SEMI), 28)
    W = 2000
    rows: list[Image.Image] = []
    # row 1: monograms + avatar sizes
    r = Image.new("RGB", (W, 520), (235, 235, 235)); d = ImageDraw.Draw(r)
    for i, (n, bg) in enumerate([("monogram-light-1024.png", paper), ("monogram-dark-1024.png", navy), ("monogram-mono-1024.png", paper), ("avatar-light-1024.png", paper)]):
        cell = Image.new("RGBA", (440, 440), bg + (255,)); im = load(n).resize((400, 400), Image.LANCZOS); cell.alpha_composite(im, (20, 20))
        r.paste(cell.convert("RGB"), (30 + i * 470, 30))
    x = 30 + 4 * 470 - 20
    d.text((x, 40), "avatar at 200 / 96 / 48 / 32", font=f, fill=(90, 90, 90))
    for size, pos in ((200, (x, 90)), (96, (x + 230, 90)), (48, (x + 230, 210)), (32, (x + 300, 210))):
        im = load("avatar-light-1024.png").resize((size, size), Image.LANCZOS); r.paste(im, pos, im)
    rows.append(r)
    # row 2: stacked wordmark light + dark
    r = Image.new("RGB", (W, 620), (235, 235, 235))
    for i, (n, bg) in enumerate([("stacked-light-1600.png", paper), ("stacked-dark-1600.png", navy)]):
        cell = Image.new("RGBA", (960, 560), bg + (255,)); im = load(n); im.thumbnail((900, 500)); cell.alpha_composite(im, ((960 - im.width) // 2, (560 - im.height) // 2))
        r.paste(cell.convert("RGB"), (30 + i * 990, 30))
    rows.append(r)
    # row 3: lockup light + masthead
    r = Image.new("RGB", (W, 420), (235, 235, 235))
    for i, (n, bg) in enumerate([("lockup-light-2400.png", paper), ("masthead-light-2400.png", paper)]):
        cell = Image.new("RGBA", (960, 360), bg + (255,)); im = load(n); im.thumbnail((920, 320)); cell.alpha_composite(im, ((960 - im.width) // 2, (360 - im.height) // 2))
        r.paste(cell.convert("RGB"), (30 + i * 990, 30))
    rows.append(r)
    # row 4: mock Facebook page header
    r = Image.new("RGB", (W, 700), (240, 242, 245)); d = ImageDraw.Draw(r)
    cover = Image.new("RGBA", (1940, 440), navy + (255,))
    lk = load("lockup-dark-2400.png"); lk.thumbnail((1100, 300)); cover.alpha_composite(lk, (420, 70))
    r.paste(cover.convert("RGB"), (30, 30))
    av = load("avatar-light-1024.png").resize((240, 240), Image.LANCZOS)
    ring = Image.new("RGBA", (260, 260), (0, 0, 0, 0)); ImageDraw.Draw(ring).ellipse([0, 0, 259, 259], fill=(240, 242, 245, 255)); ring.alpha_composite(av, (10, 10))
    r.paste(ring, (80, 330), ring)
    d.text((360, 500), names["page"], font=ImageFont.truetype(str(BOLD), 54), fill=(5, 5, 5))
    d.text((360, 570), f"{names['handle']} · Media/News Company", font=ImageFont.truetype(str(SEMI), 30), fill=(101, 103, 107))
    rows.append(r)
    H = sum(im.height for im in rows)
    out = Image.new("RGB", (W, H), (235, 235, 235))
    y = 0
    for im in rows:
        out.paste(im, (0, y)); y += im.height
    out.save(OUT / "sheet.jpg", quality=90)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", default="FORT WORTH"); ap.add_argument("--main", default="DAILY"); ap.add_argument("--mono", default="FWD")
    ap.add_argument("--name", default="Fort Worth Daily"); ap.add_argument("--handle", default="@FortWorthDaily")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    files = []
    for way in WAYS:
        (OUT / f"monogram-{way}.svg").write_text(monogram(a.mono, way, circle=False)); files.append(f"monogram-{way}.svg")
        (OUT / f"avatar-{way}.svg").write_text(monogram(a.mono, way, circle=True)); files.append(f"avatar-{way}.svg")
        (OUT / f"stacked-{way}.svg").write_text(stacked(a.top, a.main, way)); files.append(f"stacked-{way}.svg")
        (OUT / f"lockup-{way}.svg").write_text(lockup(a.mono, a.top, a.main, way)); files.append(f"lockup-{way}.svg")
        (OUT / f"masthead-{way}.svg").write_text(masthead(a.name, way)); files.append(f"masthead-{way}.svg")
    node = ROOT / "scripts" / "render_svg.js"
    sq = [str(OUT / f) for f in files if f.startswith(("monogram", "avatar"))]
    wide = [str(OUT / f) for f in files if f.startswith(("lockup", "masthead"))]
    st = [str(OUT / f) for f in files if f.startswith("stacked")]
    subprocess.run(["node", str(node), "1024", str(OUT), *sq], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["node", str(node), "2400", str(OUT), *wide], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["node", str(node), "1600", str(OUT), *st], check=True, stdout=subprocess.DEVNULL)
    sheet({"page": a.name, "handle": a.handle})
    print("wrote", len(files), "svgs + pngs to", OUT)


if __name__ == "__main__":
    main()
