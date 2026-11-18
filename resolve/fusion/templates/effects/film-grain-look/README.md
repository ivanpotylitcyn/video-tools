# Film Grain Look

Fusion Effect с зерном на родном узле FilmGrain.
**Статус: на проверке.** Шаблон создан и подключён на macOS; визуальный результат
и рендер нужно подтвердить Ивану в рабочем процессе.
Windows/Linux не проверены. Это не ResolveFX Film Grain.

## Подключение

Из корня репозитория, Bash:

```bash
bash resolve/fusion/templates/effects/film-grain-look/install
```

[Общие правила установки и удаления](../../README.md).

## Минимальный пример и проверка

Перезапусти Resolve → Effects Library → Fusion Effects → Film Grain Look.
Добавь на короткий Adjustment Clip над видео. Если там же аберрации,
зерно должно обрабатываться после них.

- Strength управляет силой, Size — размером, Monochrome — монохромностью.
- Проверить, что Strength = 0 убирает зерно и настройки видны в Inspector.
- Просмотреть и отрендерить короткий фрагмент; сравнить с выключенным эффектом.
- После подтверждения обновить статус в этом README, каталоге и ROADMAP.

## Реализация

[Шаблон](Film%20Grain%20Look.setting) использует MasterStrength, MasterXSize и
Monochrome; имена параметров взяты из штатных шаблонов Resolve.
Настройки по умолчанию: Strength 0,04; Size 1,5; Monochrome включён.
