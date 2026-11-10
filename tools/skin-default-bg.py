#!/usr/bin/env python3
"""Фон скина по умолчанию (media/common/bg2.jpg) - нейтральный.

bg2.jpg скин показывает, когда у элемента нет фанарта и в настройках скина не
выбрана своя картинка (Skin.String(fanart.fallback), «Настройки скина -> Фон»).
Раньше там был терминатор, подобранный под себя (CHANGES.md скина, п. 4.2) -
для общего скина это не годится. Теперь - почти чёрный фон со слабым свечением
в центре и приглушённой надписью с названием скина, как на заставке загрузки.
Своя картинка ставится настройкой скина, на K9 - ./bin/k9-kodi.sh bg.

    skin-default-bg.py                         показать, что поменяется
    skin-default-bg.py --apply                 записать bg2.jpg в рабочую копию
    skin-default-bg.py --title "..." --sub "..." --apply   другое название
    skin-default-bg.py --skin <каталог скина> [--apply]     другая копия скина

По умолчанию - основная копия скина под Kodi 22, там фон -
extras/backgrounds/bg2.jpg; в легаси под Kodi 21 - media/common/bg2.jpg. Куда писать,
скрипт определяет сам по раскладке скина.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SKIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skin.arctic.zephyr.2.resurrection.k9")


def paths(skin):
    """(bg2.jpg, шрифт): в 1.1.12 фоны - в extras/backgrounds, в 1.0.36 - в media/common."""
    glob_xml = open(os.path.join(skin, "1080i", "Includes_Global.xml"), encoding="utf-8").read()
    rel = "extras/backgrounds" if "extras/backgrounds/bg2.jpg" in glob_xml else "media/common"
    out = os.path.join(skin, rel, "bg2.jpg")
    return out, os.path.join(skin, "fonts", "RobotoCondensed-Bold.ttf")


OUT, FONT = paths(SKIN)
W, H = 1920, 1080
ACCENT = (229, 9, 20)       # красный Netflix - focuscolor.name темы


def render(title, accent_word, sub):
    # фон: от #050506 по краям к #17171b в центре
    bg = Image.new("RGB", (W, H), (5, 5, 6))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.15, H * 0.05, W * 0.85, H * 0.95), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(260))
    bg = Image.composite(Image.new("RGB", (W, H), (23, 23, 27)), bg, glow)

    # надпись - водяной знак: белое ~16%, акцент ~30%
    text = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(text)
    big, small = ImageFont.truetype(FONT, 150), ImageFont.truetype(FONT, 96)
    white, red = (255, 255, 255, 40), ACCENT + (78,)
    parts = [(w + " ", red if w == accent_word else white) for w in title.split()]
    parts[-1] = (parts[-1][0].rstrip(), parts[-1][1])
    width = sum(d.textlength(p, font=big) for p, _ in parts)
    x, y = (W - width) / 2, H * 0.47
    for p, color in parts:
        d.text((x, y), p, font=big, fill=color, anchor="ls")
        x += d.textlength(p, font=big)
    if sub:
        d.text((W / 2, y + 115), sub, font=small, fill=red, anchor="ms")
    out = Image.alpha_composite(bg.convert("RGBA"), text).convert("RGB")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Arctic Zephyr 2")
    ap.add_argument("--accent", default="Zephyr", help="слово названия цветом акцента")
    ap.add_argument("--sub", default="Resurrection")
    ap.add_argument("--skin", default=SKIN, help="каталог скина")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    global OUT, FONT
    OUT, FONT = paths(os.path.abspath(os.path.expanduser(a.skin)))
    im = render(a.title, a.accent, a.sub)
    print("%s: %dx%d, «%s» / «%s»" % (OUT, W, H, a.title, a.sub))
    if not a.apply:
        print("это план; записать - --apply, на K9 - ./bin/k9-kodi.sh update --apply")
        return
    im.save(OUT, quality=92, optimize=True)
    print("записано")


if __name__ == "__main__":
    main()
