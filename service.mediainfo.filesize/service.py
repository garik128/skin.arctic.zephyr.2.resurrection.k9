# -*- coding: utf-8 -*-
"""Размер файла и битрейт выделенного элемента списка -> свойства окна Home.

Kodi не хранит размер файла в видеобиблиотеке (в MyVideos*.db его просто нет,
JSON-RPC отдаёт size: 0), а битрейта нет нигде вообще. Поэтому размер берётся
через xbmcvfs.Stat, а битрейт считается как размер * 8 / длительность.

Скину отдаются свойства окна Home (10000):
    MediaInfo.Size        "12.4 GB"
    MediaInfo.Bitrate     "14.3 Мбит/с"
    MediaInfo.SizeRaw     байты
    MediaInfo.BitrateRaw  кбит/с

Плюс имя текущей аудиодорожки играющего файла (в Kodi для неё нет инфолейбла,
VideoPlayer.AudioStreamName пустой) — скин показывает его при старте вместе с
бейджами кодеков:
    MediaInfo.AudioStream      "RUS | MVO [HDRezka] 18+ - AAC-LC stereo (AAC 2.0)"
    MediaInfo.AudioStreamName  "MVO [HDRezka] 18+ - AAC-LC stereo"
    MediaInfo.AudioStreamLang  "RUS"

Плюс признак «поток только что сменился» для Kodi на Android:
    MediaInfo.AVChange         "1" пять секунд после старта или смены потока
По нему скин показывает бейджи кодеков и имя дорожки. На приставке то же
отдаёт инфолейбл сборки CoreELEC Player.Process(av.change), в Kodi на Android
его нет, и без признака бейджи там не появлялись никогда.

И строка про видео для плашки на старте (только Android/Amlogic, её собирает
PlayerPanel.video_line):
    MediaInfo.VideoInfo        "Dolby Vision 7.6 FEL | 3840x2160 23.976 к/с | HEVC"

И строки панели информации о воспроизведении на Android (K9Info.*,
модуль playerpanel.py): на CoreELEC панель скина питается полями его сборки,
которых в Kodi на Android нет.

И даты «сегодня» и «вчера» в коротком формате региона Kodi (как у ListItem.DateAdded),
чтобы скин писал «Сегодня»/«Вчера» у роликов дополнений: считать даты скин не умеет.
    K9.DateToday       "13.11.2026"
    K9.DateYesterday   "12.11.2026"

Всё посчитанное кладётся в addon_data/service.mediainfo.filesize/cache.json,
плюс при старте и после сканирования библиотеки фильмы обходятся заранее —
чтобы при листании ничего не тормозило и не дёргало NFS.
"""

import json
import os
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import playerpanel

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
CACHE_FILE = os.path.join(PROFILE, 'cache.json')

HOME = xbmcgui.Window(10000)
POLL_INTERVAL = 0.25  # как часто опрашиваем фокус, сек
SAVE_EVERY = 10  # через сколько новых записей сбрасывать кэш на диск

PROPS = ('MediaInfo.Size', 'MediaInfo.Bitrate',
         'MediaInfo.SizeRaw', 'MediaInfo.BitrateRaw')

AUDIO_PROPS = ('MediaInfo.AudioStream', 'MediaInfo.AudioStreamName',
               'MediaInfo.AudioStreamLang', 'MediaInfo.AudioFormat',
               'MediaInfo.AudioStreamTitle')
VIDEO_PROP = 'MediaInfo.VideoInfo'
# по частям - для плашки на старте с плашками-«чипами» (CHANGES.md скина, п. 27)
VIDEO_PARTS = ('Kind', 'Layer', 'Frame', 'Fps', 'Codec')
PANEL = None  # PlayerPanel (только Android/Amlogic): он умеет собрать строку про видео
AUDIO_RETRIES = 6  # после старта/смены дорожки поток отдаётся не сразу
AUDIO_RETRY_DELAY = 0.4

