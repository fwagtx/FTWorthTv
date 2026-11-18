"""Generate the Fort Worth Texas TV brand kit into assets/brand/.

Everything is drawn with Pillow from the brand tokens below, so the kit is reproducible and free of third-party artwork:
logo marks (light / dark / gold), profile pictures, the horizontal wordmark, platform cover images at the sizes each
network asks for, Instagram highlight covers, a story template, a watermark for video, palette and type sheets, and a
contact sheet of all of it. Run: python scripts/make_brandkit.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "assets" / "brand"

# ---- brand tokens (mirrored in docs/BRAND_KIT.md) ----
NAVY = (20, 24, 43)        # #14182B  Fort Worth Navy  (backgrounds, mark on light)
GOLD = (242, 177, 52)      # #F2B134  Stockyards Gold  (accent only)
INK = (15, 20, 25)         # #0F1419  card text
GREY = (83, 100, 113)      # #536471  secondary text (handle, credits)
LINE = (207, 217, 222)     # #CFD9DE  hairlines
PAPER = (255, 255, 255)
FEED = (240, 242, 245)     # #F0F2F5  Facebook feed background
RED = (224, 36, 36)        # #E02424  only for the 🚨 class of posts, never for the logo

NAME = "Fort Worth Texas TV"
HANDLE = "@FortWorthTexasTV"
SHORT = "FTWTV"
TAGLINE = "The home of Fort Worth entertainment"


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")), size)


# ---- the skyline inside the screen: stylised Fort Worth (Burnett Plaza, Wells Fargo, The Tower, the courthouse) ----
SKYLINE = [  # (x, width, height, style) in fractions of the screen box
    (0.04, 0.09, 0.30, "box"), (0.15, 0.07, 0.46, "step"), (0.24, 0.10, 0.34, "box"), (0.36, 0.08, 0.62, "crown"),
    (0.46, 0.11, 0.50, "step"), (0.59, 0.06, 0.40, "box"), (0.67, 0.07, 0.72, "spire"), (0.76, 0.09, 0.36, "box"),
    (0.87, 0.05, 0.56, "dome"), (0.93, 0.05, 0.24, "box"),
]


def draw_skyline(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color, windows=None) -> None:
    x0, y0, x1, y1 = box
    W, H = x1 - x0, y1 - y0
    base = y1
    for x, w, h, style in SKYLINE:
        bx0, bx1, top = x0 + W * x, x0 + W * (x + w), base - H * h
        if style == "step":
            draw.rectangle([bx0, top + H * 0.08, bx1, base], fill=color)
            draw.rectangle([bx0 + (bx1 - bx0) * 0.25, top, bx1 - (bx1 - bx0) * 0.25, base], fill=color)
        elif style == "crown":   # pyramid roof
            draw.rectangle([bx0, top + H * 0.07, bx1, base], fill=color)
            draw.polygon([(bx0, top + H * 0.07), (bx1, top + H * 0.07), ((bx0 + bx1) / 2, top)], fill=color)
        elif style == "spire":
            draw.rectangle([bx0, top + H * 0.12, bx1, base], fill=color)
            draw.polygon([(bx0, top + H * 0.12), (bx1, top + H * 0.12), ((bx0 + bx1) / 2, top)], fill=color)
            cx = (bx0 + bx1) / 2
            draw.line([(cx, top), (cx, top - H * 0.08)], fill=color, width=max(1, int(W * 0.012)))
        elif style == "dome":    # courthouse clock tower
            draw.rectangle([bx0, top + H * 0.10, bx1, base], fill=color)
            draw.ellipse([bx0, top, bx1, top + H * 0.2], fill=color)
        else:
            draw.rectangle([bx0, top, bx1, base], fill=color)
        if windows and w >= 0.08:
            step = max(2, int(W * 0.045))
            for wy in range(int(top + H * 0.14), int(base - H * 0.05), step):
                for wx in range(int(bx0 + W * 0.02), int(bx1 - W * 0.02), step):
                    draw.rectangle([wx, wy, wx + W * 0.014, wy + W * 0.014], fill=windows)


LOGO_DIR = ROOT / "assets" / "brand" / "logo-options"
LOGO_CHOICE = "b-skyline"    # b-skyline | d-longhorn | e-courthouse | g-sign | a-horns | c-badge  (scripts/make_logo_options.py)


def mark(size: int, body, screen, city, ground, text: str | None, text_color, windows=None) -> Image.Image:
    """The brand mark on a transparent square. Uses the chosen vector logo (light / dark / mono, with or without the
    caption) when it has been rendered; otherwise falls back to the simple drawn TV."""
    way = "dark" if body == PAPER else ("mono" if body == INK else "light")
    custom = ROOT / "assets" / "brand" / "logo-custom.png"      # drop a designer's / ChatGPT logo here and it drives the kit
    if custom.exists():
        return custom_mark(custom, size, way)
    rendered = LOGO_DIR / f"{LOGO_CHOICE}-{way}-{'full' if text else 'mark'}-1024.png"
    if rendered.exists():
        with Image.open(rendered) as im:
            return im.convert("RGBA").resize((size, size), Image.LANCZOS)
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, top = S * 0.5, S * 0.06
    aw = int(S * 0.035)
    d.line([(cx, S * 0.22), (cx - S * 0.16, top)], fill=body, width=aw)
    d.line([(cx, S * 0.22), (cx + S * 0.16, top)], fill=body, width=aw)
    d.ellipse([cx - S * 0.035, S * 0.185, cx + S * 0.035, S * 0.255], fill=body)
    bx0, by0, bx1, by1 = S * 0.08, S * 0.22, S * 0.92, S * 0.74 if text else S * 0.88
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=int(S * 0.08), fill=body)
    inset = S * 0.04
    sx0, sy0, sx1, sy1 = bx0 + inset, by0 + inset, bx1 - inset, by1 - inset
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=int(S * 0.05), fill=screen)
    draw_skyline(d, (sx0 + S * 0.03, sy0 + S * 0.05, sx1 - S * 0.03, sy1 - S * 0.045), city, windows)
    d.rectangle([sx0 + S * 0.02, sy1 - S * 0.045, sx1 - S * 0.02, sy1 - S * 0.03], fill=ground)
    d.rectangle([S * 0.25, by1, S * 0.32, by1 + S * 0.04], fill=body)
    d.rectangle([S * 0.68, by1, S * 0.75, by1 + S * 0.04], fill=body)
    if text:
        f = font(True, int(S * 0.15))
        tw = d.textlength(text, font=f)
        d.text(((S - tw) / 2, S * 0.79), text, font=f, fill=text_color)
    return img


def custom_mark(path: Path, size: int, way: str) -> Image.Image:
    """A supplied square logo: near-white pixels become transparent; 'mono' turns it into a black silhouette;
    'dark' puts the colour art on a white disc so it still reads on navy."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    if all(px[x, y][3] == 255 for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))):   # opaque white background
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if min(r, g, b) > 238:
                    px[x, y] = (r, g, b, 0)
    side = max(w, h)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0)); sq.alpha_composite(im, ((side - w) // 2, (side - h) // 2))
    sq = sq.resize((size, size), Image.LANCZOS)
    if way == "mono":
        alpha = sq.getchannel("A")
        return Image.merge("RGBA", (Image.new("L", sq.size, 15), Image.new("L", sq.size, 20), Image.new("L", sq.size, 25), alpha))
    if way == "dark":
        disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse([0, 0, size - 1, size - 1], fill=PAPER)
        inner = sq.resize((int(size * 0.8), int(size * 0.8)), Image.LANCZOS)
        disc.alpha_composite(inner, (int(size * 0.1), int(size * 0.1)))
        return disc
    return sq


def circle_profile(size: int, bg, m: Image.Image, ring=None) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=bg, outline=ring, width=int(size * 0.02) if ring else 0)
    inner = int(size * 0.80)
    mm = m.resize((inner, inner), Image.LANCZOS)
    img.alpha_composite(mm, ((size - inner) // 2, (size - inner) // 2))
    return img


def spaced(d: ImageDraw.ImageDraw, xy, text, f, fill, spacing: float):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + spacing
    return x


def wordmark(width: int, color, accent, m: Image.Image, with_tagline=True) -> Image.Image:
    """Horizontal lockup: mark + FORT WORTH TEXAS TV (+ tagline), transparent background."""
    H = int(width * 0.30)
    img = Image.new("RGBA", (width, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ms = int(H * 0.86)
    img.alpha_composite(m.resize((ms, ms), Image.LANCZOS), (0, (H - ms) // 2))
    x = ms + int(width * 0.03)
    avail = width - x - int(width * 0.01)
    f1 = fit_font(d, "FORT WORTH", True, int(H * 0.33), avail, spacing=H * 0.02)
    y = int(H * 0.10) if with_tagline else int(H * 0.28)
    spaced(d, (x, y), "FORT WORTH", f1, color, H * 0.02)
    spaced(d, (x, y + int(f1.size * 1.12)), "TEXAS TV", f1, accent, H * 0.02)
    if with_tagline:
        f3 = fit_font(d, TAGLINE.upper(), False, int(H * 0.11), avail)
        d.text((x + 2, y + int(f1.size * 2.35)), TAGLINE.upper(), font=f3, fill=color)
    return img


def fit_font(d: ImageDraw.ImageDraw, text: str, bold: bool, size: int, max_width: int, spacing: float = 0.0) -> ImageFont.FreeTypeFont:
    """Largest font at or below `size` whose text (with letter spacing) fits in max_width."""
    while size > 8:
        f = font(bold, size)
        w = sum(d.textlength(ch, font=f) + spacing for ch in text)
        if w <= max_width:
            return f
        size -= 2
    return font(bold, size)


def cover(size: tuple[int, int], safe: tuple[int, int] | None, name: str) -> Image.Image:
    """Navy cover with a gold skyline line, the mark, the name and the handle, all inside the platform's safe area."""
    W, H = size
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    # soft glow + skyline silhouette along the bottom
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.2, H * 0.3, W * 0.8, H * 1.6], fill=(242, 177, 52, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(int(H * 0.12)))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    d = ImageDraw.Draw(img)
    draw_skyline(d, (W * 0.05, H * 0.42, W * 0.95, H * 0.985), (32, 38, 64), windows=(70, 60, 40))
    d.rectangle([0, H * 0.985, W, H], fill=GOLD)
    sw, sh = safe or size
    sx, sy = (W - sw) // 2, (H - sh) // 2
    m = mark(int(sh * 0.62), PAPER, NAVY, PAPER, GOLD, None, PAPER, windows=GOLD)
    mx = sx + int(sw * 0.05)
    img.alpha_composite(m, (mx, sy + int((sh - m.height) * 0.42)))
    tx = mx + m.width + int(sw * 0.03)
    avail = sx + sw - tx - int(sw * 0.03)          # everything stays inside the platform's safe area
    f1 = fit_font(d, "FORT WORTH", True, int(sh * 0.17), avail, spacing=sh * 0.012)
    f3 = fit_font(d, TAGLINE, False, int(sh * 0.075), avail)
    f4 = fit_font(d, f"{HANDLE}  ·  DM us your videos & photos", False, int(sh * 0.07), avail)
    ty = sy + int(sh * 0.20)
    spaced(d, (tx, ty), "FORT WORTH", f1, PAPER, sh * 0.012)
    spaced(d, (tx, ty + int(f1.size * 1.12)), "TEXAS TV", f1, GOLD, sh * 0.012)
    d.text((tx + 2, ty + int(f1.size * 2.45)), TAGLINE, font=f3, fill=(225, 228, 236))
    d.text((tx + 2, ty + int(f1.size * 2.45) + int(f3.size * 1.35)), f"{HANDLE}  ·  DM us your videos & photos", font=f4, fill=(170, 176, 196))
    return img.convert("RGB")


def highlight_cover(label: str) -> Image.Image:
    S = 1080
    img = Image.new("RGB", (S, S), NAVY)
    d = ImageDraw.Draw(img)
    d.ellipse([S * 0.08, S * 0.08, S * 0.92, S * 0.92], outline=GOLD, width=int(S * 0.012))
    m = mark(int(S * 0.34), PAPER, NAVY, PAPER, GOLD, None, PAPER)
    img.paste(m, ((S - m.width) // 2, int(S * 0.22)), m)
    f = font(True, int(S * 0.11))
    tw = d.textlength(label, font=f)
    d.text(((S - tw) / 2, S * 0.60), label, font=f, fill=GOLD)
    return img


def story_template(card: Path | None) -> Image.Image:
    """1080x1920: our post card on navy, logo + handle at the top. Used for Instagram / Facebook stories."""
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    pm = circle_profile(140, PAPER, mark(140, NAVY, PAPER, NAVY, GOLD, None, NAVY), ring=None)
    img.paste(pm, (60, 120), pm)
    d.text((220, 140), NAME, font=font(True, 44), fill=PAPER)
    d.text((220, 196), HANDLE, font=font(False, 36), fill=(170, 176, 196))
    if card and card.exists():
        with Image.open(card) as c:
            c = c.convert("RGB")
            cw = 980
            c = c.resize((cw, int(c.height * cw / c.width)), Image.LANCZOS)
        mask = Image.new("L", c.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, c.width - 1, c.height - 1], radius=28, fill=255)
        y = max(330, (H - c.height) // 2)
        img.paste(c, ((W - cw) // 2, y), mask)
    else:
        d.rounded_rectangle([50, 420, 1030, 1380], radius=28, fill=PAPER, outline=LINE)
        d.text((110, 480), "post card goes here", font=font(False, 40), fill=GREY)
    d.text((60, H - 150), "Full story in the post  ·  " + HANDLE, font=font(False, 34), fill=(170, 176, 196))
    return img


def palette_sheet() -> Image.Image:
    sw = [("Fort Worth Navy", "#14182B", NAVY), ("Stockyards Gold", "#F2B134", GOLD), ("Ink", "#0F1419", INK),
          ("Grey", "#536471", GREY), ("Hairline", "#CFD9DE", LINE), ("Paper", "#FFFFFF", PAPER), ("Feed", "#F0F2F5", FEED), ("Alert red (🚨 posts only)", "#E02424", RED)]
    W, cell = 1600, 200
    img = Image.new("RGB", (W, cell * len(sw) // 2 + 120), PAPER)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "Palette", font=font(True, 48), fill=INK)
    for i, (n, hx, c) in enumerate(sw):
        col, row = i % 2, i // 2
        x, y = 40 + col * 780, 110 + row * cell
        d.rounded_rectangle([x, y, x + 220, y + 160], radius=18, fill=c, outline=LINE)
        d.text((x + 250, y + 40), n, font=font(True, 36), fill=INK)
        d.text((x + 250, y + 92), hx, font=font(False, 32), fill=GREY)
    return img


def type_sheet() -> Image.Image:
    img = Image.new("RGB", (1600, 900), PAPER)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "Type", font=font(True, 48), fill=INK)
    d.text((40, 120), "Cards: system sans (Helvetica / Arial / Liberation Sans). Name bold 2.85% of width, handle regular 2.45%, headline regular 3.15%, line height 1.36.",
           font=font(False, 26), fill=GREY)
    d.text((40, 200), NAME, font=font(True, 56), fill=INK)
    d.text((40, 270), HANDLE, font=font(False, 48), fill=GREY)
    d.text((40, 360), "New Texas leaders say THC rules are a top priority for 2027", font=font(False, 62), fill=INK)
    d.text((40, 470), "Captions: plain sentences, sentence case, two short paragraphs, no hashtags on Facebook, at most one emoji (🚨 for incidents).",
           font=font(False, 26), fill=GREY)
    d.text((40, 560), "FORT WORTH", font=font(True, 110), fill=NAVY)
    d.text((40, 690), "TEXAS TV", font=font(True, 110), fill=GOLD)
    d.text((760, 620), "Wordmark: bold caps, 2% letter spacing, navy + gold.", font=font(False, 26), fill=GREY)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made: list[tuple[str, Image.Image]] = []

    m_light = mark(1024, NAVY, PAPER, NAVY, GOLD, SHORT, NAVY, windows=GOLD)         # navy mark for light backgrounds
    m_dark = mark(1024, PAPER, NAVY, PAPER, GOLD, SHORT, PAPER, windows=GOLD)         # white mark for dark backgrounds
    m_mono = mark(1024, INK, PAPER, INK, INK, SHORT, INK)                             # one-colour black (print, stamps)
    m_notext = mark(1024, NAVY, PAPER, NAVY, GOLD, None, NAVY, windows=GOLD)
    for name, im in (("logo-navy.png", m_light), ("logo-white.png", m_dark), ("logo-black.png", m_mono), ("logo-mark-only.png", m_notext)):
        im.save(OUT / name); made.append((name, im))

    prof_light = circle_profile(1024, PAPER, m_light, ring=NAVY)
    prof_dark = circle_profile(1024, NAVY, m_dark, ring=GOLD)
    prof_light.save(OUT / "profile-light-1024.png"); made.append(("profile-light-1024.png", prof_light))
    prof_dark.save(OUT / "profile-dark-1024.png"); made.append(("profile-dark-1024.png", prof_dark))
    prof_light.resize((400, 400), Image.LANCZOS).save(OUT / "profile-400.png")
    prof_light.resize((180, 180), Image.LANCZOS).save(OUT / "favicon-180.png")
    # the post-card avatar used by the pipeline
    prof_light.save(ROOT / "assets" / "logo.png")

    wm = wordmark(2400, NAVY, GOLD, m_notext)
    wm.save(OUT / "wordmark-navy.png"); made.append(("wordmark-navy.png", wm))
    wm_w = wordmark(2400, PAPER, GOLD, mark(1024, PAPER, NAVY, PAPER, GOLD, None, PAPER, windows=GOLD))
    dark_bg = Image.new("RGBA", wm_w.size, NAVY + (255,)); dark_bg.alpha_composite(wm_w)
    wm_w.save(OUT / "wordmark-white.png"); made.append(("wordmark-white.png", dark_bg))

    covers = {
        "cover-facebook-1640x624.png": ((1640, 624), (1100, 624)),      # phones show the centre 16:9 slice
        "cover-x-1500x500.png": ((1500, 500), (1350, 420)),
        "cover-youtube-2560x1440.png": ((2560, 1440), (1546, 423)),     # YouTube's "safe for all devices" box
        "cover-linkedin-1584x396.png": ((1584, 396), (1300, 340)),
    }
    for name, (size, safe) in covers.items():
        im = cover(size, safe, name); im.save(OUT / name); made.append((name, im))

    for label in ("NEWS", "EVENTS", "FOOD", "WEATHER", "SPORTS", "WANTED"):
        im = highlight_cover(label); im.save(OUT / f"highlight-{label.lower()}.png"); made.append((f"highlight-{label.lower()}.png", im))

    sample = next(iter(sorted((ROOT / "out").glob("tweet-renders/0*/post.jpg"))), None)
    st = story_template(sample); st.save(OUT / "story-template-1080x1920.png"); made.append(("story-template-1080x1920.png", st))

    # watermark for video / reels: handle on a soft pill
    wmk = Image.new("RGBA", (900, 160), (0, 0, 0, 0)); d = ImageDraw.Draw(wmk)
    d.rounded_rectangle([0, 0, 899, 159], radius=80, fill=(0, 0, 0, 110))
    pm = circle_profile(120, PAPER, m_notext); wmk.alpha_composite(pm, (20, 20))
    d.text((165, 46), HANDLE, font=font(True, 58), fill=PAPER)
    wmk.save(OUT / "watermark-handle.png"); made.append(("watermark-handle.png", Image.alpha_composite(Image.new("RGBA", wmk.size, (90, 90, 90, 255)), wmk)))

    ps = palette_sheet(); ps.save(OUT / "palette.png"); made.append(("palette.png", ps))
    ts = type_sheet(); ts.save(OUT / "type.png"); made.append(("type.png", ts))

    # contact sheet
    cols, cw = 4, 420
    tiles = []
    for name, im in made:
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (235, 235, 235, 255)); bg.alpha_composite(im); im = bg.convert("RGB")
        im.thumbnail((cw, cw)); tiles.append((name, im))
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * (cw + 24) + 24, rows * (cw + 64) + 24), (24, 25, 26))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(tiles):
        x, y = 24 + (i % cols) * (cw + 24), 24 + (i // cols) * (cw + 64)
        sheet.paste(im, (x + (cw - im.width) // 2, y + (cw - im.height) // 2))
        d.text((x, y + cw + 12), name, font=font(False, 22), fill=(200, 200, 200))
    sheet.save(OUT / "brand-kit-sheet.jpg", quality=88)
    print("wrote", len(made), "assets to", OUT)


if __name__ == "__main__":
    main()
