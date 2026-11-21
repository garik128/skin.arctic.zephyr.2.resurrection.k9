# -*- coding: utf-8 -*-
"""Кнопка «Качество» в OSD: выбор варианта видео у играющего потока.

Запускается из скина: RunScript(special://home/addons/service.mediainfo.filesize/quality.py).
Адаптивный поток (YouTube через inputstream.adaptive) отдаёт плееру все
качества сразу, поэтому переключение идёт на лету, без перезапуска ролика:
Player.SetVideoStream. Варианты с «Автоматически» - адаптивный выбор, прочие -
фиксированное качество.
"""
import json
import re

import xbmc
import xbmcgui


RU = xbmc.getLanguage(xbmc.ISO_639_1) == 'ru'
TITLE = 'Качество видео' if RU else 'Video quality'
ONE = 'У этого видео один вариант' if RU else 'This video has a single quality'


def rpc(method, params):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get('result') or {}
    except Exception:  # noqa: BLE001
        return {}


def label(stream):
    name = re.sub(r'\[/?B\]', '', stream.get('name') or '').strip()
    if not name:
        height = stream.get('height') or 0
        name = '%dp' % height if height else 'Video %d' % stream.get('index', 0)
    codec = (stream.get('codec') or '').upper()
    return '%s   %s' % (name, codec) if codec else name


def main():
    players = rpc('Player.GetActivePlayers', {})
    video = [p for p in players if p.get('type') == 'video'] if isinstance(players, list) else []
    if not video:
        return
    playerid = video[0]['playerid']
    props = rpc('Player.GetProperties', {'playerid': playerid,
                                         'properties': ['videostreams', 'currentvideostream']})
    streams = props.get('videostreams') or []
    if len(streams) < 2:
        xbmcgui.Dialog().notification(TITLE, ONE, time=3000)
        return
    current = (props.get('currentvideostream') or {}).get('index')
    pos = next((i for i, s in enumerate(streams) if s.get('index') == current), 0)
    choice = xbmcgui.Dialog().select(TITLE, [label(s) for s in streams], preselect=pos)
    if choice < 0 or choice == pos:
        return
    rpc('Player.SetVideoStream', {'playerid': playerid, 'stream': streams[choice]['index']})


if __name__ == '__main__':
    main()