# Свой признак смены потока - только там, где нет Player.Process(av.change)
# CoreELEC; держится столько же, сколько логотипы кодеков на приставке
# (coreelec.codeclogotimeout = 5).
AV_FLAG = 'MediaInfo.AVChange'
AV_FLAG_SECONDS = 8   # по умолчанию; настройка скина K9.StartSeconds (5/8/12)

# Кнопка пульта для панели информации о воспроизведении - настройка скина
# K9.PPIKey (имя клавиши Kodi: fastforward, info, red ...). Раскладку под неё
# пишет сервис, скин сам keymap положить не может (CHANGES.md скина, п. 32).
PPI_KEYMAP = 'special://profile/keymaps/skin-playerinfo.xml'
PPI_KEYS = ('fastforward', 'info', 'menu', 'red', 'green', 'yellow', 'blue', 'guide')
PPI_CHECK = 2.0  # раз в сколько секунд сверять настройку
# везде, кроме CoreELEC (там скин смотрит его Player.Process(av.change))
NEED_AV_FLAG = playerpanel.available()
# признак для скина: сервис работает - показывать наши панель и плашки на старте
# вместо панели CoreELEC (CHANGES.md скина, п. 35)
ACTIVE_PROP = 'K9Info.Active'

UNSUPPORTED = ('plugin://', 'pvr://', 'addons://', 'videodb://', 'musicdb://',
               'library://', 'upnp://', 'stack://', 'http://', 'https://')


def log(message, level=xbmc.LOGDEBUG):
    xbmc.log('[%s] %s' % (ADDON_ID, message), level)


def format_size(size):
    value = float(size)
    unit = 'B'
    for unit in ('B', 'kB', 'MB', 'GB'):
        if value < 1024.0 or unit == 'GB':
            break
        value /= 1024.0
    if unit == 'B':
        return '%d B' % value
    return '%.1f %s' % (value, unit)


def format_bitrate(kbps):
    if not kbps:
        return ''
    if kbps >= 1000:
        return '%.1f Мбит/с' % (kbps / 1000.0)
    return '%d кбит/с' % kbps


def is_supported(path):
    if not path or path.endswith('/') or path.endswith('\\'):
        return False
    return not path.lower().startswith(UNSUPPORTED)


def probe(path, duration):
    """(размер в байтах, битрейт в кбит/с) или None, если файл не достучался."""
    try:
        size = xbmcvfs.Stat(path).st_size()
    except Exception as exc:  # noqa: BLE001 - сеть может отвалиться в любой момент
        log('stat failed for %s: %s' % (path, exc))
        return None
    if not size:
        return None
    kbps = int(size * 8 / duration / 1000) if duration else 0
    return [size, kbps]


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def jsonrpc(method, params):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps(request))).get('result')
        return {} if result is None else result
    except Exception as exc:  # noqa: BLE001
        log('jsonrpc %s failed: %s' % (method, exc), xbmc.LOGWARNING)
        return {}


def clear_video():
    HOME.clearProperty(VIDEO_PROP)
    for k in VIDEO_PARTS:
        HOME.clearProperty('MediaInfo.Video.' + k)


def start_seconds():
    value = xbmc.getInfoLabel('Skin.String(K9.StartSeconds)').strip()
    return int(value) if value.isdigit() and 1 <= int(value) <= 60 else AV_FLAG_SECONDS


def sync_ppi_keymap(state):
    """Раскладка под кнопку панели информации - по настройке скина. state -
    словарь сервиса: что уже записано (чтобы не перечитывать раскладки зря)."""
    key = xbmc.getInfoLabel('Skin.String(K9.PPIKey)').strip()
    if key not in PPI_KEYS:
        key = ''
    if state.get('ppi_key') == key:
        return
    path = xbmcvfs.translatePath(PPI_KEYMAP)
    try:
        if key:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                         '<!-- пишет service.mediainfo.filesize по настройке скина K9.PPIKey;\n'
                         '     руками не править - перезапишется -->\n'
                         '<keymap>\n  <FullscreenVideo>\n    <keyboard>\n'
                         '      <%s>PlayerProcessInfo</%s>\n'
                         '    </keyboard>\n  </FullscreenVideo>\n</keymap>\n' % (key, key))
        elif os.path.exists(path):
            os.remove(path)
        elif 'ppi_key' not in state:
            state['ppi_key'] = key   # на старте записывать нечего
            return
    except OSError as exc:
        log('keymap: %s' % exc, xbmc.LOGWARNING)
        return
    state['ppi_key'] = key
    xbmc.executebuiltin('Action(reloadkeymaps)')
    log('кнопка панели информации: %s' % (key or 'нет'), xbmc.LOGINFO)


