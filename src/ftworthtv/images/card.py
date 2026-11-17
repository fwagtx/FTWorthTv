"""Render the branded photo card (real photo + headline overlay + 'FTW TV' badge) with Pillow."""
from __future__ import annotations

import colorsys
import random
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
    scale = min(tw / img.width, (th * 0.78) / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", size, bg)
    # blurred, darkened copy of the image as the backdrop so the letterbox is not flat
    backdrop = cover(img, size).filter(ImageFilter.GaussianBlur(28))
    canvas.paste(Image.blend(backdrop, Image.new("RGB", size, bg), 0.55))
    canvas.paste(resized, ((tw - resized.width) // 2, int(th * 0.08)))
    return canvas


def placeholder_background(size: tuple[int, int], colors: dict, seed: str = "") -> Image.Image:
    """Night-sky gradient + Fort Worth-ish skyline silhouette. Used only when no licensed photo is available."""
    w, h = size
    primary = _hex(colors.get("primary", "#14182B"))
    accent = _hex(colors.get("accent", "#F2B134"))
    img = Image.new("RGB", size, primary)
    draw = ImageDraw.Draw(img)
    hue, light, sat = colorsys.rgb_to_hls(*(c / 255 for c in primary))
    for y in range(h):
        t = y / h
        r, g, b = colorsys.hls_to_rgb(hue, max(0.03, light + 0.22 * (1 - t) - 0.08 * t), min(1, sat + 0.1))
        draw.line([(0, y), (w, y)], fill=(int(r * 255), int(g * 255), int(b * 255)))
    rnd = random.Random(seed or "ftw")
    for _ in range(140):  # stars
        x, y = rnd.randrange(w), rnd.randrange(int(h * 0.55))
        draw.ellipse([x, y, x + 2, y + 2], fill=(255, 255, 255, 180))
    horizon = int(h * 0.68)
    glow = Image.new("RGB", size, primary)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-w * 0.2, horizon - 90, w * 1.2, horizon + 320], fill=accent)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, glow, 0.35)
    draw = ImageDraw.Draw(img)
    x = -20
    while x < w + 20:  # skyline blocks
        bw = rnd.randrange(50, 150)
        bh = rnd.randrange(60, 380)
        top = horizon - bh
        draw.rectangle([x, top, x + bw, horizon + 40], fill=(10, 12, 24))
        for wy in range(top + 18, horizon - 10, 26):  # lit windows
            for wx in range(x + 10, x + bw - 10, 22):
                if rnd.random() < 0.35:
                    draw.rectangle([wx, wy, wx + 8, wy + 10], fill=(255, 226, 150))
        x += bw + rnd.randrange(6, 26)
    draw.rectangle([0, horizon + 40, w, h], fill=(8, 9, 18))
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
                logo_path: Path | None = None) -> Path:
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
        base = placeholder_background(size, colors, seed=headline)

    # bottom gradient so white text always reads
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    grad_top = int(h * 0.42)
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

    # --- footer: source + credit ---
    foot_font = load_font(fonts_dir, bold=False, size=26)
    footer_y = h - margin - foot_font.size
    footer_lines = []
    if source_line and card_cfg.get("show_source_line", True):
        footer_lines.append(source_line)
    if photo_credit and card_cfg.get("show_photo_credit", True):
        footer_lines.append(photo_credit)
    footer_text = "   •   ".join(footer_lines)
    if footer_text:
        while draw.textlength(footer_text, font=foot_font) > w - 2 * margin and len(footer_text) > 20:
            footer_text = footer_text[:-4].rstrip() + "…"
        draw.text((margin, footer_y), footer_text, font=foot_font, fill=muted)

    # --- headline block (bottom-left, above footer) ---
    max_width = w - 2 * margin
    head_font, lines = fit_headline(draw, headline, fonts_dir, max_width, max_lines=4)
    line_h = int(head_font.size * 1.12)
    block_h = line_h * len(lines)
    y = footer_y - 44 - block_h
    for line in lines:
        draw.text((margin, y), line, font=head_font, fill=text_col)
        y += line_h
    # accent bar + optional subline above the headline
    bar_y = footer_y - 44 - block_h - 34
    draw.rounded_rectangle([margin, bar_y, margin + 140, bar_y + 10], radius=5, fill=accent)
    if subline:
        sub_font = load_font(fonts_dir, bold=True, size=32)
        sub = subline.upper()
        while draw.textlength(sub, font=sub_font) > max_width and len(sub) > 10:
            sub = sub[:-4].rstrip() + "…"
        draw.text((margin, bar_y - 20 - sub_font.size), sub, font=sub_font, fill=accent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=90, optimize=True)
    return out_path
