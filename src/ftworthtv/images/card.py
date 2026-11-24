"""Render the branded photo card (real photo + headline overlay + 'FTW TV' badge) with Pillow."""
from __future__ import annotations

import colorsys
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DEFAULT_SIZE = (1080, 1350)


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def load_font(fonts_dir: Path, *, bold: bool = True, size: int = 64) -> ImageFont.FreeTypeFont:
    name = "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"
    path = Path(fonts_dir) / name
    if path.exists():
        return ImageFont.truetype(str(path), size=size)
    try:  # CI runners without our assets dir
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + center-crop to fill the canvas (like CSS object-fit: cover)."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    left = (resized.width - tw) // 2
    top = (resized.height - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def contain(img: Image.Image, size: tuple[int, int], bg: tuple[int, int, int]) -> Image.Image:
    """Fit the whole image inside the canvas (radar maps must not be cropped)."""
    tw, th = size
    scale = min((tw * 0.9) / img.width, (th * 0.62) / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", size, bg)
    # blurred, darkened copy of the image as the backdrop so the letterbox is not flat
    backdrop = cover(img, size).filter(ImageFilter.GaussianBlur(28))
    canvas.paste(Image.blend(backdrop, Image.new("RGB", size, bg), 0.55))
    canvas.paste(resized, ((tw - resized.width) // 2, int(th * 0.09)))
    return canvas


MOODS = {  # sky gradient stops top -> horizon, star count, lit-window probability, glow color
    "night":   {"stops": [(14, 18, 43), (28, 36, 80), (60, 54, 70)], "stars": 140, "windows": 0.35, "glow": (242, 177, 52)},
    "sunrise": {"stops": [(22, 36, 92), (120, 100, 140), (250, 160, 70)], "stars": 25, "windows": 0.12, "glow": (255, 210, 90)},
    "dusk":    {"stops": [(40, 20, 80), (130, 50, 110), (235, 110, 80)], "stars": 60, "windows": 0.3, "glow": (255, 140, 90)},
    "day":     {"stops": [(70, 130, 215), (140, 190, 240), (215, 230, 245)], "stars": 0, "windows": 0.0, "glow": (255, 255, 255)},
    "storm":   {"stops": [(30, 34, 48), (70, 76, 95), (120, 124, 135)], "stars": 0, "windows": 0.3, "glow": (200, 200, 210)},
}


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def placeholder_background(size: tuple[int, int], colors: dict, seed: str = "", mood: str = "night") -> Image.Image:
    """Sky gradient + Fort Worth-ish skyline silhouette. Used only when no licensed photo is available."""
    w, h = size
    m = MOODS.get(mood, MOODS["night"])
    stops = m["stops"]
    img = Image.new("RGB", size, stops[0])
    draw = ImageDraw.Draw(img)
    horizon = int(h * 0.68)
    for y in range(h):
        t = min(1.0, y / horizon)
        seg = t * (len(stops) - 1)
        i = min(int(seg), len(stops) - 2)
        draw.line([(0, y), (w, y)], fill=_lerp(stops[i], stops[i + 1], seg - i))
    rnd = random.Random(seed or "ftw")
    for _ in range(m["stars"]):
        x, y = rnd.randrange(w), rnd.randrange(int(h * 0.5))
        draw.ellipse([x, y, x + 2, y + 2], fill=(255, 255, 255))
    glow = Image.new("RGB", size, stops[-1])
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-w * 0.2, horizon - 90, w * 1.2, horizon + 320], fill=m["glow"])
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, glow, 0.3)
    draw = ImageDraw.Draw(img)
    building = (10, 12, 24) if mood in ("night", "dusk", "storm") else (38, 48, 78)
    x = -20
    while x < w + 20:  # skyline blocks
        bw = rnd.randrange(50, 150)
        bh = rnd.randrange(60, 380)
        top = horizon - bh
        draw.rectangle([x, top, x + bw, horizon + 40], fill=building)
        for wy in range(top + 18, horizon - 10, 26):  # lit windows
            for wx in range(x + 10, x + bw - 10, 22):
                if rnd.random() < m["windows"]:
                    draw.rectangle([wx, wy, wx + 8, wy + 10], fill=(255, 226, 150))
        x += bw + rnd.randrange(6, 26)
    draw.rectangle([0, horizon + 40, w, h], fill=(8, 9, 18) if mood in ("night", "dusk", "storm") else (24, 30, 50))
    return img


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    # a short last word alone on its line reads as a typo: Nov 24, "... high near" / "49". Take the word before it along.
    if len(lines) >= 2 and len(lines[-1]) <= 4 and " " not in lines[-1] and " " in lines[-2]:
        head, moved = lines[-2].rsplit(" ", 1)
        if draw.textlength(f"{moved} {lines[-1]}", font=font) <= max_width:
            lines[-2], lines[-1] = head, f"{moved} {lines[-1]}"
    return lines


def fit_headline(draw, text: str, fonts_dir: Path, max_width: int, max_lines: int, start: int = 92, minimum: int = 48):
    size = start
    while size >= minimum:
        font = load_font(fonts_dir, bold=True, size=size)
        lines = wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines and all(draw.textlength(l, font=font) <= max_width for l in lines):
            return font, lines
        size -= 6
    font = load_font(fonts_dir, bold=True, size=minimum)
    lines = wrap_text(draw, text, font, max_width)[:max_lines]
    if len(lines) == max_lines:
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return font, lines


def _pill(draw, xy, text, font, fill, text_fill, pad=(26, 14), radius=18):
    x, y = xy
    tw = draw.textlength(text, font=font)
    th = font.size
    box = [x, y, x + tw + pad[0] * 2, y + th + pad[1] * 2]
    draw.rounded_rectangle(box, radius=radius, fill=fill)
    draw.text((x + pad[0], y + pad[1] - th * 0.12), text, font=font, fill=text_fill)
    return box


def render_card(*, background: Path | None, headline: str, category_label: str, brand: dict, out_path: Path,
                fonts_dir: Path, source_line: str | None = None, photo_credit: str | None = None,
                subline: str | None = None, fit: str = "cover", size: tuple[int, int] | None = None,
                logo_path: Path | None = None, mood: str = "night") -> Path:
    colors = brand.get("colors", {}) or {}
    card_cfg = brand.get("card", {}) or {}
    size = tuple(size or card_cfg.get("size") or DEFAULT_SIZE)  # type: ignore[assignment]
    w, h = size
    primary, accent, text_col, muted = (_hex(colors.get(k, d)) for k, d in
                                        (("primary", "#14182B"), ("accent", "#F2B134"), ("text", "#FFFFFF"), ("muted", "#D7D9E0")))

    if background and Path(background).exists():
        with Image.open(background) as src:
            src = src.convert("RGB")
            base = contain(src, size, primary) if fit == "contain" else cover(src, size)
    else:
        base = placeholder_background(size, colors, seed=headline, mood=mood)

    # bottom gradient so white text always reads
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    grad_top = int(h * 0.34)
    for y in range(grad_top, h):
        t = (y - grad_top) / (h - grad_top)
        alpha = int(235 * (t ** 1.4))
        od.line([(0, y), (w, y)], fill=(*primary, alpha))
    od.rectangle([0, 0, w, int(h * 0.16)], fill=(0, 0, 0, 0))
    top_shade = Image.new("RGBA", size, (0, 0, 0, 0))
    td = ImageDraw.Draw(top_shade)
    for y in range(0, int(h * 0.2)):
        td.line([(0, y), (w, y)], fill=(0, 0, 0, int(120 * (1 - y / (h * 0.2)))))
    base = Image.alpha_composite(Image.alpha_composite(base.convert("RGBA"), top_shade), overlay)
    draw = ImageDraw.Draw(base)

    margin = int(w * 0.052)
    # --- badge + category pill (top-left), drawn on a transparent layer so translucent fills really blend ---
    y_top = margin
    ui = Image.new("RGBA", size, (0, 0, 0, 0))
    ud = ImageDraw.Draw(ui)
    if card_cfg.get("watermark", True):
        if logo_path and Path(logo_path).exists():
            with Image.open(logo_path) as logo:
                logo = logo.convert("RGBA")
                logo.thumbnail((int(w * 0.3), 96))
                ui.alpha_composite(logo, (margin, y_top))
                badge_right = margin + logo.width + 18
        else:
            badge_font = load_font(fonts_dir, bold=True, size=40)
            box = _pill(ud, (margin, y_top), brand.get("short_name", "FTW TV").upper(), badge_font, (*accent, 255), (*primary, 255))
            badge_right = int(box[2]) + 18
    else:
        badge_right = margin
    cat_font = load_font(fonts_dir, bold=True, size=30)
    _pill(ud, (badge_right, y_top + 5), category_label.upper(), cat_font, (*primary, 165), (*text_col, 255), pad=(22, 14), radius=16)
    base = Image.alpha_composite(base, ui)
    draw = ImageDraw.Draw(base)

    # --- text block (footer, headline, subline) on its own layers so the shadow blends properly ---
    text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)
    sdraw = ImageDraw.Draw(shadow_layer)

    def shadowed(xy, text, font, fill):
        sdraw.text((xy[0] + 3, xy[1] + 4), text, font=font, fill=(0, 0, 0, 190))
        tdraw.text(xy, text, font=font, fill=fill)

    foot_font = load_font(fonts_dir, bold=False, size=26)
    footer_y = h - margin - foot_font.size
    footer_lines = []
    if source_line and card_cfg.get("show_source_line", True):
        footer_lines.append(source_line)
    if photo_credit and card_cfg.get("show_photo_credit", True):
        footer_lines.append(photo_credit)
    footer_text = "   •   ".join(footer_lines)
    if footer_text:
        while tdraw.textlength(footer_text, font=foot_font) > w - 2 * margin and len(footer_text) > 20:
            footer_text = footer_text[:-4].rstrip() + "…"
        shadowed((margin, footer_y), footer_text, foot_font, (*muted, 255))

    max_width = w - 2 * margin
    head_font, lines = fit_headline(tdraw, headline, fonts_dir, max_width, max_lines=4)
    line_h = int(head_font.size * 1.12)
    block_h = line_h * len(lines)
    y = footer_y - 44 - block_h
    for line in lines:
        shadowed((margin, y), line, head_font, (*text_col, 255))
        y += line_h
    bar_y = footer_y - 44 - block_h - 34
    tdraw.rounded_rectangle([margin, bar_y, margin + 140, bar_y + 10], radius=5, fill=(*accent, 255))
    if subline:
        sub_font = load_font(fonts_dir, bold=True, size=32)
        sub = subline.upper()
        while tdraw.textlength(sub, font=sub_font) > max_width and len(sub) > 10:
            sub = sub[:-4].rstrip() + "…"
        shadowed((margin, bar_y - 20 - sub_font.size), sub, sub_font, (*accent, 255))

    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(6))
    base = Image.alpha_composite(base, shadow_layer)
    base = Image.alpha_composite(base, text_layer)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=90, optimize=True)
    return out_path


