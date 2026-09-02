# Исходный код ядра (src/) 📦

Директория `src/` содержит весь модульный исходный код платформы **Kalich Reborn**.

---

## 📂 Обзор пакетов

| Каталог / Файл | Назначение |
|---|---|
| [`core/`](core/) | Контейнер зависимостей (`ServiceContainer`), контекст (`AppContext`), базовые команды (`BaseCommand`) и сканер (`CommandScanner`). |
| [`services/`](services/) | Доменные сервисы: парсер страниц Глориса (`parser.py`), аналитика Matplotlib (`analytics.py`), фоновые воркеры и нотификации (`notifier.py`). |
| [`bot/`](bot/) | Компоненты Telegram-бота: фабрика клавиатур (`keyboards.py`), инстанс бота (`instance.py`), директория команд ([`commands/`](bot/commands/)). |
| [`database.py`](database.py) | Слой работы с базой данных SQLite с включенным режимом WAL и `busy_timeout = 5000`. |
| [`config.py`](config.py) | Единая точка конфигурации, пути к файлам и расписание звонков. |

---

## 📖 Документация разработчика

- [Руководство по архитектуре](../docs/ARCHITECTURE.md)
- [Руководство по созданию команд и DI](../docs/COMMAND_SYSTEM.md)
