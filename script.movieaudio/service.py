"""Пересчитывает виджет Movies Atmos/DTS-X, когда меняется медиатека.

Сам пересчёт делает bin/coreelec/kodi-movie-audio.py (установщик кладёт его в
resources/ аддона), сервис только решает когда: после сканирования (его
запускает Radarr после импорта, library-refresh, старт Kodi), очистки и
удаления фильма. Запускается системным python3, как и из bin/coreelec-kodi.sh,
чтобы логика жила в одном файле.

Перезаписанный плейлист виджет сам не перечитывает: его список обновляется
только по событиям медиатеки, а своё OnScanFinished Kodi к этому моменту уже
разослал. Поэтому после правки сервис просит просканировать несуществующий
каталог: Kodi пропускает его за доли секунды, в базу ничего не пишет, но
рассылает OnScanStarted и OnScanFinished, и виджет перечитывается. Наше же
OnScanFinished запускает пересчёт ещё раз - он ничего не меняет, круг на этом
заканчивается.

Заодно сервис держит в свойствах окна Home строки MovieTotals («Всего фильмов -
57, 2.2 ТБ») и SeriesTotals («Сериалов - 7 (53 серий), 432 ГБ»): их
рисует скин под погодой; MovieTotalsShort («75 фильмов · 2.4 ТБ») и
SeriesTotalsShort («7 сериалов · 54 серии · 376 ГБ») - то же короче, для
карточки у часов на K9. Последние значения (и числа виджетов) лежат в
totals.json профиля аддона и выставляются сразу при старте, до подсчёта.
Считается на тех же событиях, размеры
файлов запоминаются, чтобы недоступный на минуту NAS не обнулил объём.

Если рядом лежит source.json (стоковая приставка), список берётся у эталона,
а своих событий о пополнении библиотеки здесь нет: сканирует только эталон.
Тогда сервис спрашивает его раз в POLL секунд.

На Android (Kodi FEL на Kinhank K9) системного python3 нет: виджет Atmos там не
пересчитывается (плейлист приезжает готовым с приставки), сервис держит только
итоги. Разбор - README.md.

И число элементов в каждом виджете меню - свойство окна Home
WidgetTotal.<заголовок виджета>, скин выводит его в скобках после заголовка
(View_Cast_Toplabel). Container(id).NumItems для этого не годится: виджет
грузит не больше widgetLimit (25) элементов. Итог спрашивается у самого
Kodi (Files.GetDirectory с limits - в ответе limits.total) по путям виджетов
из меню skinshortcuts; плагины не считаем - это долго и не библиотека.
"""
import glob
import os
import re
import shutil
import subprocess
import time

import json

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
HERE = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
DATA = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
SCRIPT = os.path.join(HERE, "resources", "kodi-movie-audio.py")
SOURCE = os.path.join(DATA, "source.json")
STATUS = os.path.join(DATA, "last.txt")
# последние итоги и числа виджетов: при старте Kodi показываются сразу, а не
# через START_DELAY + подсчёт (CHANGES.md скина, п. 26)
CACHE = os.path.join(DATA, "totals.json")
ADVANCED = "/storage/.kodi/userdata/advancedsettings.xml"

EVENTS = ("VideoLibrary.OnScanFinished", "VideoLibrary.OnCleanFinished",
          "VideoLibrary.OnRemove")
# Каталог, которого нет: сканирование его пропускает, событие остаётся.
POKE_DIR = "special://temp/movie-audio-refresh/"
# Удаление приходит пачкой OnRemove - пересчитываем, когда пачка кончилась.
SETTLE = 5
# Первый пересчёт после старта: к этому моменту поднят веб-сервер Kodi.
START_DELAY = 60
POLL = 600


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[script.movieaudio] %s" % msg, level)


def clean_on_update():
    """С cleanonupdate любое сканирование, даже пустое, чистит всю базу."""
    try:
        with open(ADVANCED, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return False
    return bool(re.search(r"<cleanonupdate>\s*true", raw, re.I))


def poke():
    if clean_on_update():
        log("cleanonupdate включён - виджет перечитается при следующем событии",
            xbmc.LOGWARNING)
        return
    xbmc.executeJSONRPC(
        '{"jsonrpc":"2.0","id":1,"method":"VideoLibrary.Scan",'
        '"params":{"directory":"%s","showdialogs":false}}' % POKE_DIR)


SIZES = {}  # путь -> размер, только успешно прочитанные


def file_paths(item):
    files = item.get("file", "")
    if files.startswith("stack://"):
        return files[len("stack://"):].split(" , ")
    return [files] if files else []


def file_size(path):
    if path not in SIZES:
        size = xbmcvfs.Stat(path).st_size()
        if size > 0:
            SIZES[path] = size
    return SIZES.get(path, 0)


def fmt_size(total):
    if total >= 1024 ** 4:
        return "%.1f ТБ" % (total / 1024 ** 4)
    return "%d ГБ" % round(total / 1024 ** 3)


def library(method, key, extra=()):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method,
         "params": {"properties": list(extra)}})))
    return reply.get("result", {}).get(key, [])