def render_plain(background: Path, out_path: Path, *, brand: dict, fonts_dir: Path, watermark: str | None = None,
                 max_side: int = 1440, min_side: int = 720) -> Path:
    """The photo as-is (own aspect ratio), like the Dallas page posts: no headline, no badge, just an optional small @handle."""
    with Image.open(background) as src:
        img = src.convert("RGB")
    w, h = img.size
    if min(w, h) < min_side:  # small agency photos (booking photos, radar) get upscaled so Facebook does not blur them
        scale = min_side / min(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    if watermark:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        font = load_font(fonts_dir, bold=True, size=max(22, int(img.width * 0.028)))
        tw = d.textlength(watermark, font=font)
        x, y = img.width - tw - int(img.width * 0.025), img.height - font.size - int(img.height * 0.025)
        d.text((x + 2, y + 2), watermark, font=font, fill=(0, 0, 0, 150))
        d.text((x, y), watermark, font=font, fill=(255, 255, 255, 215))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path


def _initials(name: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w[0].isalpha() and w.lower() not in ("of", "the", "and", "for", "at")]
    return "".join(w[0] for w in words[:3 if len(words) >= 3 else 2]).upper() or "FW"


def _avatar_color(name: str) -> tuple[int, int, int]:
    palette = [(24, 119, 242), (0, 150, 136), (233, 30, 99), (255, 112, 67), (103, 58, 183), (0, 131, 143), (121, 85, 72)]
    return palette[sum(map(ord, name)) % len(palette)]


def _quote_lines(draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Paragraphs are separated by a blank line. The first paragraph is always shown (cut with an ellipsis if it must be);
    later paragraphs are added only when they fit completely, so the card never ends mid-sentence."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return [""]
    def wrap_para(para: str) -> list[str]:
        out: list[str] = []
        for ln in para.split("\n"):
            out.extend(wrap_text(draw, ln, font, max_width) if ln.strip() else [""])
        return out
    lines = wrap_para(paras[0])
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    for para in paras[1:]:
        extra = wrap_para(para)
        if len(lines) + 1 + len(extra) <= max_lines:
            lines += [""] + extra
        else:
            break
    return lines


def render_quote_card(*, author: str, handle: str | None, when: str, text: str, photo: Path | None, out_path: Path, brand: dict,
                      fonts_dir: Path, watermark: str | None = None, footer: str | None = None,
                      size: tuple[int, int] | None = None, bold_first_line: bool = False) -> Path:
    """A post inside a post: the source's post (author, handle, text, photo) as a white card on a feed-colored background,
    the way a shared post looks. No platform logos, no badges, no invented like/comment counts.
    The canvas is 1080 wide; its height follows the card, between square (1080) and 4:5 (1350)."""
    W, H = tuple(size or (1080, 1350))
    bg, card, ink, muted, line = (240, 242, 245), (255, 255, 255), (5, 5, 5), (101, 103, 107), (228, 230, 235)
    margin, pad, radius = 54, 44, 30
    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)
    card_w = W - 2 * margin
    inner_w = card_w - 2 * pad

    name_font = load_font(fonts_dir, bold=True, size=40)
    sub_font = load_font(fonts_dir, bold=False, size=30)
    text_font = load_font(fonts_dir, bold=False, size=44)
    foot_font = load_font(fonts_dir, bold=False, size=26)

    photo_img = None
    if photo and Path(photo).exists():
        with Image.open(photo) as im:
            photo_img = im.convert("RGB")
    max_text_lines = 6 if photo_img is not None else 12
    bold_font = load_font(fonts_dir, bold=True, size=44)
    lines = _quote_lines(draw, text, text_font, inner_w, max_text_lines)
    line_h = int(text_font.size * 1.3)
    header_h = 104
    text_h = line_h * len(lines)
    footer_h = (foot_font.size + 28) if footer else 0
    photo_h = 0
    if photo_img is not None:
        avail = H - 2 * margin - 2 * pad - header_h - text_h - footer_h - 60
        max_photo_h = max(300, min(avail, int(H * 0.56)))
        scale = inner_w / photo_img.width
        natural_h = int(photo_img.height * scale)
        if natural_h <= max_photo_h:
            photo_img = photo_img.resize((inner_w, natural_h), Image.LANCZOS)
        else:
            # tall photo (a booking photo, a phone screenshot): never crop a face. Fit it inside the box on a blurred,
            # darkened copy of itself, the way TV news shows portraits.
            box = Image.new("RGB", (inner_w, max_photo_h))
            backdrop = cover(photo_img, (inner_w, max_photo_h)).filter(ImageFilter.GaussianBlur(28))
            backdrop = Image.blend(backdrop, Image.new("RGB", backdrop.size, (20, 22, 28)), 0.35)
            box.paste(backdrop, (0, 0))
            fit_scale = max_photo_h / photo_img.height
            fitted = photo_img.resize((max(1, int(photo_img.width * fit_scale)), max_photo_h), Image.LANCZOS)
            box.paste(fitted, ((inner_w - fitted.width) // 2, 0))
            photo_img = box
        photo_h = photo_img.height
    card_h = 2 * pad + header_h + text_h + (photo_h + 28 if photo_img is not None else 0) + footer_h
    card_h = min(card_h, H - 2 * margin)
    if size is None:  # tighten the canvas to the card: no big empty bands in the feed
        H = max(1080, min(1350, card_h + 2 * margin + 44))
        canvas = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(canvas)
    y0 = (H - card_h - 44) // 2
    x0 = margin

    # shadow + card
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0 + 6, y0 + 12, x0 + card_w + 6, y0 + card_h + 12], radius=radius, fill=(0, 0, 0, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=radius, fill=card, outline=line, width=2)

    # header: avatar + name + handle · time
    ax, ay = x0 + pad, y0 + pad
    draw.ellipse([ax, ay, ax + 88, ay + 88], fill=_avatar_color(author))
    init_font = load_font(fonts_dir, bold=True, size=34)
    tw = draw.textlength(_initials(author), font=init_font)
    draw.text((ax + 44 - tw / 2, ay + 44 - init_font.size * 0.58), _initials(author), font=init_font, fill=(255, 255, 255))
    name = author
    while draw.textlength(name, font=name_font) > inner_w - 110 and len(name) > 8:
        name = name[:-2].rstrip() + "…"
    draw.text((ax + 108, ay + 2), name, font=name_font, fill=ink)
    sub = " · ".join(x for x in (handle, when) if x)
    draw.text((ax + 108, ay + 52), sub, font=sub_font, fill=muted)

    # text
    ty = y0 + pad + header_h
    for i, ln in enumerate(lines):
        draw.text((x0 + pad, ty), ln, font=bold_font if (bold_first_line and i == 0) else text_font, fill=ink)
        ty += line_h

    # photo with rounded corners
    if photo_img is not None:
        py = ty + 20
        mask = Image.new("L", photo_img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo_img.width - 1, photo_img.height - 1], radius=22, fill=255)
        canvas.paste(photo_img, (x0 + pad, py), mask)
        ty = py + photo_img.height + 8

    if footer:
        draw.line([(x0 + pad, ty + 10), (x0 + card_w - pad, ty + 10)], fill=line, width=2)
        draw.text((x0 + pad, ty + 22), footer, font=foot_font, fill=muted)

    if watermark:
        wm_font = load_font(fonts_dir, bold=True, size=30)
        wtw = draw.textlength(watermark, font=wm_font)
        draw.text((W - wtw - margin, H - margin - wm_font.size), watermark, font=wm_font, fill=(140, 143, 150))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path


def _verified_badge(draw: ImageDraw.ImageDraw, x: int, cy: int, size: int) -> None:
    """A plain blue disc with a white check (no platform artwork)."""
    r = size // 2
    draw.ellipse([x, cy - r, x + size, cy + r], fill=(29, 155, 240))
    w = max(3, size // 9)
    pts = [(x + size * 0.28, cy + size * 0.02), (x + size * 0.44, cy + size * 0.20), (x + size * 0.74, cy - size * 0.20)]
    draw.line(pts, fill=(255, 255, 255), width=w, joint="curve")


def render_tweet_card(*, name: str, handle: str, headline: str, photo: Path | None, logo: Path | None, out_path: Path,
                      fonts_dir: Path, verified: bool = False, credit: str | None = None, width: int = 1200) -> Path:
    """Our own post, the way the Dallas Texas TV page posts media: a white card with our avatar, page name and @handle,
    a one-line news headline in plain type, then the photo with rounded corners. No date, no counts, no platform logo.
    Proportions are measured from their posts: ~13.5% side padding, headline ~3.2% of the width, 3:2 photo below."""
    W = width
    pad_x, pad_top, pad_bottom = int(W * 0.135), int(W * 0.03), int(W * 0.014)
    ink, muted, border, white = (15, 20, 25), (83, 100, 113), (207, 217, 222), (255, 255, 255)
    content_w = W - 2 * pad_x
    name_font = load_font(fonts_dir, bold=True, size=int(W * 0.0285))
    handle_font = load_font(fonts_dir, bold=False, size=int(W * 0.0245))
    head_font = load_font(fonts_dir, bold=False, size=int(W * 0.0315))
    credit_font = load_font(fonts_dir, bold=False, size=int(W * 0.018))
    avatar = int(W * 0.073)

    probe = ImageDraw.Draw(Image.new("RGB", (W, 8)))
    lines = wrap_text(probe, " ".join(headline.split()), head_font, content_w)
    if len(lines) > 4:
        lines = lines[:4]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    line_h = int(head_font.size * 1.36)
    head_y = pad_top + avatar + int(W * 0.040)
    photo_y = head_y + line_h * len(lines) + int(W * 0.037)

    photo_img = None
    if photo and Path(photo).exists():
        with Image.open(photo) as im:
            photo_img = im.convert("RGB")
        scale = content_w / photo_img.width
        natural_h = int(photo_img.height * scale)
        cap = int(content_w * 1.1)
        floor = int(content_w * 0.52)
        if natural_h < floor:      # a panorama would be a thin strip: crop it to 2:1 like a news site does
            photo_img = cover(photo_img, (content_w, floor))
        elif natural_h <= cap:
            photo_img = photo_img.resize((content_w, max(1, natural_h)), Image.LANCZOS)
        else:  # tall photo: contain on a blurred copy of itself, never crop a face
            box = cover(photo_img, (content_w, cap)).filter(ImageFilter.GaussianBlur(26))
            box = Image.blend(box, Image.new("RGB", box.size, (22, 24, 30)), 0.3)
            fs = cap / photo_img.height
            fitted = photo_img.resize((max(1, int(photo_img.width * fs)), cap), Image.LANCZOS)
            box.paste(fitted, ((content_w - fitted.width) // 2, 0))
            photo_img = box
    credit_h = (credit_font.size + int(W * 0.014)) if (credit and photo_img is not None) else 0
    H = photo_y + (photo_img.height if photo_img is not None else -int(W * 0.02)) + credit_h + pad_bottom

    canvas = Image.new("RGB", (W, H), white)
    draw = ImageDraw.Draw(canvas)
    # avatar
    ax, ay = pad_x, pad_top
    mask = Image.new("L", (avatar, avatar), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, avatar - 1, avatar - 1], fill=255)
    if logo and Path(logo).exists():
        with Image.open(logo) as lg:
            lg = lg.convert("RGBA").resize((avatar, avatar), Image.LANCZOS)
        flat = Image.new("RGB", (avatar, avatar), white)
        flat.paste(lg, (0, 0), lg)
        canvas.paste(flat, (ax, ay), mask)
    else:
        draw.ellipse([ax, ay, ax + avatar, ay + avatar], fill=(20, 24, 43))
        f = load_font(fonts_dir, bold=True, size=int(avatar * 0.4))
        tw = draw.textlength(_initials(name), font=f)
        draw.text((ax + avatar / 2 - tw / 2, ay + avatar / 2 - f.size * 0.58), _initials(name), font=f, fill=white)
    # name, badge, handle
    tx = ax + avatar + int(W * 0.02)
    draw.text((tx, ay + int(avatar * 0.02)), name, font=name_font, fill=ink)
    if verified:
        nw = draw.textlength(name, font=name_font)
        _verified_badge(draw, int(tx + nw + name_font.size * 0.3), int(ay + avatar * 0.02 + name_font.size * 0.58), int(name_font.size * 0.9))
    draw.text((tx, ay + int(avatar * 0.50)), handle, font=handle_font, fill=muted)
    # headline
    y = head_y
    for ln in lines:
        draw.text((pad_x, y), ln, font=head_font, fill=ink)
        y += line_h
    # photo with rounded corners and a hairline border
    if photo_img is not None:
        radius = int(W * 0.0175)
        m = Image.new("L", photo_img.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, photo_img.width - 1, photo_img.height - 1], radius=radius, fill=255)
        canvas.paste(photo_img, (pad_x, photo_y), m)
        draw.rounded_rectangle([pad_x, photo_y, pad_x + photo_img.width - 1, photo_y + photo_img.height - 1], radius=radius, outline=border, width=2)
        if credit:
            draw.text((pad_x, photo_y + photo_img.height + int(W * 0.008)), credit, font=credit_font, fill=muted)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=93, optimize=True)
    return out_path


def render_story(card: Path, out_path: Path, *, brand: dict, fonts_dir: Path, logo: Path | None = None) -> Path:
    """The same post as a 1080x1920 Story: our card on the brand's charcoal, with the page name on top and a
    'full story on our page' line at the bottom. Everything important sits inside the 250-1670 px band that
    Instagram's and Facebook's story overlays leave visible."""
    W, H = 1080, 1920
    colors = brand.get("colors", {}) or {}
    bg = _hex(colors.get("primary", "#26282E"))
    accent = _hex(colors.get("accent", "#2F5BFF"))
    paper = _hex(colors.get("text", "#F7F7F5"))
    muted = _hex(colors.get("muted", "#B9BCC6"))
    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)
    margin = 70
    # header: avatar, name, handle, a short accent bar (the identity's overbar)
    top = 270
    av = 112
    if logo and Path(logo).exists():
        with Image.open(logo) as lg:
            lg = lg.convert("RGBA").resize((av, av), Image.LANCZOS)
        mask = Image.new("L", (av, av), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, av - 1, av - 1], fill=255)
        canvas.paste(lg, (margin, top), mask)
    name_font = load_font(fonts_dir, bold=True, size=50)
    handle_font = load_font(fonts_dir, bold=False, size=36)
    draw.text((margin + av + 28, top + 4), brand.get("page_name", "Fort Worth Daily"), font=name_font, fill=paper)
    draw.text((margin + av + 28, top + 66), brand.get("instagram_handle") or brand.get("handle", ""), font=handle_font, fill=muted)
    draw.rounded_rectangle([margin, top + av + 34, margin + 180, top + av + 46], radius=6, fill=accent)
    # the card, fitted into the band below the header
    band_top, band_bottom = top + av + 90, 1610
    with Image.open(card) as im:
        im = im.convert("RGB")
        scale = min((W - 2 * margin + 20) / im.width, (band_bottom - band_top) / im.height)
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    radius = 30
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    x0 = (W - im.width) // 2
    y0 = band_top + (band_bottom - band_top - im.height) // 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0 + 8, y0 + 16, x0 + im.width + 8, y0 + im.height + 16], radius=radius, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.paste(shadow, (0, 0), shadow)
    canvas.paste(im, (x0, y0), mask)
    # footer
    foot_font = load_font(fonts_dir, bold=False, size=34)
    foot_bold = load_font(fonts_dir, bold=True, size=34)
    draw.text((margin, 1640), "Full story on our page", font=foot_font, fill=muted)
    handle = brand.get("instagram_handle") or brand.get("handle", "")
    tw = draw.textlength(handle, font=foot_bold)
    draw.text((W - margin - tw, 1640), handle, font=foot_bold, fill=paper)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=90, optimize=True)
    return out_path
