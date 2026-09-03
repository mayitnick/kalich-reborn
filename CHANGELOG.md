# Changelog

Все заметные изменения в проекте документируются в этом файле.

## [Unreleased] - 2026-09-02

### Added
- Динамический парсинг групп с сайта Глорис (`глорис-окту-1.рф`, `глорис-окту-2.рф`, `глорис-окту-3.рф`) с авто-подгрузкой новых групп на лету (`find_group_info`, `get_department_groups`).
- Эндпоинт проверки здоровья `/api/health` для мониторинга статуса базы данных и количества спарсенных групп.
- Режим SQLite WAL (`PRAGMA journal_mode=WAL;`) и `PRAGMA busy_timeout = 5000;` в `kalich.py` и `api_server.py` для устранения блокировок при многопоточных запросах.
- Параметр `?refresh=true` для эндпоинта `/api/groups`.
- Модульная система команд и внедрения зависимостей (Dependency Injection):
  - Пакет `src/core/` (`ServiceContainer`, `AppContext`, `BaseCommand`, `command`, `CommandScanner`).
  - Полное автодополнение типов (IDE type hints) для всех методов сервисов (`ctx.db`, `ctx.parser`, `ctx.analytics`, `ctx.notifier`, `ctx.config`, `ctx.bot`).
  - Автоматическое сканирование каталога `src/bot/commands/` и валидация объявленных зависимостей (`requires`).
  - Поддержка слэш-команд, текстовых алиасов, regex-шаблонов и медиа-хэндлеров (фото, документы, аудио).
  - Подробное руководство по созданию команд и расширению контейнера: `docs/COMMAND_SYSTEM.md`.
- Unit-тесты для динамического парсера, эндпоинта `/api/health` и системы команд с DI (`tests/test_command_system.py`).

### Changed
- Архитектурный рефакторинг монолита `kalich.py` в модульную структуру `src/`:
  - `src/config.py`: централизованная конфигурация окружения, пути, звонки и фильтры.
  - `src/database.py`: слой доступа к данным SQLite, транзакции, менеджеры мониторов и кастомных имен.
  - `src/services/parser.py`: парсинг страниц Глориса, динамическое кэширование и поиск групп.
  - `src/services/analytics.py`: построение графиков и аналитика учебной нагрузки (Matplotlib).
  - `src/services/notifier.py`: фоновые воркеры, утренние рассылки и определение совмещений кабинетов.
  - `src/bot/instance.py` и `src/bot/keyboards.py`: инициализация бота и фабрика клавиатур.
  - `src/bot/handlers/teacher.py`: команды и логика для преподавателей.
  - Монолит `kalich.py` сокращён более чем на 1700 строк с сохранением 100% обратной совместимости.
- Синхронизирован порт бэкенда (`8999:8999`) в `docker-compose.yml` и `api_server.py`.
- Добавлен том `./data:/app/data` в `docker-compose.yml` для персистентности базы данных SQLite.
- Обновлен `ROADMAP.md`: отмечены выполненные задачи 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.2, 5.3; Фаза 4 (PWA) законсервирована.

### Removed
- Удалены команды генерации стикеров: `/s`, `/s1`, `/s2`, `/s3`, `/s_fire`, `/s_blood`, `/s_glitch`, `/setsticker`, `/clear_stickers` (`/cs`), `/clear`.
- Удалены голосовые команды и синтез речи: `/gs`, `/langs`, `/r_voice`.
- Удалены тяжелые библиотеки из `requirements.txt`: `gtts`, `pydub`, `Pillow`, `audioop-lts`.

### Archived
- PWA-фронтенд (`pwa/`, `Dockerfile.frontend`) законсервирован и перемещен в каталог `archive/pwa/` и `archive/pwa.tar.gz`.
- Обработчики статики в `api_server.py` адаптированы под работу с архивом и безопасный fallback.
- Сервис `frontend` в `docker-compose.yml` временно отключен.
