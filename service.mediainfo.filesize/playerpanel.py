# -*- coding: utf-8 -*-
"""Строки панели информации о воспроизведении для Kodi на Android.

Панель скина (DialogPlayerProcessInfo.xml, на пульте - «перемотка вперёд»)
на приставке CoreELEC строится на полях Player.Process(amlogic.*, video.*.raw,
video.dovi.*), которые отдаёт только сборка CoreELEC. В Kodi на Android их нет,
и половина панели там пустая. Поэтому на Android скин показывает свою панель,
а строки для неё собирает этот модуль - из того, что есть:

- поля Kodi (Player.Process(videowidth), VideoPlayer.HdrType, HdrDetail - это
  профиль Dolby Vision, битрейты, очереди, звук);
- /sys бокса Amlogic (Kinhank K9): что реально ушло на HDMI (режим, частота,
  глубина цвета, DV), идёт ли сборка FEL модулем dvfel (путь в /sys/class/vfm/map),
  температура. Kodi - обычное приложение (untrusted_app), но эти файлы ему
  читать можно - так же их читает строка состояния K9 (garik128,
  android/k9bar);
- размер файла и средний битрейт - как в списках (кэш сервиса);
- яркость из метаданных (мастеринг, MaxCLL/MaxFALL) - из .hdrinfo.json в
  корне медиатеки на NAS: его заранее считает tools/hdr-scan.py.
  Kodi FEL этих полей не отдаёт, а ffprobe на боксе нет.

Панель - карточками (с 1.6.0): свойства окна Home K9Info.<имя> (список - в
rows(), раскладка - tools/skin-android-ppi.py). Обновляются
раз в секунду, пока панель открыта; пустые не выставляются, скин их прячет.
Битрейт видео копится раз в секунду всё время воспроизведения - для столбиков,
Ø и пика.
Разбор - README.md.
"""

import json
import os
import re
import threading

import xbmc
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
PERIOD = 1.0
PREFIX = 'K9Info.'

HDMI = '/sys/class/amhdmitx/amhdmitx0'
VFM_MAP = '/sys/class/vfm/map'
FEL_VERSION = '/sys/module/dvfel/version'

HDR_NAMES = {'dolbyvision': 'Dolby Vision', 'hdr10': 'HDR10', 'hdr10plus': 'HDR10+',
             'hlg': 'HLG'}
AUDIO_NAMES = {'truehd_atmos': 'TrueHD Atmos', 'truehd': 'TrueHD', 'eac3_ddp_atmos': 'DD+ Atmos',
               'eac3': 'Dolby Digital Plus', 'ac3': 'Dolby Digital', 'dtshd_ma_x': 'DTS:X',
               'dtshd_ma_x_imax': 'DTS:X IMAX', 'dtshd_ma': 'DTS-HD MA', 'dtshd_hra': 'DTS-HD HRA',
               'dts': 'DTS', 'aac': 'AAC', 'flac': 'FLAC', 'opus': 'Opus', 'mp3': 'MP3',
               'pcm': 'PCM'}
CHANNELS = {'1': '1.0', '2': '2.0', '3': '2.1', '6': '5.1', '7': '6.1', '8': '7.1'}
# VIC -> (кадр, частота) по CTA-861, только то, что отдаёт K9; как vicName в k9bar
VIC = {'4': ('1280x720p', 60), '19': ('1280x720p', 50), '16': ('1920x1080p', 60),
       '31': ('1920x1080p', 50), '32': ('1920x1080p', 24), '33': ('1920x1080p', 25),
       '34': ('1920x1080p', 30), '93': ('3840x2160p', 24), '94': ('3840x2160p', 25),
       '95': ('3840x2160p', 30), '96': ('3840x2160p', 50), '97': ('3840x2160p', 60),
       '98': ('4096x2160p', 24)}