class AudioTrack(xbmc.Player):
    """Имя текущей аудиодорожки -> свойства окна Home.

    JSON-RPC (Player.GetProperties -> currentaudiostream) — единственное место,
    где Kodi отдаёт название потока: инфолейбла для него нет.
    """

    def __init__(self):
        super().__init__()
        self.updating = False
        self.av_timer = None
        self.signature = None
        self.update()

    def onAVStarted(self):
        self.signature = self.stream_signature()
        self.flag_av_change()
        self.update()

    def onAVChange(self):
        # Kodi шлёт onAVChange и после перемотки, хотя потоки те же: плашка тогда
        # не нужна. Поднимаем признак, только если сменилась дорожка или видео.
        sig = self.stream_signature()
        if sig != self.signature:
            self.signature = sig
            self.flag_av_change()
        self.update()

    @staticmethod
    def stream_signature():
        stream = AudioTrack.current_stream() or {}
        return (stream.get('index'), stream.get('codec'),
                xbmc.getInfoLabel('VideoPlayer.VideoCodec'), xbmc.getInfoLabel('VideoPlayer.HdrType'),
                xbmc.getInfoLabel('Player.Process(videowidth)'))

    def onPlayBackStopped(self):
        clear_video()
        self.clear_av_flag()
        self.signature = None
        self.publish(None)

    def onPlayBackEnded(self):
        clear_video()
        self.clear_av_flag()
        self.signature = None
        self.publish(None)

    def flag_av_change(self):
        if not NEED_AV_FLAG:
            return
        # событие приходит пачкой (старт, затем смена дорожки) - окно отсчитываем
        # от последнего
        if self.av_timer:
            self.av_timer.cancel()
        HOME.setProperty(AV_FLAG, '1')
        self.av_timer = threading.Timer(start_seconds(), self.clear_av_flag)
        self.av_timer.daemon = True
        self.av_timer.start()

    def clear_av_flag(self):
        if self.av_timer:
            self.av_timer.cancel()
            self.av_timer = None
        HOME.clearProperty(AV_FLAG)

    def update(self):
        if PANEL is not None:
            threading.Thread(target=self.refresh_video, daemon=True).start()
        if self.updating:
            return
        self.updating = True
        threading.Thread(target=self.refresh, daemon=True).start()

    def refresh_video(self):
        """Строка про видео для плашки на старте (HDR/DV, кадр, кодек). Сразу
        после старта поток ещё не отдан, а FEL/MEL Kodi решает на первом пакете -
        повторяем, пока строка не станет окончательной."""
        try:
            for _ in range(AUDIO_RETRIES * 2):
                line, final = PANEL.video_line()
                if line:
                    HOME.setProperty(VIDEO_PROP, line)
                    parts, _ = PANEL.video_parts()
                    for k in VIDEO_PARTS:
                        HOME.setProperty('MediaInfo.Video.' + k, parts.get(k, ''))
                    if final:
                        return
                xbmc.sleep(int(AUDIO_RETRY_DELAY * 1000))
        except Exception as exc:  # noqa: BLE001 - плашка не должна ронять сервис
            log('video info: %s' % exc, xbmc.LOGWARNING)

    def refresh(self):
        try:
            for attempt in range(AUDIO_RETRIES):
                stream = self.current_stream()
                if stream:
                    self.publish(stream)
                    return
                if attempt < AUDIO_RETRIES - 1:
                    xbmc.sleep(int(AUDIO_RETRY_DELAY * 1000))
            log('audio stream not available', xbmc.LOGINFO)
            self.publish(None)
        finally:
            self.updating = False

    @staticmethod
    def current_stream():
        players = jsonrpc('Player.GetActivePlayers', {})
        if not isinstance(players, list):
            return None
        video = [p for p in players if p.get('type') == 'video']
        if not video:
            return None
        result = jsonrpc('Player.GetProperties',
                         {'playerid': video[0]['playerid'],
                          'properties': ['currentaudiostream']})
        stream = result.get('currentaudiostream') or None
        # без имени и языка (UNK) дорожка всё равно есть - нужен хотя бы формат
        return stream if stream and (stream.get('name') or stream.get('language')
                                     or stream.get('codec')) else None

    @staticmethod
    def format_of(stream):
        """«TrueHD Atmos 7.1» - формат и каналы играющей дорожки. Названия те же,
        что в панели информации (playerpanel); Atmos и DTS:X Kodi отдаёт только
        инфолейблом кодека, JSON-RPC даёт общее truehd."""
        codec = xbmc.getInfoLabel('VideoPlayer.AudioCodec').strip() or (stream.get('codec') or '')
        channels = xbmc.getInfoLabel('VideoPlayer.AudioChannels').strip() or str(stream.get('channels') or '')
        return ' '.join(x for x in (playerpanel.AUDIO_NAMES.get(codec, codec.upper()),
                                    playerpanel.CHANNELS.get(channels, '')) if x)

    @staticmethod
    def publish(stream):
        if not stream:
            for prop in AUDIO_PROPS:
                HOME.clearProperty(prop)
            return
        name = (stream.get('name') or '').strip()
        lang = (stream.get('language') or '').strip().upper()
        if lang in ('UND', 'UNK'):   # «не задан» - показывать нечего
            lang = ''
        HOME.setProperty('MediaInfo.AudioStreamName', name)
        HOME.setProperty('MediaInfo.AudioStreamLang', lang)
        # «RUS | MVO ...», без висящей черты, если одной из частей нет
        HOME.setProperty('MediaInfo.AudioStreamTitle', ' | '.join(x for x in (lang, name) if x))
        fmt = AudioTrack.format_of(stream)
        HOME.setProperty('MediaInfo.AudioFormat', fmt)
        # ни имени, ни языка (диск, кривая сборка) - остаётся один формат
        label = ' | '.join(part for part in (lang, name + (' (%s)' % fmt if fmt and name else '')) if part) \
            or fmt
        HOME.setProperty('MediaInfo.AudioStream', label)
        log('audio stream: %s' % label, xbmc.LOGINFO)


