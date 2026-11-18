"""Facebook cover variants for Fort Worth Daily at 1640x624 (phones show the centre 1109 px, so all text lives there).

  photo     the Trinity Park view of downtown (DerekAyala27, CC BY 4.0, from the brandrefs branch) under a charcoal
            gradient, the lockup and tagline on the left, the credit small at the right
  charcoal  typographic: the lockup, the beat strip (NEWS · EVENTS · FOOD ...) and the handle
  light     the same on off-white

    python scripts/make_facebook_banners.py
Output: assets/brand/kit-B/banners/ + preview.jpg (desktop and mobile crops)
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_brandkit_identity import HANDLE, TAGLINE, lockup_body, text  # noqa: E402
from make_identity import DIRECTIONS, FONT_DIR, ROOT, g, svg  # noqa: E402

KEY = "B"
OUT = ROOT / "assets" / "brand" / f"kit-{KEY}" / "banners"
W, H = 1640, 624
SAFE_X0, SAFE_X1 = 266, 1374          # the 16:9 centre slice phones show
PHOTO = ROOT / "out" / "refs" / "Downtown_Fort_Worth_Skyline_jpg.jpg"
CREDIT = "Photo: DerekAyala27, CC BY 4.0"
BEATS = "NEWS  ·  EVENTS  ·  FOOD  ·  SPORTS  ·  WEATHER  ·  CULTURE"


def photo_data_uri() -> str | None:
    if not PHOTO.exists():
        return None
    with Image.open(PHOTO) as im:
        im = im.convert("RGB")
        target = W / H
        cw = im.width; ch = int(cw / target)
        top = max(0, int(im.height * 0.02))
        im = im.crop((0, top, cw, min(im.height, top + ch))).resize((W, H), Image.LANCZOS)
        tmp = OUT / "_photo.jpg"; im.save(tmp, quality=90)
    data = base64.b64encode(tmp.read_bytes()).decode(); tmp.unlink()
    return "data:image/jpeg;base64," + data


def banner_photo() -> str:
    d = DIRECTIONS[KEY]
    uri = photo_data_uri()
    body = f'<image href="{uri}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice"/>' if uri else ""
    body += ('<defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="{d["ink"]}" stop-opacity="0.96"/><stop offset="0.55" stop-color="{d["ink"]}" stop-opacity="0.72"/>'
             f'<stop offset="1" stop-color="{d["ink"]}" stop-opacity="0.25"/></linearGradient>'
             '<linearGradient id="vg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0.5" stop-color="{d["ink"]}" stop-opacity="0"/><stop offset="1" stop-color="{d["ink"]}" stop-opacity="0.7"/></linearGradient></defs>'
             f'<rect width="{W}" height="{H}" fill="url(#lg)"/><rect width="{W}" height="{H}" fill="url(#vg)"/>')
    b, lw, lh = lockup_body(KEY, d["paper"], d["accent"], d["ink"], mono_h=250)
    s = min(1.0, 980 / lw)
    x = SAFE_X0 + 20; y = 150
    body += g(b, x, y, s)
    body += text(x + 8, y + lh * s + 78, TAGLINE, 500, 40, d["paper"], 0.02, wdth=112)
    body += text(x + 8, y + lh * s + 130, f"{HANDLE}   ·   Fort Worth · Tarrant County · Arlington", 500, 28, "#D7D9E0", 0.04, wdth=100)
    body += text(SAFE_X1 - 10, H - 24, CREDIT, 500, 18, "#C7CAD2", 0.02, "end", wdth=100)
    return svg(W, H, body, bg=d["ink"])


def banner_type(dark: bool) -> str:
    d = DIRECTIONS[KEY]
    bg, fg, muted = (d["ink"], d["paper"], "#B9BCC6") if dark else (d["paper"], d["ink"], "#6B6F7A")
    b, lw, lh = lockup_body(KEY, fg, d["accent"], bg, mono_h=270)
    s = min(1.0, 1000 / lw)
    x = (W - lw * s) / 2; y = 130
    body = g(b, x, y, s)
    body += f'<rect x="{SAFE_X0 + 160}" y="{y + lh * s + 56}" width="{SAFE_X1 - SAFE_X0 - 320}" height="2" fill="{d["accent"]}"/>'
    body += text(W / 2, y + lh * s + 118, BEATS, 600, 28, fg, 0.18, "middle", wdth=100)
    body += text(W / 2, y + lh * s + 168, f"{HANDLE}   ·   {TAGLINE}", 500, 26, muted, 0.04, "middle", wdth=100)
    return svg(W, H, body, bg=bg)


def preview(names: list[str]) -> None:
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 22)
    rows = []
    for n in names:
        im = Image.open(OUT / f"{n}.png").convert("RGB")
        desk = im.resize((820, 312), Image.LANCZOS)
        mob = im.crop((SAFE_X0, 0, SAFE_X1, H)).resize((460, 259), Image.LANCZOS)
        row = Image.new("RGB", (820 + 460 + 60, 330), (235, 235, 232)); dr = ImageDraw.Draw(row)
        row.paste(desk, (0, 0)); row.paste(mob, (850, 0))
        dr.text((0, 316), f"{n}  ·  desktop", font=f, fill=(60, 60, 60)); dr.text((850, 316 - 50), "phone crop", font=f, fill=(60, 60, 60))
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows) + 20 * len(rows)), (235, 235, 232))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height + 20
    sheet.save(OUT / "preview.jpg", quality=88)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"cover-photo-1640x624": banner_photo(), "cover-charcoal-1640x624": banner_type(True), "cover-light-1640x624": banner_type(False)}
    paths = []
    for n, s in files.items():
        p = OUT / f"{n}.svg"; p.write_text(s, encoding="utf-8"); paths.append(str(p))
    subprocess.run(["node", str(ROOT / "scripts" / "render_svg_inline.js"), str(FONT_DIR), "1640", str(OUT), *paths], check=True, stdout=subprocess.DEVNULL)
    for png in OUT.glob("*-1640.png"):
        png.rename(OUT / png.name.replace("-1640.png", ".png"))
    for p in OUT.glob("*.svg"):
        p.unlink()
    preview(list(files))
    print("banners:", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
