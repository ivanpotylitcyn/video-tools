# Edge Aberration

Fusion Effect: призраки и цветовые каёмки у краёв, с чистой центральной областью.
**Статус: готов.** Применён в бесплатном Resolve 21.1 на macOS.
Windows/Linux не проверены. Внешние плагины и Studio API не нужны.

## Подключение

Из корня репозитория, Bash:

```bash
bash resolve/fusion/templates/effects/edge-aberration/install
```

[Общие правила установки и удаления](../../README.md).

## Минимальный пример

Перезапусти Resolve → Effects Library → Fusion Effects → Edge Aberration.
Добавь на Adjustment Clip над видео, начни с нескольких секунд.
Настрой Center на главный объект, Clean Zone и Softness — на область без искажений.
Ghosting управляет общими призраками, Color Fringe — красно-синими каёмками.

## Устройство и ограничения

[Шаблон](Edge%20Aberration.setting): инвертированная EllipseMask и DirectionalBlur
в режиме Zoom (Type = 3). Общее размытие даёт призраки, R наружу и B внутрь — каёмки.
Структура ориентирована на штатный шаблон Chromatic Aberration установленного Resolve.
Обновление файла не меняет уже добавленные на таймлайн экземпляры.
При совместном использовании зерно применять после аберраций, чтобы его не размывать.