FRACTIONAL = {24: '23.976', 30: '29.97', 60: '59.94'}
# Решение Kodi FEL о сборке слоя: на первом пакете он разбирает RPU (libdovi,
# el_type) и, если это не FEL, пишет одну из этих строк. Других следов MEL нет:
# в путь dvfel видео просто не идёт.
NO_FEL = 'AddData: no FEL composition ('
LOG_TAIL = 512 * 1024
HDRINFO = '.hdrinfo.json'   # кэш bin/hdr-scan.py, ищется вверх по пути файла
SPACES = {'444': '4:4:4', '422': '4:2:2', '420': '4:2:0', 'rgb': 'RGB'}

HISTORY = 26        # секунд битрейта на столбиках панели (BARS в skin-android-ppi.py)
LEVELS = 20         # кольца и столбики - картинки 00..20 в media/k9ppi скина
TEMP_RANGE = (30, 90)   # °C, во что вписано кольцо температуры
AMBER = '[COLOR FFFFB74D]%s[/COLOR]'
GAUGES = ('Cache', 'VQueue', 'AQueue', 'Cpu', 'Mem', 'Soc', 'Gpu')


# Отладка: такой файл в профиле аддона - вести себя как бокс без Amlogic (не
# читать /sys), чтобы проверить на K9, как панель выглядит на чужом железе.
SIMULATE_GENERIC = 'special://profile/addon_data/service.mediainfo.filesize/simulate-generic'


def coreelec():
    try:
        with open('/etc/os-release', errors='replace') as fh:
            return 'coreelec' in fh.read().lower()
    except (IOError, OSError):
        return False


def available():
    """Панель и плашки на старте - на любом Kodi, кроме CoreELEC: там у скина
    своя панель на полях сборки (Player.Process(amlogic.*)) и свой av.change.
    Что берётся из /sys бокса Amlogic, на другом железе просто прячется."""
    return not coreelec()


def amlogic():
    return os.path.isdir(HDMI) and not xbmcvfs.exists(SIMULATE_GENERIC)


def read(path):
    try:
        with open(path, 'r', errors='replace') as fh:
            return fh.read().strip()
    except (IOError, OSError):
        return None


def info(label):
    """Инфолейбл Kodi. Незнакомый (VideoPlayer.HdrDetail появился только в Kodi 22)
    Kodi возвращает своим же именем - это пусто, а не значение."""
    value = xbmc.getInfoLabel(label).strip()
    return '' if value == label else value


def number(label):
    """Число из Player.Process: Kodi форматирует по локали (3,840)."""
    return info(label).replace(',', '').replace('\xa0', '')


def kv(text, key):
    for line in (text or '').splitlines():
        if line.startswith(key + ':'):
            return line.split(':', 1)[1].strip()
    return ''


def zero(value):
    return value in ('', '0', '0.0', '0.00', '0.000', 'unknown')


def thermal_zone(kind):
    base = '/sys/class/thermal'
    try:
        for z in os.listdir(base):
            if read(os.path.join(base, z, 'type')) == kind:
                return os.path.join(base, z, 'temp')
    except OSError:
        pass
    return None


def dot(*parts):
    return ' · '.join(p for p in parts if p)


def mbits(text):
    """«69.3 Mbit/s», «850 kbit/s», «100.8 Мбит/с» (Kodi переводит единицы) -> Мбит/с;
    None - не разобрать."""
    m = re.match(r'\s*([\d.,]+)\s*(\w?)', text or '')
    if not m:
        return None
    try:
        # 3,409 - разделитель тысяч, 69,3 - десятичная запятая
        v = float(re.sub(r',(?=\d{3}$)', '', m.group(1)).replace(',', '.'))
    except ValueError:
        return None
    unit = m.group(2).lower()
    if unit in ('k', 'к'):
        return v / 1000.0
    if unit in ('g', 'г'):
        return v * 1000.0
    return v


def percent(text):
    m = re.search(r'(\d+(?:[.,]\d+)?)', text or '')
    return int(round(float(m.group(1).replace(',', '.')))) if m else None


