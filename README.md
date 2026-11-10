# Arctic: Zephyr 2 - Resurrection K9

Форк скина Kodi [Arctic: Zephyr 2 - Resurrection](https://github.com/DenDyGH/skin.arctic.zephyr.2.resurrection.k9)
с полным русским переводом и переработанной информацией о воспроизведении. Делался под
ТВ-бокс Kinhank K9 с Kodi FEL (Dolby Vision FEL), но работает на любом Kodi: на
Android-боксах, Windows, Linux. Чего на конкретном железе нет, то просто не показывается.

**Основной выпуск - для Kodi 22 (Piers)**: на основе Resurrection 1.1.12 DenDyGH, меню на
Skin Shortcuts 3. Для **Kodi 21 (Omega)** остаётся прежний выпуск 1.0.36.k9.x (основа
1.0.36-CPM, Skin Shortcuts 2) - он больше не развивается, но и не убран: наш репозиторий
сам отдаёт каждому Kodi его вариант. Исходники варианта для Kodi 21 - ветка `kodi21`.

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
- **Виджеты по умолчанию**: у «Фильмов» - начатые, новые, 4K и 1080p, у «Сериалов» -
  следующие серии, новые серии и новые сериалы; тёмная тема с красным акцентом и
  Netflix-раскладка главной на свежих настройках.
- **Строка под списком плашками**: разрешение и HDR картинками, звук, размер файла, битрейт.
- **Главный экран**: описание до 8 строк, английское имя папки рядом с названием, карточка
  у часов с итогами по медиатеке («75 фильмов · 2.4 ТБ»), число элементов в заголовках
  виджетов, нейтральный фон по умолчанию.
- **Раздел «Дополнительно» в настройках скина** - всё перечисленное включается и
  выключается, там же положение логотипов на старте и кнопка пульта для панели информации
  (FF, Info, Menu, цветные, Guide).

## Состав

| Каталог | Что это |
|---|---|
| `skin.arctic.zephyr.2.resurrection.k9` | сам скин |
| `service.mediainfo.filesize` | сервис: размер и битрейт файла в списках, данные панели информации и сведений на старте, кнопка пульта для панели |
| `script.movieaudio` | сервис: итоги по медиатеке у часов, числа в заголовках виджетов |
| `tools/` | генераторы разметки панели (`skin-android-ppi.py`) и фона (`skin-default-bg.py`); нужны только тем, кто правит скин |
| `repository.resurrection.k9` | Kodi-репозиторий (сам репозиторий живёт в ветке `gh-pages`, GitHub Pages) |
| `service.resurrection.k9.setup` | установка одним zip: подключает репозиторий и ставит скин из него |

## Установка

Kodi 22 (Piers) - основной выпуск, Kodi 21 (Omega) - легаси. Все файлы - на странице
**<https://garik128.github.io/skin.arctic.zephyr.2.resurrection.k9/>**.

**Одним zip (проще всего).** Скачать `service.resurrection.k9.setup-*.zip`, «Дополнения →
Установить из zip» (если Kodi спросит - разрешить «Неизвестные источники»). Через несколько
секунд Kodi сам спросит, ставить ли скин, подтянет все зависимости и предложит на него
переключиться - оба раза ответить «Да» (на «Оставить эту обложку?» Kodi ждёт 10 секунд и без
ответа возвращает прежний скин). Установщик подключает наш репозиторий, так что
обновления приходят сами; сработав, он выключается.

**Через репозиторий.** Поставить из zip `repository.resurrection.k9-*.zip`, затем
«Установить из репозитория → Resurrection K9 repository → Внешний вид → Скин →
Arctic: Zephyr 2 - Resurrection K9». Репозиторий смотрит и в репозиторий DenDyGH: оттуда
приходит нужный скину `script.skinhelper` (его нет в официальном репозитории Kodi), а в
списке скинов рядом виден и оригинальный Resurrection. Скин для Kodi 22 требует TMDb Helper
5.4.16 - версию из официального репозитория Kodi 22 (оригинал 1.1.12 требует 5.5.11, а она
есть только у DenDyGH, и Kodi с настройками по умолчанию её не берёт).

После установки: «Настройки → Интерфейс → Обложка → Настроить обложку → Дополнительно» -
что включить и какой кнопкой пульта открывать панель информации (по умолчанию - кнопкой в
OSD рядом с кнопкой дорожек).

## Советы

- **Раскладка главного экрана - «Современный | Несколько виджетов»** («Настройки скина →
  Главное меню → Раскладка главной», стоит по умолчанию): под неё сделаны карточка у часов и
  поднятое описание. В других раскладках итоги у часов показываются без карточки.
- **Переходите с оригинального Resurrection (Kodi 21)?** Меню skinshortcuts общее для всех
  скинов, и часть подписей в нём ссылается на строки старого скина - на месте заголовка
  виджета будет «None». Выберите такой виджет заново («Настроить главное меню») или сбросьте
  меню («Resurrection → Сбросить настройки скина»). В Kodi 22 меню Skin Shortcuts 3 хранится
  для каждого скина отдельно, этой беды нет.
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
  ([исходник](https://github.com/DenDyGH/skin.arctic.zephyr.2.resurrection.k9)); основа выпуска
  для Kodi 22 - 1.1.12, для Kodi 21 - сборка 1.0.36-CPM
- выпуск K9: перевод, панель информации, плашки, раздел «Дополнительно»

Шрифты: Roboto (Apache 2.0), Font Awesome и Inter (вариант для Kodi 21) - OFL, Amazon Ember
(набор шрифтов «Amazon Ember» - как в исходном скине 1.1.12), шрифты «текстов песен» - OFL,
Apache 2.0 и бесплатные с разрешением распространения; три шрифта без такого разрешения
из исходного скина убраны. Логотипы форматов (Dolby, DTS, IMAX и др.) - товарные знаки
их владельцев.

`service.mediainfo.filesize` и `script.movieaudio` - MIT.

---

## English summary

A fork of Arctic: Zephyr 2 - Resurrection (DenDyGH) with a complete Russian
translation, a card-style playback info panel (video, audio, HDMI output, Dolby Vision
layers, bitrate chart, buffers and temperatures), start-of-playback cards, badges below
lists and an "Extras" section in skin settings to toggle all of it, including a remote
button for the info panel. Built for the Kinhank K9 with Kodi FEL, works on any Kodi:
hardware-specific parts (HDMI output, temperatures, FEL) are hidden where unavailable.
The main release is for Kodi 22 (based on Resurrection 1.1.12, Skin Shortcuts 3); Kodi 21
gets the frozen legacy release 1.0.36.k9.x from the same repository (sources: branch `kodi21`).

Install: from https://garik128.github.io/skin.arctic.zephyr.2.resurrection.k9/ get
`service.resurrection.k9.setup-*.zip` and install it from zip - it adds the repository and
installs the skin with all dependencies (answer "Yes" twice). Or install
`repository.resurrection.k9-*.zip` and the skin from that repository.
License: CC BY-NC-SA 4.0 (skin), MIT (services). Credits: jurialmunkey, pkscout, heppen,
DenDyGH.
