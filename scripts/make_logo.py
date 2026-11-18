"""Draw the page avatar used on post cards: a TV set with the Fort Worth skyline on screen and the short name under it.
Replace assets/logo.png with your real logo any time (square PNG, transparent or white background)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
NAVY, GOLD, WHITE = (20, 24, 43), (242, 177, 52), (255, 255, 255)


def draw_logo(size: int = 1024, text: str = "FTWTV") -> Image.Image:
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, S - 1, S - 1], fill=WHITE, outline=NAVY, width=int(S * 0.022))
    # antennae
    cx, top = S * 0.5, S * 0.17
    d.line([(cx, S * 0.30), (cx - S * 0.13, top)], fill=NAVY, width=int(S * 0.03))
    d.line([(cx, S * 0.30), (cx + S * 0.13, top)], fill=NAVY, width=int(S * 0.03))
    d.ellipse([cx - S * 0.03, S * 0.27, cx + S * 0.03, S * 0.33], fill=NAVY)
    # TV body + screen
    bx0, by0, bx1, by1 = S * 0.17, S * 0.30, S * 0.83, S * 0.72
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=int(S * 0.07), fill=NAVY)
    sx0, sy0, sx1, sy1 = bx0 + S * 0.035, by0 + S * 0.035, bx1 - S * 0.035, by1 - S * 0.035
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=int(S * 0.045), fill=WHITE)
    # skyline silhouette (Fort Worth-ish: a stepped tower, a pointed one, blocks), gold ground line
    base = sy1 - S * 0.03
    towers = [(0.05, 0.12, 0.22), (0.19, 0.08, 0.30), (0.29, 0.10, 0.18), (0.41, 0.07, 0.36), (0.50, 0.09, 0.26), (0.61, 0.06, 0.22), (0.69, 0.11, 0.31), (0.82, 0.07, 0.16)]
    sw = sx1 - sx0
    for x, w, h in towers:
        x0, x1 = sx0 + sw * x, sx0 + sw * (x + w)
        y0 = base - S * h
        d.rectangle([x0, y0, x1, base], fill=NAVY)
        if w >= 0.09:  # a few lit windows
            for wy in range(int(y0 + S * 0.03), int(base - S * 0.02), int(S * 0.035)):
                for wx in range(int(x0 + S * 0.02), int(x1 - S * 0.02), int(S * 0.035)):
                    d.rectangle([wx, wy, wx + S * 0.012, wy + S * 0.012], fill=GOLD)
    # pointed spire on the tallest tower
    tx0, tw, th = towers[3][0], towers[3][1], towers[3][2]
    px0, px1 = sx0 + sw * tx0, sx0 + sw * (tx0 + tw)
    d.polygon([(px0, base - S * th), (px1, base - S * th), ((px0 + px1) / 2, base - S * th - S * 0.05)], fill=NAVY)
    d.rectangle([sx0, base, sx1, base + S * 0.012], fill=GOLD)
    # legs + name
    d.rectangle([S * 0.30, by1, S * 0.36, by1 + S * 0.035], fill=NAVY)
    d.rectangle([S * 0.64, by1, S * 0.70, by1 + S * 0.035], fill=NAVY)
    font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "LiberationSans-Bold.ttf"), int(S * 0.12))
    tw_ = d.textlength(text, font=font)
    d.text(((S - tw_) / 2, S * 0.765), text, font=font, fill=NAVY)
    return img


if __name__ == "__main__":
    out = ROOT / "assets" / "logo.png"
    draw_logo(1024).save(out)
    print("wrote", out)