def present(items):
    """Записи, чьи файлы есть на диске.

    Проверка нужна не только ради счёта: для файла, которого нет, Kodi всё
    равно отдаёт размер (чужой, из кэша NFS), и объём получается выдуманным.
    Записи без файла остаются в библиотеке после удаления в обход Kodi."""
    return [i for i in items
            if file_paths(i) and all(xbmcvfs.exists(f) for f in file_paths(i))]


def files_size(items):
    """Объём файлов; файл, за которым числится несколько серий, считается раз."""
    paths = {f for item in items for f in file_paths(item)}
    return sum(file_size(f) for f in paths)


SHORTCUTS = xbmcvfs.translatePath("special://profile/addon_data/script.skinshortcuts/")
SKIN_LABEL = re.compile(r"^\$(?:SKIN|LOCALIZE)\[(\d+)")


def widget_label(raw):
    """Заголовок, как его покажет скин: $SKIN[31225|...] и $LOCALIZE[31225]
    Kodi раскрывает в текст раньше $INFO, поэтому и ключ - текст."""
    m = SKIN_LABEL.match(raw)
    return xbmc.getLocalizedString(int(m.group(1))) if m else raw


def update_widget_totals():
    """Window(Home).Property(WidgetTotal.<заголовок>) по виджетам меню."""
    seen = {}
    for data in glob.glob(os.path.join(SHORTCUTS, "*.DATA.xml")):
        try:
            with open(data, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError:
            continue
        for label, action in re.findall(r"<label>([^<]*)</label>.*?<action>([^<]*)</action>",
                                        raw, re.S):
            if action.startswith(("videodb://", "special://")) or action.endswith(".xsp"):
                seen[widget_label(label.strip())] = action.strip()
    home = xbmcgui.Window(10000)
    totals = {}
    for label, path in seen.items():
        reply = json.loads(xbmc.executeJSONRPC(json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
             "params": {"directory": path, "media": "video",
                        "limits": {"start": 0, "end": 1}}})))
        total = (reply.get("result") or {}).get("limits", {}).get("total")
        if total is None:
            home.clearProperty("WidgetTotal." + label)
        else:
            home.setProperty("WidgetTotal." + label, str(total))
            totals["WidgetTotal." + label] = str(total)
    remember(totals, drop_prefix="WidgetTotal.")
    log("виджеты: %s" % ", ".join("%s %s" % (k, xbmcgui.Window(10000).getProperty("WidgetTotal." + k))
                                   for k in sorted(seen)))


# Смарт-плейлисты виджетов «Фильмы 4K» и «Фильмы 1080p» (меню скина по умолчанию,
# CHANGES.md скина, п. 37). Тот же текст пишет tools/kodi-movie-quality.py;
# здесь - только если файла нет, свои правки пользователя не трогаем. Имя «Movies 4K»
# не переводить: на него по имени ссылается правило плейлиста 1080p.
PLAYLISTS = {'Movies4K.xsp': '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<smartplaylist type="movies">\n    <name>Movies 4K</name>\n    <match>all</match>\n    <rule field="videoresolution" operator="greaterthan">\n        <value>1080</value>\n    </rule>\n    <order direction="descending">dateadded</order>\n</smartplaylist>\n', 'Movies1080p.xsp': '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<smartplaylist type="movies">\n    <name>Movies 1080p</name>\n    <match>all</match>\n    <rule field="videoresolution" operator="is">\n        <value>1080</value>\n    </rule>\n    <rule field="playlist" operator="isnot">\n        <value>Movies 4K</value>\n    </rule>\n    <order direction="descending">dateadded</order>\n</smartplaylist>\n'}


def ensure_playlists():
    folder = xbmcvfs.translatePath("special://profile/playlists/video/")
    for name, text in PLAYLISTS.items():
        path = os.path.join(folder, name)
        if os.path.exists(path):
            continue
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            log("плейлист виджета создан: %s" % name)
        except OSError as err:
            log("плейлист %s не создан: %s" % (name, err), xbmc.LOGWARNING)


