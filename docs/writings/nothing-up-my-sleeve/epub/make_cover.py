"""Make the epub cover (D16): the Risso-style card-table art from the Atlas generator when cover-art.png is
beside this script, else a drawn hand of cards; the title, Fable as author, Justin Trollip as Head of
Metaphors. Usage: make_cover.py out.jpg "Title" "Subtitle" """
import sys, math
from PIL import Image, ImageDraw, ImageFont

out, title, subtitle = sys.argv[1:4]
W, H = 1600, 2560
bg = (246, 242, 233)
ink = (28, 30, 34)
rule = (120, 110, 95)
red = (156, 38, 36)
card_face = (252, 250, 244)
img = Image.new("RGB", (W, H), bg)
d = ImageDraw.Draw(img)

def font(size, bold=False, name=None):
    for n in ([name] if name else []) + (["Baskerville Bold.ttf" if bold else "Baskerville.ttf", "Georgia Bold.ttf" if bold else "Georgia.ttf"]):
        try:
            return ImageFont.truetype("/System/Library/Fonts/Supplemental/" + n, size)
        except OSError:
            continue
    return ImageFont.load_default()

def centred(text, y, f, fill=ink):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)
    return y + f.size

def wrapped(text, y, f, maxw, fill=ink, gap=1.15):
    words, line = text.split(), ""
    for w_ in words:
        t = (line + " " + w_).strip()
        if d.textlength(t, font=f) > maxw and line:
            y = centred(line, y, f, fill) + int(f.size * (gap - 1)); line = w_
        else:
            line = t
    if line:
        y = centred(line, y, f, fill)
    return y

# The cover art: scripts/generate-government-art.py cover:nothing-up-my-sleeve writes cover-art.png beside this
# script (fal, in the Atlas's Risso style). It is composed here in high-contrast grayscale, which is what Risso
# is and what an e-ink Kindle shows; the colour file stays as the source. Without it, a drawn hand of cards.
import os
from PIL import ImageOps, ImageEnhance
art_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cover-art.png")
if os.path.exists(art_path):
    art = Image.open(art_path).convert("L")
    art = ImageOps.autocontrast(art, cutoff=1)
    art = ImageEnhance.Contrast(art).enhance(1.25)
    # Fit the art to a fixed band so the title, the two names and the imprint always have their room.
    ah = 1300
    aw = int(art.width * ah / art.height)
    if aw > W - 160:
        aw = W - 160; ah = int(art.height * aw / art.width)
    art = art.resize((aw, ah), Image.LANCZOS).convert("RGB")
    ax = (W - aw) // 2
    img.paste(art, (ax, 80))
    d.rectangle([ax, 80, ax + aw - 1, 80 + ah - 1], outline=rule, width=3)
    y_art_end = 80 + ah
else:
    suit_font = font(150, name="Arial Unicode.ttf")
    rank_font = font(120, bold=True)
    cards = [("A", "\u2660", ink), ("K", "\u2665", red), ("10", "\u2666", red), ("7", "\u2663", ink), ("2", "\u2660", ink)]
    cw, ch = 420, 600
    pivot = (W // 2, 1150)
    for i, (rank, suit, colour) in enumerate(cards):
        layer = Image.new("RGBA", (cw + 40, ch + 40), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([20, 20, cw + 20, ch + 20], radius=28, fill=card_face, outline=rule, width=4)
        ld.text((50, 40), rank, font=rank_font, fill=colour)
        ld.text((50, 160), suit, font=font(90, name="Arial Unicode.ttf"), fill=colour)
        sw = ld.textlength(suit, font=suit_font)
        ld.text(((cw + 40 - sw) / 2, ch / 2 - 40), suit, font=suit_font, fill=colour)
        angle = -34 + i * 17
        rot = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
        r = 640
        cx = pivot[0] + r * math.sin(math.radians(angle))
        cy = pivot[1] - r * math.cos(math.radians(angle)) + 60
        img.paste(rot, (int(cx - rot.width / 2), int(cy - rot.height / 2)), rot)
    y_art_end = 1250

y = y_art_end + 70
d.line([(240, y), (W - 240, y)], fill=rule, width=3)
y += 60
y = wrapped(title, y, font(140, bold=True), W - 240, gap=1.05)
y += 24
y = wrapped(subtitle, y, font(56), W - 300, fill=rule)
y += 50
d.line([(600, y), (W - 600, y)], fill=rule, width=2)
y += 50
y = centred("Fable", y, font(88, bold=True))
y = centred("author", y + 6, font(44), fill=rule)
y += 40
y = centred("Justin Trollip", y, font(72, bold=True))
y = centred("Head of Metaphors", y + 6, font(44), fill=rule)
centred("Demiton · 2026", H - 110, font(44), fill=rule)
img.save(out, "JPEG", quality=88)
print(out, img.size)
