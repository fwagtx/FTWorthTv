"""Platform kit built from a chosen identity direction (default B, "The Overbar"): covers for Facebook, X, YouTube and
LinkedIn inside each network's safe zone, Instagram highlight covers, a story template, a handle watermark, the post-card
avatar (assets/logo.png), palette and type sheets and a contact sheet. Vector SVG rendered with the brand fonts.

    python scripts/make_brandkit_identity.py --direction B
Output: assets/brand/kit-<direction>/
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_identity import DIRECTIONS, FONT_DIR, ROOT, g, measure, mono_a, mono_b, mono_c, svg, wordmark  # noqa: E402

MONO = {"A": mono_a, "B": mono_b, "C": mono_c}
NAME, HANDLE, TAGLINE = "Fort Worth Daily", "@FortWorthDaily", "Fort Worth, every day."
SANS = "Archivo"


def lockup_body(key, ink, accent, paper, mono_h=300, gap=70, wm_h=None):
    """Monogram + wordmark side by side; returns (body, width, height)."""
    body, (w, h) = MONO[key](ink, accent)
    wm, (ww, wh) = wordmark(key, ink, accent, paper)
    inner = wm[wm.index(">") + 1:wm.rindex("</svg>")]
    ms = mono_h / h
    ws = (wm_h or mono_h * 0.9) / wh
    W = w * ms + gap + ww * ws
    H = max(h * ms, wh * ws)
    b = g(body, 0, (H - h * ms) / 2, ms) + g(inner, w * ms + gap, (H - wh * ws) / 2, ws)
    return b, W, H


def text(x, y, s, weight, size, fill, tracking=0.0, anchor="start", wdth=None):
    st = f' style="font-variation-settings:\'wdth\' {wdth}"' if wdth else ""
    ls = f' letter-spacing="{tracking * size:.1f}"' if tracking else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{SANS}, Inter, sans-serif" font-weight="{weight}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}"{ls}{st}>{s}</text>')


def cover(key, W, H, safe_w, safe_h, dark=True, handle_line=True):
    d = DIRECTIONS[key]
    bg, fg = (d["ink"], d["paper"]) if dark else (d["paper"], d["ink"])
    b, lw, lh = lockup_body(key, fg, d["accent"], bg, mono_h=safe_h * 0.52)
    s = min(1.0, (safe_w * 0.9) / lw)
    x = (W - lw * s) / 2
    y = (H - lh * s) / 2 - (safe_h * 0.06 if handle_line else 0)
    body = g(b, x, y, s)
    if handle_line:
        body += text(W / 2, y + lh * s + safe_h * 0.16, f"{HANDLE}   ·   {TAGLINE}", 500, int(safe_h * 0.075), fg, 0.06, "middle", wdth=112)
    return svg(W, H, body, bg=bg)


def highlight(key, label):
    d = DIRECTIONS[key]
    S = 1080
    body = f'<circle cx="540" cy="540" r="470" fill="none" stroke="{d["accent"]}" stroke-width="12"/>'
    mb, (w, h) = MONO[key](d["paper"], d["paper"])
    s = 330 / w
    body += g(mb, (S - w * s) / 2, 300, s)
    body += text(S / 2, 760, label, 900, 120, d["paper"], 0.02, "middle", wdth=70)
    return svg(S, S, body, bg=d["ink"])


def story(key, card: Path | None):
    d = DIRECTIONS[key]
    W, H = 1080, 1920
    mb, (w, h) = MONO[key](d["paper"], d["paper"])
    body = f'<circle cx="130" cy="190" r="70" fill="{d["paper"]}"/>'
    ib, (iw, ih) = MONO[key](d["ink"], d["ink"])
    s = 104 / iw
    body += g(ib, 130 - iw * s / 2, 190 - ih * s / 2, s)
    body += text(230, 180, NAME, 700, 46, d["paper"], 0.0, wdth=100)
    body += text(230, 232, HANDLE, 500, 34, "#B9BCC6", 0.02, wdth=100)
    if card and card.exists():
        import base64
        data = base64.b64encode(card.read_bytes()).decode()
        with Image.open(card) as im:
            cw, ch = im.size
        tw = 980; th = int(ch * tw / cw)
        y = max(330, (H - th) // 2)
        body += (f'<clipPath id="r"><rect x="50" y="{y}" width="{tw}" height="{th}" rx="28"/></clipPath>'
                 f'<image href="data:image/jpeg;base64,{data}" x="50" y="{y}" width="{tw}" height="{th}" clip-path="url(#r)"/>')
    else:
        body += f'<rect x="50" y="420" width="980" height="960" rx="28" fill="{d["paper"]}"/>'
    body += text(60, H - 130, "Full story in the post", 500, 34, "#B9BCC6", 0.02, wdth=100)
    body += text(W - 60, H - 130, HANDLE, 700, 34, d["paper"], 0.02, "end", wdth=100)
    return svg(W, H, body, bg=d["ink"])


def watermark(key):
    d = DIRECTIONS[key]
    W, H = 900, 160
    body = f'<rect width="{W}" height="{H}" rx="80" fill="{d["ink"]}" fill-opacity="0.78"/>'
    mb, (w, h) = MONO[key](d["paper"], d["paper"])
    s = 180 / w
    body += g(mb, 40, (H - h * s) / 2, s)
    body += text(250, 106, HANDLE, 700, 58, d["paper"], 0.0, wdth=100)
    return svg(W, H, body)


def sheets(out: Path, key: str):
    d = DIRECTIONS[key]
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf", 30)
    f2 = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 24)
    pal = Image.new("RGB", (1400, 360), (247, 247, 245)); dr = ImageDraw.Draw(pal)
    dr.text((40, 30), "Palette", font=f, fill=(30, 30, 30))
    for i, (n, hx) in enumerate((("Charcoal", d["ink"]), ("Off-white", d["paper"]), ("Electric blue", d["accent"]), ("Muted", "#B9BCC6"))):
        c = tuple(int(hx[j:j + 2], 16) for j in (1, 3, 5))
        x = 40 + i * 330
        dr.rounded_rectangle([x, 90, x + 200, 230], radius=18, fill=c, outline=(200, 200, 200))
        dr.text((x, 250), n, font=f, fill=(30, 30, 30)); dr.text((x, 290), hx, font=f2, fill=(110, 110, 110))
    pal.save(out / "palette.png")
    # contact sheet
    names = ["cover-facebook-1640x624.png", "cover-x-1500x500.png", "cover-youtube-2560x1440.png", "cover-linkedin-1584x396.png",
             "highlight-news.png", "highlight-events.png", "highlight-food.png", "highlight-weather.png", "highlight-sports.png", "highlight-wanted.png",
             "story-template-1080x1920.png", "watermark-handle.png", "avatar-1024.png", "palette.png"]
    tiles = []
    for n in names:
        p = out / n
        if not p.exists():
            continue
        im = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", im.size, (225, 225, 222, 255)); bg.alpha_composite(im)
        im = bg.convert("RGB"); im.thumbnail((430, 430)); tiles.append((n, im))
    cols, cw = 4, 430
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * (cw + 24) + 24, rows * (cw + 64) + 24), (24, 25, 26)); dr = ImageDraw.Draw(sheet)
    for i, (n, im) in enumerate(tiles):
        x, y = 24 + (i % cols) * (cw + 24), 24 + (i // cols) * (cw + 64)
        sheet.paste(im, (x + (cw - im.width) // 2, y + (cw - im.height) // 2))
        dr.text((x, y + cw + 12), n, font=f2, fill=(200, 200, 200))
    sheet.save(out / "kit-sheet.jpg", quality=88)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--direction", default="B")
    a = ap.parse_args()
    key = a.direction
    out = ROOT / "assets" / "brand" / f"kit-{key}"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*"):
        old.unlink()
    card = next(iter(sorted((ROOT / "out").glob("tweet-renders/0*/post.jpg"))), None)
    files = {
        "cover-facebook-1640x624": (cover(key, 1640, 624, 1100, 624), 1640),
        "cover-facebook-light-1640x624": (cover(key, 1640, 624, 1100, 624, dark=False), 1640),
        "cover-x-1500x500": (cover(key, 1500, 500, 1300, 420), 1500),
        "cover-youtube-2560x1440": (cover(key, 2560, 1440, 1546, 423, handle_line=False), 2560),
        "cover-linkedin-1584x396": (cover(key, 1584, 396, 1300, 340, handle_line=False), 1584),
        "story-template-1080x1920": (story(key, card), 1920),
        "watermark-handle": (watermark(key), 900),
    }
    for label in ("NEWS", "EVENTS", "FOOD", "WEATHER", "SPORTS", "WANTED"):
        files[f"highlight-{label.lower()}"] = (highlight(key, label), 1080)
    node = ROOT / "scripts" / "render_svg_inline.js"
    by_size: dict[int, list[str]] = {}
    for name, (s, size) in files.items():
        p = out / f"{name}.svg"; p.write_text(s, encoding="utf-8"); by_size.setdefault(size, []).append(str(p))
    for size, batch in by_size.items():
        subprocess.run(["node", str(node), str(FONT_DIR), str(size), str(out), *batch], check=True, stdout=subprocess.DEVNULL)
    for png in out.glob("*.png"):     # strip the "-<px>" suffix the renderer adds
        stem = png.stem
        for size in by_size:
            if stem.endswith(f"-{size}"):
                png.rename(out / f"{stem[: -len(str(size)) - 1]}.png"); break
    for p in out.glob("*.svg"):
        p.unlink()
    # the profile picture / post-card avatar
    src = ROOT / "assets" / "brand" / "identity" / "upload" / f"{key}-profile-1024.png"
    shutil.copy(src, out / "avatar-1024.png")
    shutil.copy(src, ROOT / "assets" / "logo.png")
    Image.open(src).resize((400, 400), Image.LANCZOS).save(out / "avatar-400.png")
    Image.open(src).resize((180, 180), Image.LANCZOS).save(out / "favicon-180.png")
    sheets(out, key)
    print("kit written to", out)


if __name__ == "__main__":
    main()
