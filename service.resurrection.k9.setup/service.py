# -*- coding: utf-8 -*-
"""Установка «под ключ»: Arctic: Zephyr 2 - Resurrection K9.

Один zip: после «Установить из zip» Kodi сам запускает этот сервис. Он кладёт рядом
репозиторий repository.resurrection.k9 (лежит внутри, resources/repository), включает его,
обновляет список репозиториев и просит Kodi поставить скин оттуда - Kodi сам подтягивает
все зависимости (наши сервисы, script.skinhelper из репозитория DenDyGH, остальное из
официального) и предлагает переключиться на скин. Обновления потом приходят из репозитория.
Сработав, сервис выключает себя.
"""
import json
import os
import shutil

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ME = ADDON.getAddonInfo("id")
HERE = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
REPO = "repository.resurrection.k9"
SKIN = "skin.arctic.zephyr.2.resurrection.k9"
RU = xbmc.getLanguage(xbmc.ISO_639_1) == "ru"


def log(msg):
    xbmc.log("[%s] %s" % (ME, msg), xbmc.LOGINFO)


def rpc(method, **params):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return reply.get("result"), reply.get("error")


def installed(addon_id):
    result, _ = rpc("Addons.GetAddonDetails", addonid=addon_id, properties=["enabled"])
    return bool(result) and result["addon"].get("enabled", False)


def say(ru, en):
    xbmcgui.Dialog().notification("Resurrection K9", ru if RU else en,
                                  xbmcgui.NOTIFICATION_INFO, 5000)


def main():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(3):
        return
    if installed(SKIN):
        log("скин уже стоит")
    else:
        if not installed(REPO):
            src = os.path.join(HERE, "resources", "repository")
            dst = os.path.join(xbmcvfs.translatePath("special://home/addons"), REPO)
            if not os.path.isdir(dst):
                shutil.copytree(src, dst)
            xbmc.executebuiltin("UpdateLocalAddons", True)
            monitor.waitForAbort(3)
            rpc("Addons.SetAddonEnabled", addonid=REPO, enabled=True)
            log("репозиторий включён")
        say("Загрузка списка дополнений...", "Fetching add-on list...")
        xbmc.executebuiltin("UpdateAddonRepos", True)
        monitor.waitForAbort(15)
        log("ставлю скин из репозитория")
        # Kodi спросит «Установить?», подтянет зависимости и предложит сменить скин.
        # Без ожидания: если ждать здесь, установка зависимости-сервиса (например,
        # обновление уже работающего service.mediainfo.filesize) повисает - Kodi ждёт
        # остановки сервиса, а поток занят этим вызовом (телевизор, 2026-11-10)
        xbmc.executebuiltin("InstallAddon(%s)" % SKIN)
    for _ in range(900):
        if installed(SKIN) or monitor.waitForAbort(1):
            break
    if installed(SKIN):
        # InstallAddon из скрипта, в отличие от меню дополнений, не предлагает
        # переключиться на скин - переключаем сами; Kodi спросит «Сохранить?» с
        # отсчётом, без ответа вернёт прежний скин (телевизор, 2026-11-10)
        current, _ = rpc("Settings.GetSettingValue", setting="lookandfeel.skin")
        if (current or {}).get("value") != SKIN:
            say("Скин установлен. Подтвердите переключение - «Да».",
                "Skin installed. Confirm the switch - \"Yes\".")
            monitor.waitForAbort(3)
            rpc("Settings.SetSettingValue", setting="lookandfeel.skin", value=SKIN)
        log("скин установлен, установщик выключается")
        rpc("Addons.SetAddonEnabled", addonid=ME, enabled=False)
    else:
        say("Не удалось. Поставьте скин из репозитория Resurrection K9 вручную.",
            "Failed. Install the skin from Resurrection K9 repository manually.")


if __name__ == "__main__":
    main()
