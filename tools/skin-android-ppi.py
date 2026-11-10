#!/usr/bin/env python3
"""Панель информации о воспроизведении для Kodi на Android - разметка скина.

Вписывает в 1080i/DialogPlayerProcessInfo.xml рабочей копии скина
(~/code/Linux/coreelec/skin.arctic.zephyr.2.resurrection.k9) группу, видимую
только на Android, между метками android-ppi:start / android-ppi:end; прежнюю
версию группы заменяет. Значения - свойства Window(Home).Property(K9Info.<имя>),
их собирает service.mediainfo.filesize (playerpanel.py). Подписи - прямо
по-русски: строки скина 32000+ на Kodi 22 приходят пустыми.

Вид (с 10.11.2026) - карточками, по образцу skin.bald: сверху три карточки
«Видео», «Звук», «Выход» (крупное значение, бейдж FEL/MEL и две строки
подробностей), ниже - слои Dolby Vision (или метаданные HDR10) и поток (битрейт
крупно, столбики последних секунд), внизу кольца: кэш, очереди, процессор,
память, температура.

Заодно скрипт рисует текстуры панели в media/k9ppi/ (скругления, кольца,
столбики - PIL; там же плашки строки под списком и карточка у часов, п. 21), а в
VideoFullScreen.xml - карточки на старте воспроизведения (логотипы сверху,
дорожка и плашки видео снизу, п. 27; штатные бейджи на Android прячет) и вписывает шрифты k9_* во все наборы Font.xml (метки
k9-fonts:start / k9-fonts:end). Прозрачность и обводка зашиты в картинки:
colordiffuse приглушил бы контур вместе с заливкой.

    skin-android-ppi.py            показать, что поменяется
    skin-android-ppi.py --apply    вписать в рабочую копию

На бокс - ./bin/k9-kodi.sh update --apply. Разбор - CHANGES.md скина, п. 17 и 21,
и docs/howto/k9-kodi.md.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

SKIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skin.arctic.zephyr.2.resurrection.k9")
DIALOG = os.path.join(SKIN, "1080i", "DialogPlayerProcessInfo.xml")
FONTS = os.path.join(SKIN, "1080i", "Font.xml")
MEDIA = os.path.join(SKIN, "media", "k9ppi")
START, END = "<!-- android-ppi:start", "<!-- android-ppi:end -->"
FSTART, FEND = "<!-- k9-fonts:start -->", "<!-- k9-fonts:end -->"
FULLSCREEN = os.path.join(SKIN, "1080i", "VideoFullScreen.xml")
SSTART, SEND = "<!-- android-start:start", "<!-- android-start:end -->"

P = "Window(Home).Property(K9Info.%s)"
# признак от service.mediainfo.filesize: сервис работает (любой Kodi, кроме CoreELEC) -
# показываем наши панель и плашки; иначе - штатные скина (п. 35)
ACTIVE = "!String.IsEmpty(Window(Home).Property(K9Info.Active))"
INACTIVE = "String.IsEmpty(Window(Home).Property(K9Info.Active))"

# шрифты панели и строки под списком: Roboto (не Condensed) - ближе к образцу
K9_FONTS = [
    ("k9_title", "Roboto-Medium.ttf", 32),
    ("k9_cap", "Roboto-Medium.ttf", 19),
    ("k9_big", "Roboto-Bold.ttf", 40),
    ("k9_huge", "Roboto-Bold.ttf", 66),
    ("k9_sub", "Roboto-Regular.ttf", 22),
    ("k9_val", "Roboto-Bold.ttf", 22),
    ("k9_pill", "Roboto-Bold.ttf", 24),
    ("k9_chip", "Roboto-Medium.ttf", 24),
    # заголовок фильма на главной: русское название и имя папки (CHANGES.md, п. 23)
    ("k9_head", "RobotoCondensed-Bold.ttf", 44, 0.9),
    ("k9_folder", "RobotoCondensed-Regular.ttf", 32),
]

# раскладка, экран 1920x1080
PANEL = (80, 330, 1760, 700)      # left, top, width, height
CARDS = [  # (left, ширина, значок font_tiny_iconic, заголовок, префикс свойств)
    (40, 544, "Video", "ВИДЕО", "Video"),
    (608, 544, "Audio", "ЗВУК", "Audio"),
    (1176, 544, "Output", "ВЫХОД", "Out"),
]
ROW1, ROW1_H = 92, 180
ROW2, ROW2_H = 296, 236
DV_W, ST_LEFT, ST_W = 980, 1044, 676
BARS = 26           # столбиков битрейта; столько же секунд копит playerpanel.HISTORY
GAUGES = [  # (свойство, подпись)
    ("Cache", "Кэш плеера"),
    ("VQueue", "Очередь видео"),
    ("AQueue", "Очередь звука"),
    ("Cpu", "Процессор"),
    ("Mem", "Память"),
    ("Soc", "SoC"),
    ("Gpu", "GPU"),
]
ROW3 = 556
GAUGES_H = 140      # сколько занимает строка колец вместе с отступом
LEVELS = 20         # кольца и столбики - картинки 00..20


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ctl(indent, kind, **kw):
    """Контрол: kw в порядке передачи; visible может быть списком."""
    pad = " " * indent
    out = ['%s<control type="%s">' % (pad, kind)]
    for k, v in kw.items():
        if k == "texture":
            v, border = v if isinstance(v, tuple) else (v, None)
            attr = ' border="%d"' % border if border else ""
            out.append('%s    <texture%s>%s</texture>' % (pad, attr, v))
            continue
        for item in (v if isinstance(v, list) else [v]):
            out.append('%s    <%s>%s</%s>' % (pad, k, item, k))
    out.append(pad + "</control>")
    return "\n".join(out)


def text(indent, left, top, width, height, label, font, color="dialog_fg_100", align=None,
         visible=None):
    kw = dict(left=left, top=top, width=width, height=height, aligny="center")
    if align:
        kw["align"] = align
    kw.update(label=label, font=font, textcolor=color)
    if visible:
        kw["visible"] = visible
    return ctl(indent, "label", **kw)


def image(indent, left, top, width, height, texture, border=None, visible=None):
    kw = dict(left=left, top=top, width=width, height=height,
              texture=(texture, border) if border else texture)
    if visible:
        kw["visible"] = visible
    return ctl(indent, "image", **kw)


def caption(indent, icon, title, extra=None):
    """Значок и заголовок карточки капсом, справа от него - приглушённое пояснение."""
    parts = [text(indent, 28, 18, 30, 30, icon, "font_tiny_iconic", "dialog_fg_70"),
             text(indent, 64, 18, 400, 30, title, "k9_cap", "dialog_fg_70")]
    if extra:
        parts.append(text(indent, 64 + 14 * len(title) + 14, 18, 600, 30, extra, "k9_sub", "8CFFFFFF"))
    return parts


def card(indent, left, top, width, height, body, tex="k9ppi/card.png", visible=None):
    pad = " " * indent
    return "\n".join([pad + '<control type="group">',
                      pad + '    <left>%d</left>' % left,
                      pad + '    <top>%d</top>' % top] +
                     ([pad + '    <visible>%s</visible>' % visible] if visible else []) + [
                      image(indent + 4, 0, 0, width, height, tex, 22)] + body +
                     [pad + '</control>'])


def top_card(indent, left, width, icon, title, key, visible=None):
    i = indent + 4
    big = P % (key + "Big")
    tag = P % (key + "Tag")
    body = caption(i, icon, title)
    # крупное значение и бейдж сразу за ним: grouplist с шириной по тексту
    body.append("\n".join([
        " " * i + '<control type="grouplist">',
        " " * i + '    <left>28</left>',
        " " * i + '    <top>50</top>',
        " " * i + '    <width>%d</width>' % (width - 56),
        " " * i + '    <height>56</height>',
        " " * i + '    <orientation>horizontal</orientation>',
        " " * i + '    <itemgap>16</itemgap>',
        " " * i + '    <usecontrolcoords>true</usecontrolcoords>',
        ctl(i + 4, "label", width="auto", height=56, aligny="center",
            label="$INFO[%s]" % big, font="k9_big", textcolor="dialog_fg_100"),
        " " * i + '    <control type="group">',
        " " * i + '        <width>86</width>',
        " " * i + '        <height>56</height>',
        " " * i + '        <visible>!String.IsEmpty(%s)</visible>' % tag,
        image(i + 8, 0, 9, 86, 38, "k9ppi/pill.png", 12),
        text(i + 8, 0, 9, 86, 38, "$INFO[%s]" % tag, "k9_pill", "FF101010", "center"),
        " " * i + '    </control>',
        " " * i + '</control>']))
    body.append(text(i, 28, 110, width - 56, 30, "$INFO[%s]" % (P % (key + "Sub")), "k9_sub", "dialog_fg_70"))
    body.append(text(i, 28, 140, width - 56, 30, "$INFO[%s]" % (P % (key + "Sub2")), "k9_sub", "8CFFFFFF"))
    tex = "k9ppi/card_hi.png" if key == "Video" else "k9ppi/card.png"
    return card(indent, left, ROW1, width, ROW1_H, body, tex, visible)


def dv_card(indent, icons):
    i = indent + 4
    body = [text(i, 28, 18, 300, 30, "$INFO[%s]" % (P % "DvTitle"), "k9_cap", "dialog_fg_70"),
            text(i, 240, 18, DV_W - 268, 30, "$INFO[%s]" % (P % "DvInfo"), "k9_sub", "8CFFFFFF")]
    # строки слоёв - списком: пустая (EL без профиля на Kodi 21) прячется, следующая
    # поднимается (п. 37)
    body.append("\n".join([
        " " * i + '<control type="grouplist">',
        " " * i + '    <top>66</top>',
        " " * i + '    <width>%d</width>' % DV_W,
        " " * i + '    <height>162</height>',
        " " * i + '    <orientation>vertical</orientation>',
        " " * i + '    <itemgap>10</itemgap>']))
    for n in (1, 2, 3):
        tag, style, line = (P % ("L%d%s" % (n, x)) for x in ("Tag", "Style", "Text"))
        body.append("\n".join([
            " " * (i + 4) + '<control type="group">',
            " " * (i + 4) + '    <height>44</height>',
            " " * (i + 4) + '    <visible>!String.IsEmpty(%s)</visible>' % tag,
            image(i + 8, 28, 15, 124, 14, "k9ppi/layer_$INFO[%s].png" % style),
            text(i + 8, 172, 0, 70, 44, "$INFO[%s]" % tag, "k9_val", "dialog_fg_100"),
            text(i + 8, 250, 0, DV_W - 278, 44, "$INFO[%s]" % line, "k9_sub", "dialog_fg_70"),
            " " * (i + 4) + '</control>']))
    body.append(" " * i + '</control>')
    return card(indent, 40, ROW2, DV_W, ROW2_H, body)


def stream_card(indent, icons):
    i = indent + 4
    body = [text(i, 28, 18, 120, 30, "ПОТОК", "k9_cap", "dialog_fg_70"),
            text(i, 120, 18, ST_W - 148, 30, "$INFO[%s]" % (P % "StreamInfo"), "k9_sub", "8CFFFFFF"),
            text(i, 28, 58, 240, 74, "$INFO[%s]" % (P % "Rate"), "k9_huge", "dialog_fg_100"),
            text(i, 28, 128, 220, 30, "$INFO[%s]" % (P % "RateUnit"), "k9_sub", "dialog_fg_70"),
            text(i, 28, 158, 230, 28, "$INFO[%s]" % (P % "RateSub"), "k9_sub", "8CFFFFFF"),
            text(i, 28, 194, ST_W - 56, 30, "$INFO[%s]" % (P % "StreamFoot"), "k9_sub", "8CFFFFFF")]
    left0 = ST_W - 28 - (BARS * 15 - 5)
    for n in range(BARS):
        # последний столбик - текущая секунда, ярче остальных
        prefix = "barhi" if n == BARS - 1 else "bar"
        body.append(image(i, left0 + n * 15, 66, 10, 120,
                          "k9ppi/%s$INFO[%s].png" % (prefix, P % ("Bar.%d" % n)),
                          visible="!String.IsEmpty(%s) + !Skin.HasSetting(K9.PPIHideBars)"
                          % (P % ("Bar.%d" % n))))
    return card(indent, ST_LEFT, ROW2, ST_W, ROW2_H, body)


def gauges(indent):
    pad = " " * indent
    width = (PANEL[2] - 80) // len(GAUGES)
    out = [pad + '<control type="grouplist">',
           pad + '    <left>40</left>',
           pad + '    <top>%d</top>' % ROW3,
           pad + '    <width>%d</width>' % (PANEL[2] - 80),
           pad + '    <height>130</height>',
           pad + '    <orientation>horizontal</orientation>',
           pad + '    <align>center</align>',
           pad + '    <itemgap>0</itemgap>',
           pad + '    <visible>!Skin.HasSetting(K9.PPIHideGauges)</visible>']
    for key, title in GAUGES:
        val, ring = P % ("G.%s" % key), P % ("G.%s.Ring" % key)
        out += [pad + '    <control type="group">',
                pad + '        <width>%d</width>' % width,
                pad + '        <visible>!String.IsEmpty(%s)</visible>' % val,
                image(indent + 8, (width - 92) // 2, 0, 92, 92, "k9ppi/ring$INFO[%s].png" % ring),
                text(indent + 8, (width - 92) // 2, 0, 92, 92, "$INFO[%s]" % val, "k9_val",
                     "dialog_fg_100", "center"),
                text(indent + 8, 0, 98, width, 30, title, "k9_sub", "dialog_fg_70", "center"),
                pad + '    </control>']
    out.append(pad + '</control>')
    return "\n".join(out)


def build(icons):
    left, top, width, height = PANEL
    parts = ['        %s: своя панель для Kodi на Android (Kodi FEL на K9).' % START,
             '             Генерирует tools/skin-android-ppi.py -',
             '             руками не править. CHANGES.md, п. 17 и 21 -->',
             '        <control type="group">',
             '            <visible>%s</visible>' % ACTIVE,
             '            <left>%d</left>' % left,
             '            <top>%d</top>' % top,
             '            <width>%d</width>' % width,
             '            <height>%d</height>' % height,
             # без колец (настройка K9.PPIHideGauges) панель короче на GAUGES_H и
             # опущена на столько же - низ остаётся на месте (п. 32)
             '            <animation effect="slide" start="0,0" end="0,%d" time="0" condition="Skin.HasSetting(K9.PPIHideGauges)">Conditional</animation>' % GAUGES_H,
             image(12, 0, 0, width, height, "k9ppi/panel.png", 40, visible="!Skin.HasSetting(K9.PPIHideGauges)"),
             image(12, 0, 0, width, height - GAUGES_H, "k9ppi/panel.png", 40, visible="Skin.HasSetting(K9.PPIHideGauges)"),
             text(12, 40, 26, 800, 48, "Информация о воспроизведении", "k9_title"),
             text(12, 860, 26, width - 900, 48, "$INFO[%s]" % (P % "Where"), "k9_sub",
                  "8CFFFFFF", "right")]
    # «Выход» есть только там, где сервис читает HDMI из /sys (Amlogic); без него
    # «Видео» и «Звук» встают в два столбца на всю ширину (п. 35)
    has_out = "!String.IsEmpty(%s)" % (P % "OutBig")
    for cl, cw, icon, title, key in CARDS:
        parts.append(top_card(12, cl, cw, icons[icon], title, key, has_out))
    half = (width - 80 - 24) // 2
    for n, (cl, cw, icon, title, key) in enumerate(CARDS[:2]):
        parts.append(top_card(12, 40 + n * (half + 24), half, icons[icon], title, key, "!" + has_out))
    parts.append(dv_card(12, icons))
    parts.append(stream_card(12, icons))
    parts.append(gauges(12))
    parts.append('        </control>')
    parts.append('        ' + END)
    return "\n".join(parts) + "\n"


# --- текстуры ---

def textures():
    """{имя: PIL.Image} - всё, что панель берёт из media/k9ppi."""
    from PIL import Image, ImageDraw
    S = 4  # рисуем крупнее и уменьшаем - сглаженные края

    def rounded(w, h, r, fill, outline=None, line=0):
        im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), r * S, fill=fill,
                            outline=outline, width=int(line * S))
        return im.resize((w, h), Image.LANCZOS)

    out = {
        "panel": rounded(128, 128, 34, (14, 14, 16, 214), (255, 255, 255, 40), 1.5),
        "card": rounded(96, 96, 20, (255, 255, 255, 14), (255, 255, 255, 30), 1.5),
        "card_hi": rounded(96, 96, 20, (255, 255, 255, 26), (255, 255, 255, 80), 1.5),
        "pill": rounded(48, 48, 9, (255, 255, 255, 240)),
        "chip": rounded(48, 48, 10, (10, 10, 12, 150), (255, 255, 255, 70), 1.5),
        "chip_hi": rounded(48, 48, 10, (255, 255, 255, 235)),
        "glass": rounded(96, 96, 22, (10, 10, 12, 150), (255, 255, 255, 34), 1.5),
        "hline": rounded(16, 2, 0, (255, 255, 255, 46)),
        "layer_solid": rounded(124, 14, 4, (245, 240, 232, 240)),
        "layer_dim": rounded(124, 14, 4, (255, 255, 255, 45)),
    }
    dash = Image.new("RGBA", (124, 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(dash)
    for x in range(0, 124, 10):
        d.rectangle((x, 5, x + 5, 8), fill=(245, 240, 232, 230))
    out["layer_dashed"] = dash

    for n in range(LEVELS + 1):
        size, w = 92 * S, 7 * S
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        box = (w // 2 + S, w // 2 + S, size - w // 2 - S, size - w // 2 - S)
        d.ellipse(box, outline=(255, 255, 255, 50), width=w)
        if n:
            d.arc(box, -90, -90 + 360 * n / LEVELS, fill=(255, 255, 255, 245), width=w)
        out["ring%02d" % n] = im.resize((92, 92), Image.LANCZOS)
        for name, alpha in (("bar", 120), ("barhi", 250)):
            h = max(4, round(120 * n / LEVELS))
            bar = Image.new("RGBA", (10 * S, 120 * S), (0, 0, 0, 0))
            ImageDraw.Draw(bar).rounded_rectangle((0, (120 - h) * S, 10 * S - 1, 120 * S - 1), 2 * S,
                                                  fill=(255, 255, 255, alpha))
            out["%s%02d" % (name, n)] = bar.resize((10, 120), Image.LANCZOS)
    return out


def fonts_block(indent="        "):
    lines = [indent + FSTART]
    for name, fname, size, *aspect in K9_FONTS:
        lines += [indent + "<font>", indent + "    <name>%s</name>" % name,
                  indent + "    <filename>%s</filename>" % fname,
                  indent + "    <size>%d</size>" % size]
        if aspect:
            lines.append(indent + "    <aspect>%s</aspect>" % aspect[0])
        lines.append(indent + "</font>")
    lines.append(indent + FEND)
    return "\n".join(lines) + "\n"


def patch_fonts(raw):
    raw = re.sub(r"[ \t]*" + re.escape(FSTART) + r".*?" + re.escape(FEND) + r"\n", "", raw, flags=re.S)
    return raw.replace("    </fontset>", fonts_block() + "    </fontset>")


# --- плашки на старте воспроизведения (VideoFullScreen.xml), CHANGES.md, п. 27 ---
# Вместо штатных бейджей кодеков (группы 2/3/4: тип видео они берут из поля сборки
# CoreELEC video.source.hdr.type.raw, на Android его нет) и прежней плашки
# дорожки (9500) - две карточки в стиле панели: сверху логотипы видео и звука,
# снизу дорожка и «чипы». Показываются по одному признаку и гаснут вместе.
# В VideoFullScreen у группы и у каждого контрола должен быть явный id, иначе
# контрол не рисуется (CLAUDE.md garik128) - отсюда счётчик.
SHOW = ("[String.IsEqual(Player.Process(av.change),1) | "
        "String.IsEqual(Window(Home).Property(MediaInfo.AVChange),1)]")
LOGOS_ON = ("[Skin.HasSetting(osd.useleftCodecStartupLogos) | Skin.HasSetting(osd.usecenterCodecStartupLogos)"
            " | Skin.HasSetting(osd.userightCodecStartupLogos)]")
VIDEO_LOGOS = [("dolbyvision", "Dolby_Vision"), ("hdr10plus", "HDR10Plus"), ("hdr10", "HDR10"),
               ("hlg", "HLG")]
AUDIO_LOGOS = [
    ("PCM", "pcm pcm_bluray pcm_s16le pcm_s24le"),
    ("AAC", "aac aac_lc aac_ltp aac_ssr he_aac he_aac_v2 aac_latm"),
    ("Dolby_Digital", "ac3 dolbydigital"),
    ("Dolby_Digital_Plus", "eac3"),
    ("Dolby_Digital_Plus_Atmos", "eac3_ddp_atmos"),
    ("Dolby_TrueHD", "truehd"),
    ("Dolby_TrueHD_Atmos", "truehd_atmos"),
    ("MP3", "mp3 mp3float"),
    ("DTS", "dca dts dts_96_24 dts_es dts_express"),
    ("DTS-HD-MA", "dtshd_ma"),
    ("DTS-HD-HRA", "dtshd_hra"),
    ("DTSX", "dtshd_ma_x dts_x dtsx"),
    ("IMAX", "dtshd_ma_x_imax"),
    ("FLAC", "flac"),
    ("OPUS", "opus"),
]
MI = "Window(Home).Property(MediaInfo.%s)"


class Ids:
    def __init__(self, start):
        self.n = start

    def __call__(self):
        self.n += 1
        return self.n


def ictl(ids, indent, kind, **kw):
    pad = " " * indent
    out = ['%s<control type="%s" id="%d">' % (pad, kind, ids())]
    for k, v in kw.items():
        if k == "texture":
            v, border = v if isinstance(v, tuple) else (v, None)
            out.append('%s    <texture%s>%s</texture>' % (pad, ' border="%d"' % border if border else "", v))
            continue
        for item in (v if isinstance(v, list) else [v]):
            out.append('%s    <%s>%s</%s>' % (pad, k, item, k))
    out.append(pad + "</control>")
    return "\n".join(out)


def chip(ids, indent, label, visible, hi=False, font="k9_chip", height=46):
    tex = "k9ppi/chip_hi.png" if hi else "k9ppi/chip.png"
    col = "FF101010" if hi else "FFFFFFFF"
    pad = " " * indent
    return "\n".join([
        '%s<control type="button" id="%d">' % (pad, ids()),
        pad + '    <width>auto</width>', pad + '    <height>%d</height>' % height,
        pad + '    <font>%s</font>' % font, pad + '    <textoffsetx>16</textoffsetx>',
        pad + '    <align>center</align>', pad + '    <aligny>center</aligny>',
        pad + '    <enable>false</enable>',
        pad + '    <textcolor>%s</textcolor>' % col, pad + '    <disabledcolor>%s</disabledcolor>' % col,
        pad + '    <texturefocus border="12">%s</texturefocus>' % tex,
        pad + '    <texturenofocus border="12">%s</texturenofocus>' % tex,
        pad + '    <label>%s</label>' % label, pad + '    <visible>%s</visible>' % visible,
        pad + '</control>'])


def hidden_fade(indent):
    # сколько карточки видны, решает сервис (держит признак K9.StartSeconds
    # секунд, по умолчанию 8) - здесь только затухание (п. 32)
    pad = " " * indent
    return "\n".join([pad + '<animation type="Hidden">',
                      pad + '    <effect type="fade" start="100" end="0" time="500" tween="sine" />',
                      pad + '</animation>'])


def build_start():
    ids = Ids(9529)
    v = [
        '        %s: плашки на старте для Kodi на Android (K9). Генерирует' % SSTART,
        '             tools/skin-android-ppi.py - руками не править.',
        '             CHANGES.md, п. 27 -->',
    ]
    # верх: логотипы видео | звук
    cw, ch = 420, 88
    left = (1920 - cw) // 2
    v += ['        <control type="group" id="%d">' % ids(),
          '            <depth>DepthOSD+</depth>',
          '            <visible>%s + %s + %s</visible>' % (ACTIVE, LOGOS_ON, SHOW),
          '            <visible>!Window.IsVisible(videoosd)</visible>',
          hidden_fade(12),
          '            <left>%d</left>' % left, '            <top>40</top>',
          # положение - по штатной настройке «Значки кодеков при старте видео»
          '            <animation effect="slide" start="0,0" end="%d,0" time="0" condition="Skin.HasSetting(osd.useleftCodecStartupLogos)">Conditional</animation>' % (40 - left),
          '            <animation effect="slide" start="0,0" end="%d,0" time="0" condition="Skin.HasSetting(osd.userightCodecStartupLogos)">Conditional</animation>' % (1920 - 40 - cw - left),
          ictl(ids, 12, "image", left=0, top=0, width=cw, height=ch, texture=("k9ppi/glass.png", 22)),
          ictl(ids, 12, "image", left=209, top=19, width=2, height=50, texture="k9ppi/hline.png")]
    known = []
    for hdr, logo in VIDEO_LOGOS:
        known.append("String.IsEqual(VideoPlayer.HdrType,%s)" % hdr)
        v.append(ictl(ids, 12, "image", left=30, top=16, width=150, height=56, aspectratio="keep",
                      texture="codecs/%s.png" % logo, visible=known[-1]))
    v.append(ictl(ids, 12, "image", left=30, top=16, width=150, height=56, aspectratio="keep",
                  texture="codecs/SDR.png", visible="!" + " + !".join(known)))
    for logo, codecs in AUDIO_LOGOS:
        cond = " | ".join("String.IsEqual(VideoPlayer.AudioCodec,%s)" % c for c in codecs.split())
        v.append(ictl(ids, 12, "image", left=240, top=16, width=150, height=56, aspectratio="keep",
                      texture="codecs/%s.png" % logo, visible=cond))
    v.append('        </control>')

    # низ: две отдельные карточки - звук и видео. Чего нет, того и нет: у
    # дорожки без имени и языка остаётся одна карточка видео на нижнем месте, без
    # видео - одна карточка звука там же (п. 28)
    bw = 1240
    has_video = "!String.IsEmpty(%s)" % (MI % "Video.Kind")
    has_name = "!String.IsEmpty(%s)" % (MI % "AudioStreamTitle")
    # без названия дорожки карточку звука не рисуем: формат уже есть логотипом сверху
    has_audio = has_name
    v += ['        <control type="group" id="%d">' % ids(),
          '            <depth>DepthOSD+</depth>',
          '            <visible>%s + %s + !Skin.HasSetting(K9.HideStartBottom)</visible>' % (ACTIVE, SHOW),
          '            <visible>%s | %s</visible>' % (has_audio, has_video),
          '            <visible>!Window.IsVisible(videoosd)</visible>',
          hidden_fade(12),
          '            <left>%d</left>' % ((1920 - bw) // 2)]
    low, high, ch = 944, 860, 72          # верх нижней и верхней карточки, высота
    # звук: на верхнем месте, если есть видео, иначе на нижнем
    for top, where in ((high, has_video), (low, "!" + has_video)):
        name = "$INFO[%s]" % (MI % "AudioStreamTitle")   # язык | имя, склеивает сервис
        fmt = "$INFO[%s]" % (MI % "AudioFormat")
        v += ['            <control type="group" id="%d">' % ids(),
              '                <top>%d</top>' % top,
              '                <visible>%s + %s</visible>' % (has_audio, where),
              ictl(ids, 16, "image", left=0, top=0, width=bw, height=ch, texture=("k9ppi/glass.png", 22)),
              '                <control type="grouplist" id="%d">' % ids(),
              '                    <left>30</left>', '                    <top>12</top>',
              '                    <width>%d</width>' % (bw - 60), '                    <height>48</height>',
              '                    <orientation>horizontal</orientation>', '                    <align>center</align>',
              '                    <itemgap>16</itemgap>', '                    <usecontrolcoords>true</usecontrolcoords>',
              # язык | имя крупно, формат плашкой
              ictl(ids, 20, "label", width="auto", height=48, aligny="center", font="k9_title",
                   textcolor="FFFFFFFF", label=name),
              chip(ids, 20, fmt, "!String.IsEmpty(%s)" % (MI % "AudioFormat")),
              '                </control>',
              '            </control>']
    p = lambda k: MI % ("Video." + k)  # noqa: E731
    v += ['            <control type="group" id="%d">' % ids(),
          '                <top>%d</top>' % low,
          '                <visible>%s</visible>' % has_video,
          ictl(ids, 16, "image", left=0, top=0, width=bw, height=ch, texture=("k9ppi/glass.png", 22)),
          '                <control type="grouplist" id="%d">' % ids(),
          '                    <left>30</left>', '                    <top>13</top>',
          '                    <width>%d</width>' % (bw - 60), '                    <height>46</height>',
          '                    <orientation>horizontal</orientation>', '                    <align>center</align>',
          '                    <itemgap>12</itemgap>', '                    <usecontrolcoords>true</usecontrolcoords>',
          chip(ids, 20, "$INFO[%s]" % p("Kind"), has_video, hi=True),
          chip(ids, 20, "FEL", "String.IsEqual(%s,FEL)" % p("Layer"), hi=True),
          chip(ids, 20, "MEL", "String.IsEqual(%s,MEL)" % p("Layer"))]
    for k in ("Frame", "Fps", "Codec"):
        v.append(chip(ids, 20, "$INFO[%s]" % p(k), "!String.IsEmpty(%s)" % p(k)))
    v += ['                </control>', '            </control>', '        </control>', '        ' + SEND]
    return "\n".join(v) + "\n"


# штатные бейджи (2/3/4) и прежняя плашка (9500) на Android не нужны - их
# заменяет build_start(); на CoreELEC они как были
OLD_START_GROUPS = ('<control type="group" id="2">', '<control type="group" id="3">',
                    '<control type="group" id="4">', '<control type="group" id="9500">')
NOT_ANDROID = "<visible>%s</visible>" % INACTIVE
OLD_NOT_ANDROID = "<visible>!System.Platform.Android</visible>"   # до п. 35


def patch_fullscreen(raw):
    raw = raw.replace(OLD_NOT_ANDROID, NOT_ANDROID)
    for head in OLD_START_GROUPS:
        i = raw.index(head) + len(head)
        nxt = raw[i:i + 200]
        if NOT_ANDROID not in nxt:
            raw = raw[:i] + "\n            " + NOT_ANDROID + raw[i:]
    blk = build_start()
    if SSTART in raw:
        a = raw.index("        " + SSTART)
        b = raw.index(SEND, a) + len(SEND) + 1
        return raw[:a] + blk + raw[b:]
    i = raw.rindex("</controls>")   # в этом файле без отступа
    return raw[:i] + blk + raw[i:]


def main():
    apply_ = "--apply" in sys.argv[1:]
    raw = open(DIALOG, encoding="utf-8").read()

    # значки групп - символы font_tiny_iconic из прежней панели
    icons = {}
    for name in ("Video", "System", "Audio", "DV Configuration"):
        i = raw.index("<!-- %s Icon -->" % name)
        icons[name] = re.search(r"<label>(.*?)</label>", raw[i:]).group(1)
    icons["Output"] = ""   # fa-tv

    raw = raw.replace("<visible>!System.Platform.Android</visible>", "<visible>%s</visible>" % INACTIVE)
    block = build(icons)
    if START in raw:
        i = raw.index("        " + START)
        j = raw.index(END, i) + len(END) + 1
        new = raw[:i] + block + raw[j:]
    else:
        i = raw.rindex("    </controls>")
        new = raw[:i] + block + raw[i:]
    ET.fromstring(new.encode("utf-8"))  # разметка должна остаться валидной

    fraw = open(FONTS, encoding="utf-8").read()
    fnew = patch_fonts(fraw)
    ET.fromstring(fnew.encode("utf-8"))

    sraw = open(FULLSCREEN, encoding="utf-8").read()
    snew = patch_fullscreen(sraw)
    ET.fromstring(snew.encode("utf-8"))

    tex = textures()
    stale = [n for n in tex if not os.path.exists(os.path.join(MEDIA, n + ".png"))]
    print("%s: панель Android%s" % (DIALOG, "" if new != raw else " (без изменений)"))
    print("%s: шрифты %s%s" % (FONTS, ", ".join(f[0] for f in K9_FONTS),
                                "" if fnew != fraw else " (без изменений)"))
    print("%s: %d текстур, новых %d" % (MEDIA, len(tex), len(stale)))
    print("%s: плашки на старте%s" % (FULLSCREEN, "" if snew != sraw else " (без изменений)"))
    if not apply_:
        print("это план; вписать - skin-android-ppi.py --apply, на бокс - ./bin/k9-kodi.sh update --apply")
        return
    open(DIALOG, "w", encoding="utf-8").write(new)
    open(FONTS, "w", encoding="utf-8").write(fnew)
    open(FULLSCREEN, "w", encoding="utf-8").write(snew)
    os.makedirs(MEDIA, exist_ok=True)
    for name, im in tex.items():
        im.save(os.path.join(MEDIA, name + ".png"), optimize=True)
    print("вписано")


if __name__ == "__main__":
    main()