DATES_CHECK = 30  # как часто обновляем K9.DateToday/K9.DateYesterday, сек


def sync_dates(state):
    """Сегодня и вчера в формате region dateshort -> свойства Home (раз в DATES_CHECK)."""
    import datetime
    fmt = xbmc.getRegion('dateshort') or '%d.%m.%Y'
    today = datetime.date.today()
    if state.get('day') == today:
        return
    state['day'] = today
    HOME.setProperty('K9.DateToday', today.strftime(fmt))
    HOME.setProperty('K9.DateYesterday', (today - datetime.timedelta(days=1)).strftime(fmt))


class Service(xbmc.Monitor):

    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.cache = self.load_cache()
        self.pending = set()
        self.dirty = 0
        self.current = None
        self.prefetching = False
        self.start_prefetch()

    # --- кэш ---

    def load_cache(self):
        try:
            with open(CACHE_FILE, 'r') as handle:
                cache = json.load(handle)
            if isinstance(cache, dict):
                return cache
        except (IOError, OSError, ValueError):
            pass
        return {}

    def save_cache(self):
        with self.lock:
            if not self.dirty:
                return
            snapshot = dict(self.cache)
            self.dirty = 0
        try:
            if not os.path.isdir(PROFILE):
                os.makedirs(PROFILE)
            with open(CACHE_FILE, 'w') as handle:
                json.dump(snapshot, handle)
        except (IOError, OSError) as exc:
            log('cache save failed: %s' % exc, xbmc.LOGWARNING)

    def remember(self, path, entry):
        with self.lock:
            self.cache[path] = entry
            self.dirty += 1

    # --- предварительный обход библиотеки ---

    def start_prefetch(self):
        if self.prefetching:
            return
        self.prefetching = True
        threading.Thread(target=self.prefetch, daemon=True).start()

    def prefetch(self):
        """Разово посчитать все фильмы, чтобы при листании цифры были сразу."""
        try:
            movies = jsonrpc('VideoLibrary.GetMovies',
                             {'properties': ['file', 'runtime']}).get('movies') or []
            added = 0
            for movie in movies:
                if self.abortRequested():
                    return
                path = movie.get('file')
                if not is_supported(path):
                    continue
                with self.lock:
                    known = path in self.cache
                if known:
                    continue
                entry = probe(path, movie.get('runtime') or 0)
                if entry:
                    self.remember(path, entry)
                    added += 1
            if added:
                self.save_cache()
                log('prefetched %d movies' % added, xbmc.LOGINFO)
        finally:
            self.prefetching = False

    # --- отслеживание фокуса ---

    def run(self):
        keymap_state, keymap_at = {}, 0.0
        dates_state, dates_at = {}, 0.0
        while not self.abortRequested():
            try:
                self.tick()
                now = time.time()
                if now - dates_at >= DATES_CHECK:
                    dates_at = now
                    sync_dates(dates_state)
                if now - keymap_at >= PPI_CHECK:
                    keymap_at = now
                    sync_ppi_keymap(keymap_state)
            except Exception as exc:  # noqa: BLE001 - сервис не должен падать
                log('tick failed: %s' % exc, xbmc.LOGERROR)
            if self.dirty >= SAVE_EVERY:
                self.save_cache()
            if self.waitForAbort(POLL_INTERVAL):
                break
        self.save_cache()
        self.publish(None)

    def tick(self):
        path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
        if path == self.current:
            return
        self.current = path
        if not is_supported(path):
            self.publish(None)
            return
        with self.lock:
            entry = self.cache.get(path)
        if entry:
            self.publish(entry)
            return
        self.publish(None)
        self.resolve_async(path, to_int(xbmc.getInfoLabel('ListItem.Duration(secs)')))

    def resolve_async(self, path, duration):
        """Stat по сети может подвиснуть — уводим его из цикла опроса."""
        with self.lock:
            if path in self.pending:
                return
            self.pending.add(path)
        threading.Thread(target=self.resolve, args=(path, duration), daemon=True).start()

    def resolve(self, path, duration):
        try:
            entry = probe(path, duration)
        finally:
            with self.lock:
                self.pending.discard(path)
        if not entry:
            return
        self.remember(path, entry)
        if self.current == path:
            self.publish(entry)

    def publish(self, entry):
        if not entry:
            for prop in PROPS:
                HOME.clearProperty(prop)
            return
        size, kbps = entry
        HOME.setProperty('MediaInfo.Size', format_size(size))
        HOME.setProperty('MediaInfo.Bitrate', format_bitrate(kbps))
        HOME.setProperty('MediaInfo.SizeRaw', str(size))
        HOME.setProperty('MediaInfo.BitrateRaw', str(kbps))

    def onNotification(self, sender, method, data):
        if method in ('VideoLibrary.OnScanFinished', 'VideoLibrary.OnCleanFinished'):
            self.start_prefetch()


if __name__ == '__main__':
    AUDIO_WATCHER = AudioTrack()  # ссылка нужна, иначе Kodi соберёт объект сборщиком мусора
    SERVICE = Service()
    if playerpanel.available():
        PANEL = playerpanel.PlayerPanel(SERVICE.cache)
        PANEL.start()
        HOME.setProperty(ACTIVE_PROP, '1')
    SERVICE.run()
    HOME.clearProperty(ACTIVE_PROP)
    AudioTrack.publish(None)
    clear_video()
