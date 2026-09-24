"""Post image designs for the daily blessing. Each style renders a 1080x1080 PNG.

Preview all styles:  python designs.py
"""
import functools
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1080
FONT_DIRS = ["C:/Windows/Fonts", str(Path(__file__).resolve().parent / "fonts"), "/usr/share/fonts",
             "/usr/share/texmf/fonts", "/usr/local/share/fonts"]

# Windows fonts the styles were designed with -> open-licence substitutes on Linux
# (apt: fonts-noto-core fonts-crosextra-caladea fonts-texgyre). Same role, close metrics.
SUBSTITUTES = {
    "georgia.ttf": "NotoSerif-Regular.ttf", "georgiab.ttf": "NotoSerif-Bold.ttf",
    "georgiai.ttf": "NotoSerif-Italic.ttf",
    "segoeui.ttf": "NotoSans-Regular.ttf", "segoeuib.ttf": "NotoSans-Bold.ttf",
    # Ubuntu's fonts-noto-core has no Light weight; Regular is the nearest installed.
    "segoeuil.ttf": ("NotoSans-Light.ttf", "NotoSans-Regular.ttf"),
    "segoeuisl.ttf": ("NotoSans-Light.ttf", "NotoSans-Regular.ttf"),
    "seguisym.ttf": "NotoSansSymbols2-Regular.ttf",
    "pala.ttf": "texgyrepagella-regular.otf", "palab.ttf": "texgyrepagella-bold.otf",
    "palai.ttf": "texgyrepagella-italic.otf",
    "cambria.ttc": "Caladea-Regular.ttf", "cambriab.ttf": "Caladea-Bold.ttf", "cambriai.ttf": "Caladea-Italic.ttf",
    "constan.ttf": "Caladea-Regular.ttf", "constanb.ttf": "Caladea-Bold.ttf", "constani.ttf": "Caladea-Italic.ttf",
    "Gabriola.ttf": "texgyrechorus-mediumitalic.otf",
}


@functools.lru_cache(maxsize=None)
def font_path(name):
    """Full path of `name` or its Linux substitute. Raises instead of falling back to
    Pillow's tiny bitmap font, so a missing font fails the run rather than the post."""
    subs = SUBSTITUTES.get(name, ())
    candidates = [name] + ([subs] if isinstance(subs, str) else list(subs))  # in order of preference
    found = {}
    for root in FONT_DIRS:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                found.setdefault(f.lower(), os.path.join(dirpath, f))
    for candidate in candidates:
        if candidate.lower() in found:
            return found[candidate.lower()]
    raise FileNotFoundError(f"Font {name} (or substitutes {subs}) not found in {FONT_DIRS}")


def font(name, size):
    return ImageFont.truetype(font_path(name), size)


