# AGENTS.md — System Instructions for Kalich Reborn

Compact operational guide for AI agents. Adhere strictly to the invariants below.

---

## ⚡ Essential Commands & Environment Quirks

- **Interpreter (Windows)**: Default system `python` may be Python 3.8. The configured environment with installed dependencies is Python 3.11 (`C:\Python311\python.exe`, defined in `pyrefly.toml`).
- **Run all tests (33 tests, 100% pass required)**:
  - Windows PowerShell: `& "C:\Python311\python.exe" -m pytest tests/`
  - Linux / CI: `PYTHONPATH=. pytest tests/`
  *(Do NOT use `PYTHONPATH=. cmd` syntax directly in PowerShell — it causes a syntax error).*
- **Run a single test**:
  - `& "C:\Python311\python.exe" -m pytest tests/test_command_system.py -v`
  - Or specific test case: `& "C:\Python311\python.exe" -m pytest tests/test_db.py::test_init_db -v`
- **Lint (0 errors required)**:
  - `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
  - Full project check: `flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics`

---

## 🏛️ Architecture & Import Invariants

- **Entrypoint Facade (`kalich.py`)**:
  - Core implementation lives in `src/`. `kalich.py` is an entrypoint and backward-compatibility facade used by `api_server.py` and `tests/`.
  - Uses `_KalichModuleWrapper` to synchronize state between root exports and `src.config` / `src.services.parser`. Never remove this wrapper.
- **Layering & Import Rules (Never import upwards)**:
  - `src.bot` (handlers/commands) → `src.core` (DI/Context) → `src.services` (parser/analytics/notifier) → `src.database` → `src.config`.
  - Always use absolute imports (e.g., `from src.database import get_db_connection`, `import src.config as config`).
  - Access mutable config values via module attribute (e.g. `config.DB_FILE`, `config.requests_get_no_proxy`) so test patches take effect.
- **Database Protocol (`src/database.py`)**:
  - Always obtain connections via `get_db_connection()` (or `ctx.db.get_connection()`).
  - SQLite MUST retain `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout = 5000;`. Never use raw unconfigured `sqlite3.connect`.
- **Command System & DI (`src/core/`, `src/bot/commands/`)**:
  - Commands inherit from `BaseCommand` or use `@command` decorator.
  - Required services must be declared in `requires = ['db', 'parser', ...]` and accessed via `ctx: AppContext` (`ctx.db`, `ctx.parser`, `ctx.bot`, etc.).

---

## 🧪 Testing Invariants & Fixtures

- **Autouse TeleBot Mock**: `tests/conftest.py` automatically mocks `kalich.bot` (`mock_telebot`, autouse=True) to prevent external Telegram API calls.
- **Isolated SQLite**: Use the `memory_db` fixture for any test touching the database; it creates and cleans up an isolated temporary DB file pointing to `kalich.DB_FILE`.
- **No Live Network Calls**: College portal (`глорис-окту-*.рф`) must never be called in tests. Mock `config.requests_get_no_proxy` or `kalich.requests_get_no_proxy`.

---

## 📌 Subdirectory Guidance & Git

- **Subsystem documentation**:
  - `src/AGENTS.md` — Domain services, scraper caching, analytics headless mode, background daemon loops.
  - `src/core/AGENTS.md` — `ServiceContainer`, `AppContext` typing, `CommandScanner` dynamic dispatch.
  - `webapp/AGENTS.md` — Telegram Mini App (TMA) & Standalone PWA client, offline caching, UI components.
  - `tests/AGENTS.md` — Test suite fixtures, mocking patterns, and synchronization.
  - `archive/AGENTS.md` — Archived legacy frontend artifacts (`archive/pwa/`).
- **Git Commits**:
  - Set author/committer if committing: `MayITNick <123010340+mayitnick@users.noreply.github.com>`.
