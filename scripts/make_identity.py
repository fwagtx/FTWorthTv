"""FORT WORTH DAILY identity: three directions, each with a custom-drawn FWD monogram (geometry, not a typed font),
a typeset wordmark, a horizontal lockup, a profile mark and a black-and-white version, presented on boards.

  A  "The Daily D"     a high-contrast Didone D drawn from two offset ellipses, FW set small inside its counter
                       black / warm ivory / muted red; serif masthead
  B  "The Overbar"     F, W and D hang from one shared top bar: an overbar ligature where the bar is the F's arm,
                       the W's shoulder line and the D's top at once;  charcoal / electric blue; grotesque wordmark
  C  "The Stencil"     condensed slab-serif FWD with stencil breaks, the D cut from its stem;  forest green / cream;
                       condensed editorial wordmark

    python scripts/make_identity.py            # renders to assets/brand/identity/
Fonts: assets/fonts/brand/<family>/*.ttf (OFL, fetched by .github/workflows/fetch-fonts.yml); falls back to system faces.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand" / "identity"
FONT_DIR = ROOT / "assets" / "fonts" / "brand"


def have(family: str) -> bool:
    return any(FONT_DIR.rglob(f"{family}*.ttf")) or any(FONT_DIR.rglob(f"{family}*.otf"))


def fam(*choices: str) -> str:
    """First family that exists (by file stem prefix), else the last entry as a system fallback."""
    for c in choices[:-1]:
        if have(c):
            return c
    return choices[-1]


DIRECTIONS = {
    "A": dict(name="The Daily D", ink="#141414", paper="#F3EEE3", accent="#B23A2E",
              serif=fam("BodoniModa", "PlayfairDisplay", "Bitstream Charter"), sans=fam("Archivo", "Inter Display")),
    "B": dict(name="The Overbar", ink="#26282E", paper="#F7F7F5", accent="#2F5BFF",
              serif=None, sans=fam("BricolageGrotesque", "SpaceGrotesk", "Inter Display")),
    "C": dict(name="The Stencil", ink="#163A2C", paper="#F2EBDD", accent="#163A2C",
              serif=fam("Fraunces", "PlayfairDisplay", "Bitstream Charter"), sans=fam("BigShouldersDisplay", "Archivo", "Inter Display")),
}


def svg(w, h, body, bg=None):
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{rect}{body}</svg>'


def g(body, x=0.0, y=0.0, s=1.0):
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({s:.4f})">{body}</g>'


def rect(x, y, w, h, fill):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"/>'


def poly(pts, fill):
    return '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f'" fill="{fill}"/>'


def stroke_poly(pts, w, color):
    return ('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
            f'" fill="none" stroke="{color}" stroke-width="{w:.1f}" stroke-linejoin="miter" stroke-miterlimit="8" stroke-linecap="butt"/>')


def w_poly(x, top, bottom, wh, widths, fill):
    """A W as four parallelogram strokes with horizontal terminals. widths = (outer stroke run, inner stroke run) in x;
    wh = horizontal thickness of a stroke. Returns the union as overlapping polygons (same fill)."""
    outer, inner = widths
    mid_top = top + (bottom - top) * 0.36
    p1 = [(x, top), (x + wh, top), (x + outer + wh, bottom), (x + outer, bottom)]
    x2 = x + outer
    p2 = [(x2, bottom), (x2 + wh, bottom), (x2 + inner + wh, mid_top), (x2 + inner, mid_top)]
    x3 = x2 + inner
    p3 = [(x3, mid_top), (x3 + wh, mid_top), (x3 + inner + wh, bottom), (x3 + inner, bottom)]
    x4 = x3 + inner
    p4 = [(x4, bottom), (x4 + wh, bottom), (x4 + outer + wh, top), (x4 + outer, top)]
    return "".join(poly(q, fill) for q in (p1, p2, p3, p4)), x4 + outer + wh


# =====================================================================================================  A  The Daily D
def mono_a(ink, accent, detail_fill=None):
    """Box 760 x 700. A Didone D: thick stem, hairline top and bottom, swelling bowl (outer ellipse vs. an inner ellipse
    shifted left), with F W drawn as small geometric caps inside the counter."""
    H = 700
    stem = 150
    cx, rx, cy, ry = 300, 400, 350, 350          # outer bowl: straight top/bottom until cx, then the half-ellipse
    hair = 24                                    # hairline thickness at top and bottom
    d_shift, t_right = 60, 95                    # the counter sits further left: right side swells to d_shift + t_right
    icx, irx, iry = cx - d_shift, rx - t_right, ry - hair
    outer = (f"M 0 0 H {cx} A {rx} {ry} 0 0 1 {cx} {H} H 0 Z")
    inner = (f"M {stem} {hair} H {icx} A {irx} {iry} 0 0 1 {icx} {H - hair} H {stem} Z")
    body = f'<path d="{outer} {inner}" fill="{ink}" fill-rule="evenodd"/>'
    # F W inside the counter: geometric caps, stroke 20, cap height 150, letter-spaced
    fw = detail_fill or accent
    s, ch = 26, 150
    ox, oy = 222, cy - ch / 2
    body += rect(ox, oy, s, ch, fw) + rect(ox, oy, 96, s, fw) + rect(ox, oy + 64, 76, s, fw)             # F
    wpoly, _ = w_poly(ox + 128, oy, oy + ch, 30, (34, 30), fw)                                             # W
    body += wpoly
    return body, (760, 700)


# =====================================================================================================  B  The Overbar
def mono_b(ink, accent):
    """Box 1010 x 500, unit 100, stroke 100. One bar across the top is the F's arm, the W's shoulders and the D's top."""
    u = 100
    body = rect(0, 0, 8.0 * u, u, ink)                                   # the shared bar (to where the D's bowl begins)
    body += rect(0, 0, u, 5 * u, ink)                                    # F stem
    body += rect(u, 2.1 * u, 1.35 * u, 0.9 * u, ink)                     # F middle arm
    wpoly, _ = w_poly(2.75 * u, u, 5 * u, 0.9 * u, (0.95 * u, 0.85 * u), ink)                           # W hangs from the bar
    body += wpoly
    body += rect(7.0 * u, 0, u, 5 * u, ink)                              # D stem
    body += (f'<path d="M {8.0 * u} 0 A {2.5 * u} {2.5 * u} 0 0 1 {8.0 * u} {5 * u} H {7.0 * u} V {4 * u} H {8.0 * u} '
             f'A {1.5 * u} {1.5 * u} 0 0 0 {8.0 * u} {u} H {7.0 * u} V 0 Z" fill="{ink}"/>')          # D bowl
    return body, (10.5 * u, 5 * u)


