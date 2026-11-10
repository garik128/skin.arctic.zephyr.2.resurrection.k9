# Arctic: Zephyr 2 - Resurrection K9

Форк скина Kodi [Arctic: Zephyr 2 - Resurrection](https://github.com/DenDyGH/skin.arctic.zephyr.2.resurrection.k9)
с полным русским переводом и переработанной информацией о воспроизведении. Делался под
ТВ-бокс Kinhank K9 с Kodi FEL (Dolby Vision FEL), но работает на любом Kodi 21-22: на
Android-боксах, Windows, Linux. Чего на конкретном железе нет, то просто не показывается.

*English summary below.*

## Что нового относительно исходного скина

- **Русский перевод** всех строк скина, меню поиска и питания.
- **Панель информации о воспроизведении карточками**: видео (класс разрешения, HDR / Dolby
  Vision, бейдж FEL/MEL), звук (формат, дорожка, битстрим), выход HDMI, слои Dolby Vision
  (RPU / EL / BL) или метаданные HDR10, поток с графиком битрейта, кольца кэша, очередей,
  памяти и температуры.
- **Сведения на старте воспроизведения**: сверху логотипы видео и звука, снизу название
  дорожки и плашки видео (формат, FEL/MEL, кадр, частота, кодек). Не появляются при
  перемотке.
- **Строка под списком плашками**: разрешение и HDR картинками, звук, размер файла, битрейт.
- **Главный экран**: описание до 8 строк, английское имя папки рядом с названием, карточка
  у часов с итогами по медиатеке («75 фильмов · 2.4 ТБ»), число элементов в заголовках
  виджетов, нейтральный фон по умолчанию.
- **Раздел «Дополнительно» в настройках скина** - всё перечисленное включается и
  выключается, там же кнопка пульта для панели информации (FF, Info, Menu, цветные, Guide).

## Состав

| Каталог | Что это |
|---|---|
| `skin.arctic.zephyr.2.resurrection.k9` | сам скин |
| `service.mediainfo.filesize` | сервис: размер и битрейт файла в списках, данные панели информации и сведений на старте, кнопка пульта для панели |
| `script.movieaudio` | сервис: итоги по медиатеке у часов, числа в заголовках виджетов |
| `tools/` | генераторы разметки панели (`skin-android-ppi.py`) и фона (`skin-default-bg.py`); нужны только тем, кто правит скин |
| `repository.resurrection.k9` | Kodi-репозиторий (сам репозиторий живёт в ветке `gh-pages`, GitHub Pages) |

## Установка

Kodi 21 (Omega) или 22.

1. Скачать `repository.resurrection.k9-*.zip` со страницы
   **<https://garik128.github.io/skin.arctic.zephyr.2.resurrection.k9/>** и поставить:
   «Дополнения → Установить из zip». Если Kodi спросит - разрешить «Неизвестные источники».
   Репозиторий смотрит и в репозиторий DenDyGH: оттуда приходит нужный скину
   `script.skinhelper` (его нет в официальном репозитории Kodi), а в списке скинов рядом
   будет виден и оригинальный Resurrection.
2. «Дополнения → Установить из репозитория → Resurrection K9 repository → Внешний вид →
   Скин → Arctic: Zephyr 2 - Resurrection K9 → Установить». Kodi сам поставит наши сервисы и
   зависимости из официального репозитория (skinshortcuts, skinvariables, TMDb Helper и др.).
3. Согласиться сменить скин. Язык интерфейса Kodi - русский, и скин тоже будет по-русски.
4. «Настройки → Интерфейс → Обложка → Настроить обложку → Дополнительно» - что включить и
   какой кнопкой пульта открывать панель информации (по умолчанию - кнопкой в OSD рядом с
   кнопкой дорожек).

Обновления приходят из того же репозитория сами. Без репозитория можно поставить zip из
раздела Releases по одному: сначала `service.mediainfo.filesize` и `script.movieaudio`,
потом скин.

## Советы

- **Раскладка главного экрана - «Modern (dark) | Multiple widgets»** («Настройки скина →
  Главное меню → Раскладка главной»): под неё сделаны карточка у часов и поднятое описание.
  В других раскладках итоги у часов показываются без карточки.
- **Переходите с оригинального Resurrection?** Меню skinshortcuts общее для всех скинов, и
  часть подписей в нём ссылается на строки старого скина - на месте заголовка виджета
  будет «None». Выберите такой виджет заново («Настроить главное меню») или сбросьте меню
  («Resurrection → Сбросить настройки скина»).
- Фон, когда у фильма нет фанарта, - «Настройки скина → Фон».

## Что зависит от железа

| Что | Где работает |
|---|---|
| Всё на главном экране, строка под списком, перевод, настройки | везде |
| Панель информации: видео, звук, поток, кэш, очереди, память | везде, кроме CoreELEC (там у скина своя панель на полях сборки) |
| Карточка «Выход HDMI», сверка частоты, температура SoC/GPU | Android-боксы на Amlogic (читается `/sys`); на другом железе карточка не показывается, «Видео» и «Звук» встают на её место |
| FEL / MEL, модуль сборки FEL | Kodi FEL на Amlogic с модулем dvfel; без него слой EL - «не используется» |
| Мастеринг и MaxCLL/MaxFALL | только если рядом с медиатекой лежит заранее посчитанный `.hdrinfo.json` (инструмент в этот выпуск не входит) - иначе строки скрыты |
| Виджет «Фильмы Atmos/DTS:X» | считается внешним скриптом с python3; на Android без него не обновляется |

## Авторы и лицензия

Скин - **CC BY-NC-SA 4.0** ([LICENSE.md](LICENSE.md)): свободно для некоммерческого
использования, с указанием авторов, изменения - на тех же условиях. Продавать скин и
сборки с ним нельзя.

- Arctic Zephyr 2 - **jurialmunkey**
- порт на Kodi 19 Matrix - **pkscout**
- Arctic Zephyr 2 Resurrection - **heppen**, мод **DenDyGH**
  ([исходник](https://github.com/DenDyGH/skin.arctic.zephyr.2.resurrection.k9)); основа этого
  выпуска - сборка 1.0.36-CPM
- выпуск K9: перевод, панель информации, плашки, раздел «Дополнительно»

Шрифты: Roboto (Apache 2.0), Inter и Font Awesome (OFL), шрифты «текстов песен» - OFL,
Apache 2.0 и бесплатные с разрешением распространения; три шрифта без такого разрешения
из исходного скина убраны. Логотипы форматов (Dolby, DTS, IMAX и др.) - товарные знаки
их владельцев.

`service.mediainfo.filesize` и `script.movieaudio` - MIT.

---

## English summary

A fork of Arctic: Zephyr 2 - Resurrection (DenDyGH) for Kodi 21-22 with a complete Russian
translation, a card-style playback info panel (video, audio, HDMI output, Dolby Vision
layers, bitrate chart, buffers and temperatures), start-of-playback cards, badges below
lists and an "Extras" section in skin settings to toggle all of it, including a remote
button for the info panel. Built for the Kinhank K9 with Kodi FEL, works on any Kodi:
hardware-specific parts (HDMI output, temperatures, FEL) are hidden where unavailable.

Install: get `repository.resurrection.k9-*.zip` from
https://garik128.github.io/skin.arctic.zephyr.2.resurrection.k9/ , install it from zip, then
install the skin from that repository - Kodi pulls in all dependencies.
License: CC BY-NC-SA 4.0 (skin), MIT (services). Credits: jurialmunkey, pkscout, heppen,
DenDyGH.