def resolution_class(w, h):
    try:
        w, h = int(w), int(h)
    except ValueError:
        return ''
    if w >= 3800 or h >= 2100:
        return '4K'
    if w >= 1900 or h >= 1000:
        return '1080p'
    if w >= 1270 or h >= 700:
        return '720p'
    return '%dp' % h if h else ''


def bit_depth(pix, hdr):
    pix = (pix or '').lower()
    if '12' in pix:
        return '12 бит'
    if '10' in pix or 'p010' in pix:
        return '10 бит'
    if hdr:
        return '10 бит'
    return '8 бит' if pix and not zero(pix) else ''


def container_of(path):
    ext = os.path.splitext(path.split('?')[0])[1].lower().lstrip('.')
    return {'mkv': 'MKV', 'mp4': 'MP4', 'm2ts': 'BDAV', 'ts': 'TS', 'iso': 'ISO'}.get(ext, ext.upper())


class PlayerPanel(threading.Thread):
    def __init__(self, sizes):
        super().__init__(daemon=True)
        self.sizes = sizes  # путь -> [байты, кбит/с] из кэша сервиса
        self.monitor = xbmc.Monitor()
        self.amlogic = amlogic()      # вывод HDMI, термодатчики и dvfel - из /sys
        self.zones = ((thermal_zone('soc_thermal'), thermal_zone('gpu_thermal'))
                      if self.amlogic else (None, None))
        self.fel_version = None
        self.size_of = {}
        self.decision = (None, None)  # (файл, причина из журнала Kodi FEL)
        self.meta = (None, None)      # (файл, запись .hdrinfo.json)
        self.hdrinfo = {}             # путь кэша -> {относительный путь: запись}
        self.history = []             # битрейт видео по секундам, Мбит/с
        self.rate_file = None
        self.rate_sum = [0.0, 0, 0.0]  # сумма, отсчётов, пик - за просмотр файла
        self.audio_key, self.audio_pos = None, (0, 0)

    def video_parts(self):
        """Части строки про видео для плашки на старте: {Kind, Layer, Frame, Fps,
        Codec} - «Dolby Vision 7», «FEL», «3840x2160», «23.976 к/с», «HEVC».
        Пусто, пока Kodi не отдал размер кадра. Второй результат - можно ли
        считать их окончательными: у DV профиля 7 решение FEL/MEL Kodi
        принимает на первом пакете, до этого слой ещё не известен."""
        w, h = number('Player.Process(videowidth)'), number('Player.Process(videoheight)')
        if zero(w):
            return {}, False
        hdr = info('VideoPlayer.HdrType')
        profile = self.dv_profile(hdr)
        layer, _ = self.fel(hdr, profile)
        final, tag = True, ''
        kind = HDR_NAMES.get(hdr, hdr or 'SDR')
        if hdr == 'dolbyvision':
            kind = ' '.join(x for x in (kind, profile) if x)
            if layer.startswith('FEL'):
                tag = 'FEL'
            elif layer.startswith('MEL'):
                tag = 'MEL'
            elif profile.startswith('7'):
                final = False
        fps = info('Player.Process(videofps)')
        return {'Kind': kind, 'Layer': tag, 'Frame': '%sx%s' % (w, h),
                'Fps': '' if zero(fps) else '%s к/с' % fps,
                'Codec': info('VideoPlayer.VideoCodec').upper()}, final

    def dv_profile(self, hdr):
        """Профиль Dolby Vision: от Kodi (VideoPlayer.HdrDetail, с Kodi 22), а если он
        не отдаёт (Kodi 21) - номер из .hdrinfo.json (bin/hdr-scan.py считает его по
        RPU файла: 5, 7, 8). Пусто - профиль неизвестен."""
        if hdr != 'dolbyvision':
            return ''
        profile = info('VideoPlayer.HdrDetail')
        if not profile:
            meta = self.hdr_meta() or {}
            if meta.get('dv'):
                profile = str(meta['dv'])
        return profile

    def video_line(self):
        """Одной строкой: «Dolby Vision 7.6 FEL | 3840x2160 23.976 к/с | HEVC»."""
        p, final = self.video_parts()
        if not p:
            return '', False
        kind = ' '.join(x for x in (p['Kind'], p['Layer']) if x)
        frame = ' '.join(x for x in (p['Frame'], p['Fps']) if x)
        return ' | '.join(x for x in (kind, frame, p['Codec']) if x), final

    def run(self):
        shown = set()
        while not self.monitor.abortRequested():
            self.sample()
            if xbmc.getCondVisibility('Window.IsVisible(playerprocessinfo)'):
                try:
                    values = self.rows()
                    for name, value in values.items():
                        HOME.setProperty(PREFIX + name, value)
                    for name in shown - set(values):
                        HOME.clearProperty(PREFIX + name)
                    shown = set(values)
                except Exception as exc:  # noqa: BLE001 - панель не должна ронять сервис
                    xbmc.log('[service.mediainfo.filesize] panel: %s' % exc, xbmc.LOGWARNING)
                wait = PERIOD
            else:
                for name in shown:
                    HOME.clearProperty(PREFIX + name)
                shown = set()
                wait = PERIOD if xbmc.getCondVisibility('Player.HasVideo') else 0.5
            if self.monitor.waitForAbort(wait):
                break

    def sample(self):
        """Битрейт видео раз в секунду, пока играет видео: столбики панели
        показывают последние HISTORY секунд, Ø и пик - за весь просмотр файла."""
        if not xbmc.getCondVisibility('Player.HasVideo'):
            if self.history:
                self.history, self.rate_file, self.rate_sum = [], None, [0.0, 0, 0.0]
            return
        path = info('Player.Filenameandpath')
        if path != self.rate_file:
            self.history, self.rate_file, self.rate_sum = [], path, [0.0, 0, 0.0]
        mbit = mbits(info('Player.Process(videolivebitrate)'))
        if mbit is None or xbmc.getCondVisibility('Player.Paused'):
            return
        self.history = (self.history + [mbit])[-HISTORY:]
        self.rate_sum[0] += mbit
        self.rate_sum[1] += 1
        self.rate_sum[2] = max(self.rate_sum[2], mbit)

    def rows(self):
        """Свойства панели: имя без префикса K9Info. -> текст. Пустых не отдаём -
        скин прячет то, чего нет (бейдж, строку слоя, кольцо)."""
        r = {}
        hdr = info('VideoPlayer.HdrType')
        profile = self.dv_profile(hdr)
        layer, module = self.fel(hdr, profile)
        meta = self.hdr_meta() if hdr else None
        output, color, dv_out, out_hz = self.hdmi()
        w, h = number('Player.Process(videowidth)'), number('Player.Process(videoheight)')
        fps = info('Player.Process(videofps)')
        codec = info('VideoPlayer.VideoCodec').upper()
        size, kbps = self.file_size()

        # --- шапка: что играет и где ---
        chapter, chapters = info('Player.Chapter'), info('Player.ChapterCount')
        r['Where'] = dot(info('VideoPlayer.Title'),
                         'глава %s / %s' % (chapter, chapters) if not zero(chapters) and not zero(chapter) else '',
                         '%s / %s' % (info('Player.Time'), info('Player.Duration')))

        # --- видео ---
        kind = HDR_NAMES.get(hdr, hdr or 'SDR')
        r['VideoBig'] = dot(resolution_class(w, h), kind)
        if layer.startswith('FEL'):
            r['VideoTag'] = 'FEL'
        elif layer.startswith('MEL'):
            r['VideoTag'] = 'MEL'
        depth = bit_depth(info('Player.Process(pixformat)'), hdr)
        dar = info('Player.Process(videodar)')
        r['VideoSub'] = dot(codec, depth, '' if zero(fps) else '%s к/с' % fps,
                            '' if zero(dar) else '%s:1' % dar.rstrip('0').rstrip('.') if ':' not in dar else dar)
        dec = info('Player.Process(videodecoder)')
        r['VideoSub2'] = dot('' if zero(w) else '%sx%s' % (w, h), '' if zero(dec) else dec,
                             size and '%.1f GB' % (size / 1024.0 ** 3))

        # --- звук ---
        acodec = info('VideoPlayer.AudioCodec')
        if acodec:
            r['AudioBig'] = ' '.join(x for x in (AUDIO_NAMES.get(acodec, acodec.upper()),
                                                  CHANNELS.get(info('VideoPlayer.AudioChannels'), '')) if x)
        lang = HOME.getProperty('MediaInfo.AudioStreamLang') or info('VideoPlayer.AudioLanguage').upper()
        if lang in ('UND', 'UNK'):
            lang = ''
        name = HOME.getProperty('MediaInfo.AudioStreamName') or info('VideoPlayer.AudioName')
        r['AudioSub'] = ' | '.join(x for x in (lang, name) if x)
        index, count = self.audio_index()
        adec = info('Player.Process(audiodecoder)')
        passthrough = adec.lower().startswith(('pt-', 'pt_'))  # pt-eac3, pt-truehd...
        out = 'битстрим' if passthrough else ('' if zero(adec) else 'декодирует Kodi')
        rate, bits = number('Player.Process(audiosamplerate)'), number('Player.Process(audiobitspersample)')
        hz = ''
        # при битстриме Kodi отдаёт параметры упаковки для HDMI (8 бит), а не звука
        if not zero(rate) and not passthrough:
            hz = '%s кГц' % ('%.1f' % (int(rate) / 1000.0)).rstrip('0').rstrip('.')
            if not zero(bits):
                hz += ' / %s бит' % bits
        abr = info('Player.Process(audiolivebitrate)')
        r['AudioSub2'] = dot('дорожка %d из %d' % (index, count) if count > 1 else '', out, hz,
                             '' if abr.startswith('0 ') else abr, self.subtitles())

        # --- выход HDMI ---
        if output:
            frame, _, rate_txt = output.partition(' ')
            r['OutBig'] = dot(frame.split('x')[-1], rate_txt)
        r['OutSub'] = color
        sync = self.rate_mismatch(fps, out_hz)
        r['OutSub2'] = AMBER % sync if sync.startswith('кадр') else sync

        # --- Dolby Vision / HDR: три строки-слоя ---
        nits = lambda v: ('%.4f' % v).rstrip('0').rstrip('.')  # noqa: E731
        mdl = cll = ''
        if meta and meta.get('mdl'):
            low, peak = meta['mdl']
            mdl = 'мастеринг %s нит' % nits(peak) + ('' if low is None else ' (чёрный %s)' % nits(low))
        if meta and meta.get('cll'):
            cll = 'MaxCLL %s · MaxFALL %s' % tuple(nits(v) for v in meta['cll'])
        if hdr == 'dolbyvision':
            r['DvTitle'] = 'DOLBY VISION'
            # профиль Kodi отдаёт с 22-й версии; без него о слое EL сказать нечего, а
            # модуль сборки FEL - не про этот Kodi (сборка FEL основана на Kodi 22)
            r['DvInfo'] = (dot('профиль %s' % profile, module if module != 'не загружен' else '')
                           if profile else 'профиль: Kodi этой версии не сообщает')
            r['L1Tag'], r['L1Style'] = 'RPU', 'dashed'
            r['L1Text'] = dot('метаданные', mdl, cll)
            p7 = profile.startswith('7')
            r['L2Tag'] = 'EL' if profile else ''
            if not profile:
                pass
            elif layer.startswith('FEL'):
                r['L2Style'] = 'solid'
                r['L2Text'] = dot('[B]FEL[/B]', 'полный слой улучшения', layer.split(', ', 1)[-1])
            elif layer.startswith('MEL'):
                r['L2Style'] = 'dim'
                r['L2Text'] = dot('[B]MEL[/B]', 'слой без данных, собирать нечего')
            elif p7 and module == 'не загружен':
                # нет модуля сборки FEL (обычный Kodi, другой бокс) - играет базовый слой
                r['L2Style'] = 'dim'
                r['L2Text'] = 'не используется: нет сборки FEL'
            elif p7:
                r['L2Style'] = 'dim'
                r['L2Text'] = layer or 'ещё не известно'
            else:
                r['L2Style'] = 'dim'
                r['L2Text'] = 'нет, однослойный профиль'
            r['L3Tag'], r['L3Style'] = 'BL', 'solid'
            base = {'5': 'IPT, без совместимости', '8': 'совместим с HDR10', '7': 'HDR10'}
            r['L3Text'] = dot('базовый слой', codec, '' if zero(w) else '%sx%s' % (w, h),
                              base.get(profile[:1], ''))
        elif hdr:
            r['DvTitle'] = kind.upper()
            r['DvInfo'] = 'статические метаданные' if hdr != 'hlg' else 'без метаданных'
            if dv_out:
                r['DvInfo'] = dot(r['DvInfo'], 'на выходе Dolby Vision')
            rows = [('EOTF', 'PQ (SMPTE ST 2084)' if hdr != 'hlg' else 'HLG (ARIB STD-B67)')]
            if mdl:
                rows.append(('MDL', mdl))
            if cll:
                rows.append(('CLL', cll))
            for n, (tag, line) in enumerate(rows, 1):
                r['L%dTag' % n], r['L%dStyle' % n], r['L%dText' % n] = tag, 'solid', line
        else:
            r['DvTitle'] = 'SDR'
            r['DvInfo'] = 'на выходе Dolby Vision' if dv_out else ''
            r['L1Tag'], r['L1Style'], r['L1Text'] = 'BT.709', 'dim', 'стандартный динамический диапазон'

        # --- поток ---
        if self.history:
            now = self.history[-1]
            top = max(max(self.history), 1.0)
            r['Rate'] = '%.1f' % now
            r['RateUnit'] = 'Мбит/с'
            total, n, peak = self.rate_sum
            r['RateSub'] = dot(n and 'Ø %.1f' % (total / n), 'пик %.1f' % peak)
            pad = HISTORY - len(self.history)
            for i, v in enumerate(self.history):
                r['Bar.%d' % (pad + i)] = '%02d' % max(1, round(LEVELS * v / top))
        elif kbps:
            # живого битрейта нет (Kodi 21: Player.Process(videolivebitrate) - с 22-й) -
            # крупно средний по файлу, без графика
            r['Rate'] = '%.1f' % (kbps / 1000.0)
            r['RateUnit'] = 'Мбит/с'
            r['RateSub'] = 'в среднем по файлу'
            kbps = 0   # в нижней строке не повторять
        path = info('Player.Filenameandpath')
        r['StreamInfo'] = dot(container_of(path), os.path.basename(path.rstrip('/')))
        r['StreamFoot'] = dot(size and 'файл %.1f GB' % (size / 1024.0 ** 3),
                              kbps and 'в среднем по файлу %.1f Мбит/с' % (kbps / 1000.0))

        # --- кольца ---
        gauge = {
            'Cache': percent(info('Player.CacheLevel')),
            'VQueue': percent(info('Player.Process(videoqueuelevel)')),
            'AQueue': percent(info('Player.Process(audioqueuelevel)')),
            'Cpu': percent(info('System.CPUUsage')),
            'Mem': percent(info('System.Memory(used.percent)')),
        }
        for key, value in gauge.items():
            if value is not None:
                r['G.%s' % key] = '%d' % value
                r['G.%s.Ring' % key] = '%02d' % round(LEVELS * min(value, 100) / 100.0)
        for key, t in zip(('Soc', 'Gpu'), self.temps()):
            if t is not None:
                lo, hi = TEMP_RANGE
                r['G.%s' % key] = '%d°' % t
                r['G.%s.Ring' % key] = '%02d' % round(LEVELS * min(max(t - lo, 0), hi - lo) / (hi - lo))
        return {k: v for k, v in r.items() if v}

    def subtitles(self):
        if not xbmc.getCondVisibility('VideoPlayer.HasSubtitles'):
            return ''
        if xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled'):
            # имени дорожки субтитров инфолейблом Kodi 22 не отдаёт - только язык
            return 'субтитры %s' % (info('VideoPlayer.SubtitlesLanguage') or 'вкл')
        return 'субтитры выкл'

    def audio_index(self):
        """(номер дорожки с 1, всего) - JSON-RPC, инфолейбла для номера нет.
        Кэш на файл и выбранную дорожку."""
        key = (info('Player.Filenameandpath'), HOME.getProperty('MediaInfo.AudioStream'))
        if self.audio_key == key:
            return self.audio_pos
        pos = (0, 0)
        try:
            players = json.loads(xbmc.executeJSONRPC(json.dumps(
                {'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetActivePlayers'}))).get('result') or []
            pid = [p['playerid'] for p in players if p.get('type') == 'video']
            if pid:
                res = json.loads(xbmc.executeJSONRPC(json.dumps(
                    {'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetProperties',
                     'params': {'playerid': pid[0], 'properties': ['audiostreams', 'currentaudiostream']}}))
                ).get('result') or {}
                streams = res.get('audiostreams') or []
                cur = (res.get('currentaudiostream') or {}).get('index', -1)
                if streams:
                    pos = (cur + 1, len(streams))
        except Exception:  # noqa: BLE001
            pass
        self.audio_key, self.audio_pos = key, pos
        return pos

    # --- источники ---

    def hdmi(self):
        """(режим, цвет, идёт ли DV) - что реально ушло на HDMI. Без Amlogic
        пусто: System.ScreenResolution на Android - режим интерфейса Kodi (1080p),
        а не то, что уходит на телевизор, - карточку «Выход» скин тогда прячет."""
        cfg = read(HDMI + '/config') if self.amlogic else None
        if cfg is None:
            return '', '', False, 0.0
        status = read(HDMI + '/hdmi_hdr_status') or ''
        vic = kv(cfg, 'cur_VIC')
        frame, hz = VIC.get(vic, ('VIC %s' % vic if vic else '', 0))
        out_hz = float(hz)
        if hz:
            # frac_rate_policy=1: 24/30/60 Гц уходят как 23.976/29.97/59.94
            rate = FRACTIONAL.get(hz) if read(HDMI + '/frac_rate_policy') == '1' else None
            frame += ' %s Гц' % (rate or hz)
            if rate:
                out_hz = float(rate)
        depth = kv(cfg, 'colordepth').replace('bit', ' бит')
        space = SPACES.get(kv(cfg, 'colorspace').lower(), kv(cfg, 'colorspace'))
        signal = status.replace('DolbyVision-Std', 'Dolby Vision') \
            .replace('DolbyVision-Lowlatency', 'Dolby Vision LL')
        color = ', '.join(x for x in (signal, ' '.join(y for y in (depth, space) if y)) if x)
        return frame, color, status.startswith('DolbyVision'), out_hz

    @staticmethod
    def rate_mismatch(fps, out_hz):
        """Источник и выход расходятся (24.000 на 23.976 Гц): раз в столько
        секунд кадр пропадёт или повторится. Кратные частоты (24 на 48) - не
        расхождение."""
        try:
            src = float(fps)
        except ValueError:
            return ''
        if not src or not out_hz:
            return ''
        n = max(1, round(out_hz / src))
        diff = abs(out_hz / n - src)
        if diff < 0.005:
            return 'частота совпадает'
        # обе частоты видны строками «Выход HDMI» и «Источник»
        return 'кадр раз в %d с' % round(1 / diff)

    def fel(self, hdr, profile):
        """(слой EL, модуль) по пути vfm: dvfel между video_composer и render."""
        lines = (read(VFM_MAP) or '').splitlines() if self.amlogic else []
        if not any('dvfel' in line for line in lines):
            self.fel_version = None
            return '', 'не загружен'
        if self.fel_version is None:
            self.fel_version = read(FEL_VERSION) or ''
        module = 'dvfel %s' % self.fel_version if self.fel_version else 'dvfel'
        if any(line.startswith('[') and 'dvfel' in line and 'video_composer' in line for line in lines):
            return 'FEL, собирается', module
        if hdr == 'dolbyvision' and profile.startswith('7'):
            why = self.fel_decision()
            if why == 'not a FEL stream':
                return 'MEL, собирать нечего', module
            if why:
                return 'FEL, но сборка не запустилась (%s)' % why, module
            return 'не собирается', module
        return '', module

    def fel_decision(self):
        """Причина из журнала Kodi FEL для играющего файла (кэш на файл)."""
        path = info('Player.Filenameandpath')
        if self.decision[0] == path:
            return self.decision[1]
        why = None
        try:
            log = xbmcvfs.translatePath('special://logpath/kodi.log')
            with open(log, 'rb') as fh:
                fh.seek(max(0, os.path.getsize(log) - LOG_TAIL))
                tail = fh.read().decode('utf-8', 'replace')
            # последнее решение в журнале - про текущий файл, если после него
            # не было старта сборки (строки CAndroidDvFel: ... started)
            i = tail.rfind(NO_FEL)
            if i >= 0 and tail.rfind('CAndroidDvFel: hardware EL decoder', i) < 0:
                why = tail[i + len(NO_FEL):tail.find(')', i)]
        except (IOError, OSError, ValueError):
            pass
        # не нашли - не запоминаем: панель могли открыть раньше, чем Kodi FEL
        # успел решить
        if why:
            self.decision = (path, why)
        return why

    def hdr_meta(self):
        """Запись .hdrinfo.json для играющего файла или None. Ищется один раз на
        файл: кэш - в каталоге файла или выше (корень медиатеки)."""
        path = info('Player.Filenameandpath')
        if path == self.meta[0]:
            return self.meta[1]
        found = None
        if path.startswith(('nfs://', 'smb://', '/')):
            folder = path.rsplit('/', 1)[0]
            for _ in range(4):
                cache = folder + '/' + HDRINFO
                if cache in self.hdrinfo or xbmcvfs.exists(cache):
                    rel = path[len(folder) + 1:]
                    files = self.hdrinfo.get(cache)
                    if files is None or rel not in files:  # новый фильм - кэш могли пересчитать
                        files = self.hdrinfo[cache] = self.load_hdrinfo(cache)
                    found = files.get(rel)
                    break
                if folder.count('/') <= 3:
                    break
                folder = folder.rsplit('/', 1)[0]
        self.meta = (path, found)
        return found

    @staticmethod
    def load_hdrinfo(cache):
        try:
            f = xbmcvfs.File(cache)
            try:
                return json.loads(f.read()).get('files', {})
            finally:
                f.close()
        except Exception as exc:  # noqa: BLE001
            xbmc.log('[service.mediainfo.filesize] %s: %s' % (cache, exc), xbmc.LOGWARNING)
            return {}

    def file_size(self):
        """(байты, средний кбит/с) играющего файла: кэш списков или stat."""
        path = info('Player.Filenameandpath')
        if not path or path.startswith(('plugin://', 'pvr://', 'http://', 'https://')):
            return 0, 0
        entry = self.sizes.get(path) or self.size_of.get(path)
        if entry is None:
            try:
                size = xbmcvfs.Stat(path).st_size()
            except Exception:  # noqa: BLE001
                size = 0
            entry = [size, 0]
            if size:
                self.size_of[path] = entry
        size, kbps = entry
        if size and not kbps:
            # в кэше списка битрейта нет, если файл выделяли в «Файлах» (там
            # длительность неизвестна) - считаем по длительности из плеера
            secs = int(info('Player.Duration(secs)') or 0)
            kbps = int(size * 8 / secs / 1000) if secs else 0
        return size, kbps

    def temps(self):
        """[SoC, GPU] в °C, None - датчика нет."""
        out = []
        for path in self.zones:
            t = read(path) if path else None
            out.append(int(t) // 1000 if t and t.lstrip('-').isdigit() else None)
        return out