# =====================================================================================================  C  The Stencil
def mono_c(ink, accent):
    """Box 880 x 500: condensed slab FWD with stencil breaks. Unit 100, stroke 0.95u, slab serifs 0.5u beyond the stem."""
    u = 100
    s, gap = 0.95 * u, 0.22 * u
    out = []
    # F ---------------------------------------------------------------- x 0 .. 2.6
    out.append(rect(0.45 * u, 0, s, 5 * u, ink))                                           # stem
    out.append(rect(0, 4.3 * u, 1.85 * u, 0.7 * u, ink))                                   # foot serif
    out.append(rect(0.45 * u + s + gap, 0, 1.3 * u, 0.8 * u, ink))                         # top arm (stencil gap from the stem)
    out.append(rect(0.45 * u + s + gap + 1.3 * u - 0.5 * u, 0, 0.5 * u, 1.5 * u, ink))     # arm's slab
    out.append(rect(0.45 * u + s + gap, 2.15 * u, 1.05 * u, 0.8 * u, ink))                 # middle arm
    # W ---------------------------------------------------------------- x 2.95 .. 6.55
    wx = 2.95 * u
    wpoly, wend = w_poly(wx + 0.25 * u, 0.0, 5 * u, 0.95 * u, (0.75 * u, 0.62 * u), ink)
    out.append(wpoly)
    out.append(rect(wx, 0, 1.45 * u, 0.7 * u, ink))                                        # top slab serifs
    out.append(rect(wend - 1.45 * u, 0, 1.45 * u, 0.7 * u, ink))
    # D ---------------------------------------------------------------- x 6.95 .. 8.8
    dx = 6.95 * u
    out.append(rect(dx + 0.45 * u, 0, s, 5 * u, ink))                                      # stem
    out.append(rect(dx, 0, 1.85 * u, 0.7 * u, ink))                                        # head serif
    out.append(rect(dx, 4.3 * u, 1.85 * u, 0.7 * u, ink))                                  # foot serif
    bx = dx + 0.45 * u + s + gap                                                           # bowl starts after a stencil gap
    out.append(f'<path d="M {bx} 0 H {bx + 0.2 * u} A {1.65 * u} {2.5 * u} 0 0 1 {bx + 0.2 * u} {5 * u} H {bx} V {4.2 * u} H {bx + 0.1 * u} '
               f'A {0.75 * u} {1.7 * u} 0 0 0 {bx + 0.1 * u} {0.8 * u} H {bx} Z" fill="{ink}"/>')
    return "".join(out), (8.8 * u, 5 * u)


# =====================================================================================================  wordmarks
def text(x, y, s, family, weight, size, fill, tracking_em=0.0, anchor="start", italic=False, extra=""):
    ls = f' letter-spacing="{tracking_em * size:.1f}"' if tracking_em else ""
    st = ' font-style="italic"' if italic else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}, serif" font-weight="{weight}" font-size="{size:.1f}" '
            f'fill="{fill}" text-anchor="{anchor}"{ls}{st} {extra}>{s}</text>')