def gradient(top, bottom):
    img = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / SIZE
        draw.line([(0, y), (SIZE, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def glow(img, box, color, blur):
    """Soft light blob composited over the image."""
    layer = Image.new("RGBA", img.size, color[:3] + (0,))  # transparent in the glow colour, so blur never darkens
    ImageDraw.Draw(layer).ellipse(box, fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.paste(layer, (0, 0), layer)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def fit(draw, text, fontfile, width, height, max_size, min_size=28, leading=1.4):
    """Largest font size whose wrapped text fits in width x height."""
    for size in range(max_size, min_size - 1, -2):
        fnt = font(fontfile, size)
        lines = wrap(draw, text, fnt, width)
        line_h = int(size * leading)
        if len(lines) * line_h <= height:
            return fnt, lines, line_h
    return fnt, lines, line_h


def text_block(draw, lines, fnt, line_h, y, fill, x=None, box_h=None):
    """Draw lines centred horizontally (x=None) or left-aligned at x; centre vertically in box_h."""
    if box_h:
        y += (box_h - len(lines) * line_h) / 2
    for line in lines:
        lx = x if x is not None else (SIZE - draw.textlength(line, font=fnt)) / 2
        draw.text((lx, y), line, font=fnt, fill=fill)
        y += line_h


def centered(draw, text, y, fnt, fill):
    draw.text(((SIZE - draw.textlength(text, font=fnt)) / 2, y), text, font=fnt, fill=fill)


def spaced(draw, text, y, fnt, fill, tracking, x=None):
    """Letter-spaced text, centred unless x is given."""
    total = sum(draw.textlength(c, font=fnt) for c in text) + tracking * (len(text) - 1)
    cx = x if x is not None else (SIZE - total) / 2
    for c in text:
        draw.text((cx, y), c, font=fnt, fill=fill)
        cx += draw.textlength(c, font=fnt) + tracking


def quote(verse):
    return f"\u201C{verse['text']}\u201D"


# ---------------------------------------------------------------- styles

def royal(verse):
    img = gradient((22, 33, 62), (74, 44, 94))
    d = ImageDraw.Draw(img)
    gold, white = (232, 196, 120), (250, 247, 240)
    d.rectangle([40, 40, SIZE - 40, SIZE - 40], outline=gold, width=3)
    centered(d, "TODAY'S BLESSING", 110, font("georgiab.ttf", 44), gold)
    d.line([(SIZE / 2 - 80, 180), (SIZE / 2 + 80, 180)], fill=gold, width=2)
    fnt, lines, lh = fit(d, quote(verse), "georgiai.ttf", 800, 560, 56)
    text_block(d, lines, fnt, lh, 230, white, box_h=560)
    centered(d, f"\u2014 {verse['ref']}", 830, font("georgiab.ttf", 40), gold)
    centered(d, "Truth of Bible", 960, font("georgia.ttf", 30), (200, 190, 215))
    return img


def sunrise(verse):
    img = gradient((255, 244, 222), (250, 178, 120))
    glow(img, (240, 700, 840, 1300), (255, 214, 140, 230), 90)
    d = ImageDraw.Draw(img)
    brown, rust = (74, 40, 22), (176, 84, 38)
    for i in range(-6, 7):  # faint sun rays
        a = math.radians(90 + i * 11)
        d.line([(540, 1000), (540 + 1500 * math.cos(a), 1000 - 1500 * math.sin(a))], fill=(255, 236, 205), width=2)
    centered(d, "Today's Blessing", 70, font("Gabriola.ttf", 96), rust)
    fnt, lines, lh = fit(d, quote(verse), "palai.ttf", 820, 540, 58)
    text_block(d, lines, fnt, lh, 250, brown, box_h=540)
    centered(d, verse["ref"], 830, font("palab.ttf", 42), rust)
    spaced(d, "TRUTH OF BIBLE", 970, font("segoeuisl.ttf", 26), brown, 8)
    return img


def minimal(verse):
    img = Image.new("RGB", (SIZE, SIZE), (247, 243, 235))
    d = ImageDraw.Draw(img)
    ink, gold = (34, 34, 34), (184, 146, 72)
    spaced(d, "DAILY BLESSING", 120, font("segoeuisl.ttf", 26), ink, 10, x=120)
    d.line([(120, 180), (220, 180)], fill=gold, width=4)
    fnt, lines, lh = fit(d, quote(verse), "constan.ttf", 840, 560, 64, leading=1.35)
    text_block(d, lines, fnt, lh, 240, ink, x=120, box_h=560)
    d.text((120, 850), verse["ref"].upper(), font=font("constanb.ttf", 34), fill=gold)
    d.text((120, 950), "Truth of Bible", font=font("constani.ttf", 28), fill=(120, 115, 105))
    return img


def parchment(verse):
    img = Image.new("RGB", (SIZE, SIZE), (236, 222, 190))
    rng = random.Random(7)
    px = img.load()
    for y in range(0, SIZE, 2):  # paper grain
        for x in range(0, SIZE, 2):
            n = rng.randint(-10, 10)
            r, g, b = px[x, y]
            px[x, y] = (r + n, g + n, b + n)
    vignette = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(vignette).ellipse((-150, -150, SIZE + 150, SIZE + 150), fill=255)
    img = Image.composite(img, Image.new("RGB", img.size, (170, 140, 95)), vignette.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(img)
    ink, red = (58, 38, 22), (128, 36, 30)
    d.rectangle([50, 50, SIZE - 50, SIZE - 50], outline=ink, width=3)
    d.rectangle([64, 64, SIZE - 64, SIZE - 64], outline=ink, width=1)
    for cx, cy in [(64, 64), (SIZE - 64, 64), (64, SIZE - 64), (SIZE - 64, SIZE - 64)]:
        d.polygon([(cx, cy - 16), (cx + 16, cy), (cx, cy + 16), (cx - 16, cy)], fill=red)
    centered(d, "A Blessing for Today", 110, font("Gabriola.ttf", 84), red)
    fnt, lines, lh = fit(d, quote(verse), "cambriai.ttf", 780, 540, 56)
    text_block(d, lines, fnt, lh, 250, ink, box_h=540)
    centered(d, "\u2766", 810, font("seguisym.ttf", 40), red)
    centered(d, verse["ref"], 870, font("cambriab.ttf", 40), ink)
    centered(d, "Truth of Bible", 950, font("cambria.ttc", 28), (110, 85, 60))
    return img


def modern(verse):
    img = Image.new("RGB", (SIZE, SIZE), (14, 70, 76))
    d = ImageDraw.Draw(img)
    coral, white = (246, 146, 108), (255, 255, 255)
    d.rectangle([0, 0, 24, SIZE], fill=coral)
    d.ellipse([760, -220, 1300, 320], outline=(28, 96, 102), width=40)
    d.text((110, 100), "\u201C", font=font("georgiab.ttf", 220), fill=coral)
    fnt, lines, lh = fit(d, verse["text"], "segoeuib.ttf", 860, 520, 70, leading=1.25)
    text_block(d, lines, fnt, lh, 310, white, x=110, box_h=520)
    d.text((110, 880), verse["ref"], font=font("segoeuib.ttf", 40), fill=coral)
    spaced(d, "TRUTH OF BIBLE", 960, font("segoeuil.ttf", 26), (170, 205, 205), 8, x=110)
    return img


def radiant(verse):
    img = gradient((8, 10, 24), (26, 22, 48))
    rays = Image.new("RGBA", img.size, (255, 225, 160, 0))
    rd = ImageDraw.Draw(rays)
    for i in range(-5, 6):  # light beams fanning down from the cross
        a = math.radians(90 + i * 14)
        tips = [(540 + 1600 * math.cos(a + s), 150 + 1600 * math.sin(a + s)) for s in (0.03, -0.03)]
        rd.polygon([(540, 150), *tips], fill=(255, 225, 160, 22))
    blurred = rays.filter(ImageFilter.GaussianBlur(12))
    img.paste(blurred, (0, 0), blurred)
    glow(img, (420, 30, 660, 270), (255, 220, 150, 200), 50)
    d = ImageDraw.Draw(img)
    gold = (244, 208, 130)
    d.rectangle([532, 80, 548, 230], fill=(255, 245, 220))
    d.rectangle([490, 120, 590, 136], fill=(255, 245, 220))
    fnt, lines, lh = fit(d, quote(verse), "georgia.ttf", 820, 520, 54)
    text_block(d, lines, fnt, lh, 300, (245, 242, 235), box_h=520)
    centered(d, verse["ref"], 860, font("georgiab.ttf", 40), gold)
    spaced(d, "TRUTH OF BIBLE", 960, font("segoeuil.ttf", 24), (170, 165, 190), 8)
    return img


# ------------------------------------------------------- modern variants

def _modern_left(verse, bg, fg, accent, sub, deco=None, bar=True, quote_mark=True):
    """Shared left-aligned bold layout used by several modern variants."""
    img = Image.new("RGB", (SIZE, SIZE), bg)
    d = ImageDraw.Draw(img)
    if deco:
        deco(d)
    if bar:
        d.rectangle([0, 0, 24, SIZE], fill=accent)
    if quote_mark:
        d.text((110, 100), "“", font=font("georgiab.ttf", 220), fill=accent)
    fnt, lines, lh = fit(d, verse["text"], "segoeuib.ttf", 860, 520, 70, leading=1.25)
    text_block(d, lines, fnt, lh, 310, fg, x=110, box_h=520)
    d.text((110, 880), verse["ref"], font=font("segoeuib.ttf", 40), fill=accent)
    spaced(d, "TRUTH OF BIBLE", 960, font("segoeuil.ttf", 26), sub, 8, x=110)
    return img


def modern_navy(verse):
    def dots(d):
        for x in range(700, 1040, 36):
            for y in range(60, 300, 36):
                d.ellipse([x, y, x + 8, y + 8], fill=(40, 54, 90))
    return _modern_left(verse, (16, 24, 48), (255, 255, 255), (255, 196, 61), (150, 160, 190), dots)


def modern_forest(verse):
    def stripes(d):
        for i in range(0, 400, 40):
            d.line([(SIZE - 400 + i, 0), (SIZE, 400 - i)], fill=(34, 78, 58), width=14)
    return _modern_left(verse, (22, 58, 42), (246, 240, 225), (233, 204, 140), (160, 190, 170), stripes)


def modern_mono(verse):
    def sun(d):
        d.ellipse([760, 760, 1300, 1300], fill=(255, 94, 58))
    return _modern_left(verse, (245, 244, 240), (20, 20, 20), (255, 94, 58), (110, 110, 110), sun, bar=False)


def modern_dark(verse):
    def big_quote(d):
        d.text((560, -160), "”", font=font("georgiab.ttf", 900), fill=(28, 28, 32))
    return _modern_left(verse, (12, 12, 14), (255, 255, 255), (190, 242, 100), (130, 130, 140),
                        big_quote, bar=False)


def pill(d, text, cx, y, fnt, bg, fg, pad=(28, 12)):
    w = d.textlength(text, font=fnt)
    h = fnt.size
    x0 = cx - w / 2 - pad[0]
    d.rounded_rectangle([x0, y, cx + w / 2 + pad[0], y + h + pad[1] * 2 + 6], radius=40, fill=bg)
    d.text((cx - w / 2, y + pad[1]), text, font=fnt, fill=fg)


def modern_gradient(verse):
    img = Image.new("RGB", (SIZE, SIZE))
    px = img.load()
    a, b = (98, 54, 200), (236, 72, 140)
    for y in range(SIZE):  # diagonal purple -> pink
        for x in range(0, SIZE):
            t = (x + y) / (2 * SIZE)
            px[x, y] = tuple(int(p + (q - p) * t) for p, q in zip(a, b))
    d = ImageDraw.Draw(img)
    pill(d, "DAILY BLESSING", SIZE / 2, 110, font("segoeuib.ttf", 28), (255, 255, 255), (120, 60, 180))
    fnt, lines, lh = fit(d, verse["text"], "segoeuib.ttf", 860, 540, 72, leading=1.25)
    text_block(d, lines, fnt, lh, 250, (255, 255, 255), box_h=540)
    centered(d, verse["ref"], 850, font("segoeuib.ttf", 42), (255, 225, 240))
    spaced(d, "TRUTH OF BIBLE", 960, font("segoeuil.ttf", 26), (255, 235, 245), 8)
    return img


def modern_card(verse):
    img = Image.new("RGB", (SIZE, SIZE), (226, 234, 246))
    shadow = Image.new("RGBA", img.size, (60, 80, 120, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([90, 110, 990, 1010], radius=48, fill=(60, 80, 120, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    img.paste(shadow, (0, 0), shadow)
    d = ImageDraw.Draw(img)
    navy, blue = (22, 34, 64), (52, 110, 235)
    d.rounded_rectangle([90, 90, 990, 990], radius=48, fill=(255, 255, 255))
    pill(d, "DAILY BLESSING", SIZE / 2, 150, font("segoeuib.ttf", 26), (232, 240, 255), blue)
    fnt, lines, lh = fit(d, verse["text"], "segoeuib.ttf", 740, 500, 62, leading=1.3)
    text_block(d, lines, fnt, lh, 260, navy, box_h=500)
    centered(d, verse["ref"], 800, font("segoeuib.ttf", 38), blue)
    d.line([(SIZE / 2 - 40, 870), (SIZE / 2 + 40, 870)], fill=(210, 220, 235), width=3)
    spaced(d, "TRUTH OF BIBLE", 900, font("segoeuil.ttf", 24), (120, 130, 150), 8)
    return img


def modern_split(verse):
    img = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    d = ImageDraw.Draw(img)
    coral, ink = (240, 106, 80), (28, 28, 36)
    d.rectangle([0, 0, SIZE, 380], fill=coral)
    spaced(d, "TODAY'S BLESSING", 110, font("segoeuib.ttf", 30), (255, 230, 222), 8, x=100)
    d.text((100, 170), verse["ref"], font=font("segoeuib.ttf", 96), fill=(255, 255, 255))
    fnt, lines, lh = fit(d, verse["text"], "segoeuisl.ttf", 880, 430, 62, leading=1.3)
    text_block(d, lines, fnt, lh, 440, ink, x=100, box_h=430)
    d.rectangle([100, 960, 160, 966], fill=coral)
    spaced(d, "TRUTH OF BIBLE", 945, font("segoeuib.ttf", 24), ink, 8, x=180)
    return img


def modern_sky(verse):
    img = gradient((110, 180, 240), (36, 84, 176))
    for box in [(-120, 780, 420, 1160), (250, 860, 760, 1260), (640, 800, 1200, 1200)]:
        glow(img, box, (255, 255, 255, 60), 40)  # soft clouds
    d = ImageDraw.Draw(img)
    white = (255, 255, 255)
    d.rectangle([110, 130, 190, 138], fill=white)
    spaced(d, "DAILY BLESSING", 160, font("segoeuib.ttf", 28), white, 8, x=110)
    fnt, lines, lh = fit(d, verse["text"], "segoeuib.ttf", 860, 520, 70, leading=1.25)
    text_block(d, lines, fnt, lh, 280, white, x=110, box_h=520)
    d.text((110, 850), verse["ref"], font=font("segoeuib.ttf", 40), fill=(255, 236, 160))
    spaced(d, "TRUTH OF BIBLE", 950, font("segoeuil.ttf", 26), (225, 238, 255), 8, x=110)
    return img


MODERN = {
    "modern": modern,
    "modern_navy": modern_navy,
    "modern_forest": modern_forest,
    "modern_mono": modern_mono,
    "modern_dark": modern_dark,
    "modern_gradient": modern_gradient,
    "modern_card": modern_card,
    "modern_split": modern_split,
    "modern_sky": modern_sky,
}


STYLES = {
    "royal": royal,
    "sunrise": sunrise,
    "minimal": minimal,
    "parchment": parchment,
    "modern": modern,
    "radiant": radiant,
    **MODERN,
}


def feature_card(feature):
    """App feature post: feature name large, one-line benefit, and a Google Play pill,
    in the modern_mono palette so feature posts sit visually with the verse posts."""
    img = Image.new("RGB", (SIZE, SIZE), (245, 244, 240))
    d = ImageDraw.Draw(img)
    ink, accent, grey = (20, 20, 20), (255, 94, 58), (90, 90, 90)
    d.ellipse([740, 700, 1340, 1300], fill=accent)
    spaced(d, "TRUTH OF BIBLE APP", 120, font("segoeuib.ttf", 28), accent, 8, x=110)
    d.line([(110, 175), (210, 175)], fill=accent, width=4)

    title_font, title_lines, title_h = fit(d, feature["title"], "segoeuib.ttf", 860, 300, 110, leading=1.1)
    y = 230
    text_block(d, title_lines, title_font, title_h, y, ink, x=110)
    y += len(title_lines) * title_h + 30
    tag_font, tag_lines, tag_h = fit(d, feature.get("image_text") or "", "segoeuisl.ttf", 760, 900 - y - 60, 50,
                                     leading=1.3)
    text_block(d, tag_lines, tag_font, tag_h, y, grey, x=110)

    pill = font("segoeuib.ttf", 30)
    label = "Get it on Google Play"
    w = d.textlength(label, font=pill)
    d.rounded_rectangle([110, 900, 110 + w + 64, 970], radius=35, fill=ink)
    d.text((142, 915), label, font=pill, fill=(255, 255, 255))
    return img


def prayer_card(item):
    """Salvation prayer: warm night-blue card, the prayer itself in serif italic,
    title and Scripture footer in gold — reverent, not promotional."""
    img = gradient((20, 26, 48), (46, 36, 66))
    glow(img, (240, -260, 840, 260), (255, 214, 150, 90), 120)
    d = ImageDraw.Draw(img)
    gold, white = (236, 200, 128), (248, 244, 236)
    spaced(d, "A PRAYER OF SALVATION", 110, font("georgiab.ttf", 26), gold, 7)
    d.line([(SIZE / 2 - 60, 160), (SIZE / 2 + 60, 160)], fill=gold, width=2)
    title_font, title_lines, title_h = fit(d, item["title"], "georgiab.ttf", 860, 150, 64, leading=1.15)
    text_block(d, title_lines, title_font, title_h, 195, gold)
    top = 195 + len(title_lines) * title_h + 40
    body_font, body_lines, body_h = fit(d, item.get("image_text") or "", "georgiai.ttf", 820, 850 - top, 44)
    text_block(d, body_lines, body_font, body_h, top, white, box_h=850 - top)
    if item.get("image_footer"):
        centered(d, f"— {item['image_footer']}", 880, font("georgiab.ttf", 36), gold)
    spaced(d, "TRUTH OF BIBLE", 970, font("segoeuil.ttf", 24), (190, 180, 210), 8)
    return img


# Card design per TOB Social Content type; unknown types get the feature card.
CONTENT_CARDS = {"App Feature": feature_card, "Salvation Prayer": prayer_card}


def render_content(item, path):
    CONTENT_CARDS.get(item.get("content_type"), feature_card)(item).save(path, "PNG")
    return path


def render(verse, style, path):
    STYLES[style](verse).save(path, "PNG")
    return path


def contact_sheet(verse, path, styles=None, cell=520, pad=20, label_h=56):
    styles = styles or {k: STYLES[k] for k in list(STYLES)[:6]}
    cols = 3
    rows = -(-len(styles) // cols)
    sheet = Image.new("RGB", (cols * (cell + pad) + pad, rows * (cell + label_h + pad) + pad), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    for i, (name, fn) in enumerate(styles.items()):
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + label_h + pad)
        sheet.paste(fn(verse).resize((cell, cell), Image.LANCZOS), (x, y))
        d.text((x, y + cell + 10), f"{i + 1}. {name}", font=font("segoeuib.ttf", 30), fill=(30, 30, 30))
    sheet.save(path, "PNG")
    return path


if __name__ == "__main__":
    import datetime
    from pathlib import Path

    from post_blessing import todays_verse

    out = Path(__file__).resolve().parent / "design_previews"
    out.mkdir(exist_ok=True)
    verse = todays_verse(datetime.date.today())
    for name in STYLES:
        print(render(verse, name, out / f"{name}.png"))
    print(contact_sheet(verse, out / "all_designs.png"))
    print(contact_sheet(verse, out / "modern_designs.png", MODERN))
