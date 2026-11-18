# video-tools

Личная мастерская инструментов для видео: расшифровка, монтаж и шаблоны Resolve.
Работаем локально, предпочитаем офлайн. Здесь — инструменты для любого проекта;
материалы роликов хранятся в их папках. Распространение и монетизация — отдельный будущий этап.

## Инструменты и готовность

| Инструмент | Статус | Основание / что осталось |
| --- | --- | --- |
| [Расшифровка](tools/transcribe/README.md) | Готов | Проверен на рабочих материалах; Bash + ffmpeg + whisper.cpp |
| [Edge Aberration](resolve/fusion/templates/effects/edge-aberration/README.md) | Готов | Применён в бесплатном Resolve 21.1 |
| [Film Grain Look](resolve/fusion/templates/effects/film-grain-look/README.md) | На проверке | Подключён; визуальный результат требует подтверждения |
| [Type Drift](resolve/fusion/templates/generators/type-drift/README.md) | На проверке | Проверена структура; нужен просмотр и рендер в Resolve |

«Готов» — проверен в рабочем процессе и документирован; «На проверке» — реализация
есть, указан незакрытый пункт; «Эксперимент» — способ решения ещё выбирается.
Статус относится к проверенной среде, а не ко всем ОС.

## Расшифровка

Команды из корня репозитория, оболочка **Bash**:

```bash
# План: исходники и результаты не меняются
bash tools/transcribe/transcribe -n "/путь/к/проекту/video/src"

# Распознавание: запускает Иван после проверки плана
bash tools/transcribe/transcribe -p "Привет, друзья! На связи Иван Потылицын." "/путь/к/проекту/video/src"

# Справка
bash tools/transcribe/transcribe -h
```

Рядом с видео создаются `audio/`, `txt/`, `srt/`, `json/`.
[Установка, замены и ограничения](tools/transcribe/README.md).

## Resolve — шаблоны Fusion

Подключение на macOS; команды выполняет Иван:

```bash
bash resolve/fusion/templates/effects/edge-aberration/install
bash resolve/fusion/templates/effects/film-grain-look/install
bash resolve/fusion/templates/generators/type-drift/install
```

Повторное подключение безопасно; чужие файлы не заменяются.
Шаблоны устанавливаются в группу `vt` в Effects и Generators.
После подключения перезапусти Resolve.
[Каталог Resolve](resolve/README.md) · [Установка и удаление шаблонов](resolve/fusion/templates/README.md).

## Разработка и навигация

- [План: сейчас, дальше, отложено](ROADMAP.md).
- [Как создаём и доводим инструменты](docs/workflows/development.md).
- [Работа с видеопроектом](docs/workflows/video-project.md).
- [Структура, языки, платформы и окружение](docs/structure.md).
- [Проверки установщиков](tests/README.md): `python3 -m unittest discover -s tests -v`.

Проверенная рабочая среда — macOS. Linux и Windows пока не проверены.
Для Windows рекомендуем [Windows Terminal](https://learn.microsoft.com/en-us/windows/terminal/),
но он не заменяет Bash, Python и зависимости.
Единой команды `vt` и автоматической установки окружения пока нет; это запланировано.