def measure(text_, family: str, size: float, axes=None, tracking_em: float = 0.0) -> float:
    """Advance width of text in a brand font (variable axes set in the file's axis order), for layout."""
    files = sorted(FONT_DIR.rglob(f"{family}[[]*.ttf")) or sorted(FONT_DIR.rglob(f"{family}*.ttf"))
    if not files:
        return len(text_) * size * 0.6
    f = ImageFont.truetype(str(files[0]), int(size))
    if axes:
        try:
            f.set_variation_by_axes(list(axes))
        except Exception:
            pass
    return f.getlength(text_) + tracking_em * size * (len(text_) - 1)


def wordmark(key, ink, accent, paper, bw=False):
    d = DIRECTIONS[key]
    col = ink
    acc = ink if bw else accent
    if key == "A":   # masthead: "Fort Worth" italic over DAILY in black Didone caps, hairline rules
        W, H = 1500, 600
        b = rect(0, 60, W, 6, col) + rect(0, 478, W, 6, col)
        b += text(W / 2, 215, "Fort Worth", d["serif"], 500, 118, col, 0.02, "middle", italic=True)
        b += text(W / 2, 440, "DAILY", d["serif"], 900, 262, col, 0.06, "middle")
        b += text(W / 2, 548, "INDEPENDENT · FORT WORTH, TEXAS", d["sans"], 600, 26, acc, 0.32, "middle")
        return svg(W, H, b), (W, H)
    if key == "B":   # one line, heavy condensed grotesque, the word DAILY in the accent
        # width contrast: FORT WORTH wide and light, DAILY condensed and black, same cap height, one baseline
        wide = fam("Archivo", d["sans"])
        size = 200
        w1 = measure("FORT WORTH", "Archivo", size, (125, 600), 0.10)
        w2 = measure("DAILY", "Archivo", size, (62, 900), -0.01)
        gap = 115
        W, H = int(w1 + gap + w2 + 20), 300
        b = text(0, 236, "FORT WORTH", wide, 600, size, col, 0.10, "start", extra="style=\"font-variation-settings:'wdth' 125\"")
        b += text(w1 + gap, 236, "DAILY", wide, 900, size, acc, -0.01, "start", extra="style=\"font-variation-settings:'wdth' 62\"")
        return svg(W, H, b), (W, H)
    # C: stacked condensed caps, very tight leading, a soft serif "Fort Worth" line above
    W, H = 1200, 700
    b = text(W / 2, 150, "Fort Worth", d["serif"], 600, 128, col, 0.0, "middle", italic=True)
    b += rect(W / 2 - 300, 186, 600, 8, acc)
    b += text(W / 2, 620, "DAILY", d["sans"], 900, 470, col, 0.02, "middle")
    return svg(W, H, b), (W, H)


def monogram_svg(key, ink, accent, bw=False):
    fn = {"A": mono_a, "B": mono_b, "C": mono_c}[key]
    body, (w, h) = fn(ink, ink if bw else accent)
    pad = 90
    return svg(w + 2 * pad, h + 2 * pad, g(body, pad, pad)), (w, h)


def profile_svg(key, ink, accent, paper, bw=False):
    """Profile mark: the monogram on a disc, sized to stay readable at 32 px."""
    fn = {"A": mono_a, "B": mono_b, "C": mono_c}[key]
    fg, bg = (paper, ink)
    body, (w, h) = fn(fg, fg if bw else accent)
    S = 1000
    inner = {"A": 740, "B": 860, "C": 720}[key]
    s = min(inner / w, inner / h)
    body = f'<circle cx="500" cy="500" r="490" fill="{bg}"/>' + g(body, 500 - w * s / 2, 500 - h * s / 2, s)
    return svg(S, S, body)


def lockup_svg(key, ink, accent, paper, bw=False):
    fn = {"A": mono_a, "B": mono_b, "C": mono_c}[key]
    body, (w, h) = fn(ink, ink if bw else accent)
    wm, (ww, wh) = wordmark(key, ink, accent, paper, bw)
    inner = wm[wm.index(">") + 1:wm.rindex("</svg>")]
    H = 700
    ms = 520 / h
    W = int(w * ms + 120 + ww * (560 / wh) + 60)
    b = g(body, 0, (H - h * ms) / 2, ms) + g(inner, w * ms + 120, (H - wh * (560 / wh)) / 2, 560 / wh)
    return svg(W, H, b)


