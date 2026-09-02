# Changelog

Все заметные изменения в проекте документируются в этом файле.

## [Unreleased] - 2026-09-02

### Added
- Динамический парсинг групп с сайта Глорис (`глорис-окту-1.рф`, `глорис-окту-2.рф`, `глорис-окту-3.рф`) с авто-подгрузкой новых групп на лету (`find_group_info`, `get_department_groups`).
- Эндпоинт проверки здоровья `/api/health` для мониторинга статуса базы данных и количества спарсенных групп.
- Режим SQLite WAL (`PRAGMA journal_mode=WAL;`) и `PRAGMA busy_timeout = 5000;` в `kalich.py` и `api_server.py` для устранения блокировок при многопоточных запросах.
- Параметр `?refresh=true` для эндпоинта `/api/groups`.
- Unit-тесты для динамического парсера и эндпоинта `/api/health`.

### Changed
- Синхронизирован порт бэкенда (`8000:8000`) в `docker-compose.yml` и `api_server.py`.
- Добавлен том `./data:/app/data` в `docker-compose.yml` для персистентности базы данных SQLite.
- Обновлен `ROADMAP.md`: отмечены выполненные задачи 1.1, 1.2, 1.3, 3.2, 5.3; Фаза 4 (PWA) законсервирована.

### Removed
- Удалены команды генерации стикеров: `/s`, `/s1`, `/s2`, `/s3`, `/s_fire`, `/s_blood`, `/s_glitch`, `/setsticker`, `/clear_stickers` (`/cs`), `/clear`.
- Удалены голосовые команды и синтез речи: `/gs`, `/langs`, `/r_voice`.
- Удалены тяжелые библиотеки из `requirements.txt`: `gtts`, `pydub`, `Pillow`, `audioop-lts`.

### Archived
- PWA-фронтенд (`pwa/`, `Dockerfile.frontend`) законсервирован и перемещен в каталог `archive/pwa/` и `archive/pwa.tar.gz`.
- Обработчики статики в `api_server.py` адаптированы под работу с архивом и безопасный fallback.
- Сервис `frontend` в `docker-compose.yml` временно отключен.