def remember(props, drop_prefix=None):
    """Свойства окна Home - в CACHE. drop_prefix: группа, которую props
    заменяет целиком (WidgetTotal. - виджеты могли исчезнуть из меню)."""
    try:
        with open(CACHE, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        cache = {}
    if drop_prefix:
        cache = {k: v for k, v in cache.items() if not k.startswith(drop_prefix)}
    cache.update(props)
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
    except OSError as err:
        log("кэш итогов не записан: %s" % err, xbmc.LOGWARNING)


def publish_cached():
    """Итоги с прошлого подсчёта - сразу при старте сервиса."""
    try:
        with open(CACHE, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        return
    home = xbmcgui.Window(10000)
    for name, text in cache.items():
        if not home.getProperty(name):
            home.setProperty(name, text)
    log("итоги из кэша: %d свойств" % len(cache))


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def update_totals():
    """Итоги по фильмам и сериалам -> Window(Home).MovieTotals / SeriesTotals."""
    try:
        all_movies = library("VideoLibrary.GetMovies", "movies", ["file"])
        all_episodes = library("VideoLibrary.GetEpisodes", "episodes",
                               ["file", "tvshowid"])
        movies, episodes = present(all_movies), present(all_episodes)
        if (all_movies or all_episodes) and not (movies or episodes):
            # Ни одного файла не видно - скорее недоступен NAS, чем пусто.
            log("файлов не видно, итоги не обновляю", xbmc.LOGWARNING)
            return
        # В Sonarr заведены и сериалы без единого файла - их не считаем.
        shows = {e.get("tvshowid") for e in episodes}
        texts = {
            "MovieTotals": "Всего фильмов - %d, %s" % (
                len(movies), fmt_size(files_size(movies))),
            "SeriesTotals": "Сериалов - %d (%d серий), %s" % (
                len(shows), len(episodes), fmt_size(files_size(episodes))),
            # короткие - для карточки у часов на K9 (CHANGES.md скина, п. 21)
            "MovieTotalsShort": "%d %s · %s" % (
                len(movies), plural(len(movies), "фильм", "фильма", "фильмов"),
                fmt_size(files_size(movies))),
            "SeriesTotalsShort": "%d %s · %d %s · %s" % (
                len(shows), plural(len(shows), "сериал", "сериала", "сериалов"),
                len(episodes), plural(len(episodes), "серия", "серии", "серий"),
                fmt_size(files_size(episodes))),
        }
    except Exception as err:
        log("итоги по библиотеке не посчитаны: %s" % err, xbmc.LOGWARNING)
        return
    home = xbmcgui.Window(10000)
    for name, text in texts.items():
        home.setProperty(name, text)
        log(text)
    remember(texts)


def recount(reason):
    if not shutil.which("python3"):
        update_totals()
        update_widget_totals()
        return
    cmd = ["python3", SCRIPT, "--apply", "--playlist-only"]
    if os.path.isfile(SOURCE):
        cmd += ["--source", SOURCE]
    try:
        res = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                             errors="replace", timeout=120)
        code, out = res.returncode, (res.stdout + res.stderr).strip()
    except Exception as err:
        code, out = -1, str(err)

    if code == 10:
        result = "плейлист обновлён"
        poke()
    elif code == 0:
        result = "без изменений"
    else:
        result = "ошибка, код %s" % code
    log("%s: %s\n%s" % (reason, result, out),
        xbmc.LOGINFO if code in (0, 10) else xbmc.LOGWARNING)

    update_totals()
    update_widget_totals()

    os.makedirs(DATA, exist_ok=True)
    with open(STATUS, "w", encoding="utf-8") as fh:
        fh.write("%s  %s  (%s)\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                         result, reason, out))


class Watcher(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.pending = None  # когда пришло последнее событие

    def onNotification(self, sender, method, data):
        if method in EVENTS:
            self.pending = time.time()
            self.reason = method.split(".")[-1]


def main():
    monitor = Watcher()
    ensure_playlists()
    publish_cached()
    if monitor.waitForAbort(START_DELAY):
        return
    recount("старт")
    last = time.time()

    while not monitor.waitForAbort(2):
        now = time.time()
        if xbmc.getCondVisibility("Library.IsScanningVideo"):
            continue
        if monitor.pending and now - monitor.pending >= SETTLE:
            monitor.pending = None
            recount(monitor.reason)
            last = now
        elif os.path.isfile(SOURCE) and now - last >= POLL:
            recount("опрос эталона")
            last = now


if __name__ == "__main__":
    main()