def board(key, parts):
    """One presentation board per direction, on a neutral background with generous spacing."""
    d = DIRECTIONS[key]
    bgc = (238, 236, 231)
    W, H = 2400, 1500
    im = Image.new("RGB", (W, H), bgc)
    dr = ImageDraw.Draw(im)
    label = ImageFont.truetype("/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf", 30)
    small = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 22)
    dr.text((80, 60), f"DIRECTION {key}  ·  {d['name'].upper()}", font=label, fill=(40, 40, 40))
    dr.text((80, 104), f"{d['ink']}  {d['paper']}  {d['accent']}   ·   {d['serif'] or '—'} / {d['sans']}", font=small, fill=(120, 120, 120))
    def place(name, box, bg=None, fit="contain"):
        x, y, w, h = box
        if bg:
            dr.rounded_rectangle([x, y, x + w, y + h], radius=24, fill=bg)
        p = Image.open(parts[name]).convert("RGBA")
        p.thumbnail((w - 60, h - 60), Image.LANCZOS)
        im.paste(p, (x + (w - p.width) // 2, y + (h - p.height) // 2), p)
    paper = tuple(int(d["paper"][i:i + 2], 16) for i in (1, 3, 5))
    ink = tuple(int(d["ink"][i:i + 2], 16) for i in (1, 3, 5))
    place("mono", (80, 170, 760, 620), paper)
    dr.text((80, 800), "1  Primary monogram", font=small, fill=(90, 90, 90))
    place("wordmark", (880, 170, 1440, 620), paper)
    dr.text((880, 800), "2  Wordmark", font=small, fill=(90, 90, 90))
    place("lockup", (80, 860, 1440, 400), paper)
    dr.text((80, 1270), "3  Horizontal lockup", font=small, fill=(90, 90, 90))
    place("profile", (1560, 860, 360, 400), None)
    dr.text((1560, 1270), "4  Profile mark", font=small, fill=(90, 90, 90))
    place("profile_bw", (1960, 860, 360, 400), None)
    dr.text((1960, 1270), "5  Black and white", font=small, fill=(90, 90, 90))
    # tiny avatars under the profile mark
    av = Image.open(parts["profile"]).convert("RGBA")
    x = 1560
    for sz in (96, 48, 32):
        a = av.resize((sz, sz), Image.LANCZOS); im.paste(a, (x, 1330), a); x += sz + 24
    bw = Image.open(parts["mono_bw"]).convert("RGBA"); bw.thumbnail((600, 120), Image.LANCZOS)
    im.paste(bw, (1760 - bw.width // 2 + 200, 1330), bw)
    im.save(OUT / f"board-{key}.jpg", quality=92)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.is_file():
            old.unlink()
    svgs = []
    for key, d in DIRECTIONS.items():
        ink, paper, accent = d["ink"], d["paper"], d["accent"]
        files = {
            f"{key}-mono.svg": monogram_svg(key, ink, accent)[0],
            f"{key}-mono-bw.svg": monogram_svg(key, "#111111", "#111111", bw=True)[0],
            f"{key}-wordmark.svg": wordmark(key, ink, accent, paper)[0],
            f"{key}-wordmark-bw.svg": wordmark(key, "#111111", "#111111", "#FFFFFF", bw=True)[0],
            f"{key}-lockup.svg": lockup_svg(key, ink, accent, paper),
            f"{key}-lockup-bw.svg": lockup_svg(key, "#111111", "#111111", "#FFFFFF", bw=True),
            f"{key}-profile.svg": profile_svg(key, ink, accent, paper),
            f"{key}-profile-bw.svg": profile_svg(key, "#111111", "#111111", "#FFFFFF", bw=True),
        }
        for n, s in files.items():
            (OUT / n).write_text(s, encoding="utf-8"); svgs.append(str(OUT / n))
    subprocess.run(["node", str(ROOT / "scripts" / "render_svg_inline.js"), str(FONT_DIR), "1600", str(OUT), *svgs], check=True)
    for key in DIRECTIONS:
        parts = {"mono": OUT / f"{key}-mono-1600.png", "mono_bw": OUT / f"{key}-mono-bw-1600.png", "wordmark": OUT / f"{key}-wordmark-1600.png",
                 "lockup": OUT / f"{key}-lockup-1600.png", "profile": OUT / f"{key}-profile-1600.png", "profile_bw": OUT / f"{key}-profile-bw-1600.png"}
        board(key, parts)
    boards = [Image.open(OUT / f"board-{k}.jpg") for k in DIRECTIONS]
    sheet = Image.new("RGB", (boards[0].width, sum(b.height for b in boards) + 40 * (len(boards) - 1)), (225, 223, 218))
    y = 0
    for b in boards:
        sheet.paste(b, (0, y)); y += b.height + 40
    sheet.save(OUT / "identity-overview.jpg", quality=88)
    print("boards written to", OUT)


if __name__ == "__main__":
    main()
