# AGENTS.md — System Instructions for AI Agents

Welcome, AI Agent. This document provides a rapid, comprehensive overview of the **Kalich Reborn** repository, its architecture, rules, invariants, and operational workflows. Read this before modifying any code.

---

## 🎯 1. Project Mission & High-Level Topology

Kalich Reborn is a high-performance, modular Telegram bot and REST API platform that monitors, parses, and distributes class schedules and teacher room changes for college departments.

### Primary Directories:
- `src/`: Core Python package containing business logic, database layer, parser, analytics, notifications, and bot components.
  - `src/core/`: Dependency injection container (`ServiceContainer`), typed execution context (`AppContext`), command scanner (`CommandScanner`), and base command abstractions (`BaseCommand`, `@command`).
  - `src/services/`: Independent domain services (network scraper `parser.py`, Matplotlib chart generator `analytics.py`, background loops `notifier.py`).
  - `src/bot/`: Telegram bot setup, keyboard factory, and command modules (`src/bot/commands/`).
  - `src/config.py`: Environment variables and system constants.
  - `src/database.py`: SQLite DAL with WAL mode, busy timeout, and monitor/custom name managers.
- `kalich.py`: Bot entrypoint and backward-compatibility facade (re-exports symbols and synchronizes module state).
- `api_server.py`: Async REST API on `aiohttp` (port 8000).
- `data/`: Local persistent storage (`schedules.db`, JSON caches).
- `tests/`: Automated unit tests using `pytest` and `unittest.mock`.
- `archive/`: Archived PWA frontend (`pwa/`, `pwa.tar.gz`) preserved for historical reference. DO NOT delete or re-enable without explicit user request.
- `docs/`: Human and architectural documentation (`ARCHITECTURE.md`, `COMMAND_SYSTEM.md`).

---

## 🔒 2. Critical Invariants & Rules for AI Agents

1. **Test-Driven Invariant (100% PASS)**:
   - Always run `PYTHONPATH=. pytest tests/` before and after changes.
   - All tests (currently 33/33) MUST pass. Zero regressions allowed.
2. **Linter Invariant (0 ERRORS)**:
   - Run `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`. Must return `0`.
3. **Database Access Protocol**:
   - Always use `src.database.get_db_connection()` (or `ctx.db.get_connection()`).
   - SQLite MUST use `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout = 5000;`. Never hardcode raw `sqlite3.connect(...)` without these pragmas.
4. **Dependency Injection & Commands**:
   - When adding or modifying commands, put them into `src/bot/commands/` as `BaseCommand` subclasses or `@command` functions.
   - Declare required services via `requires = ['db', 'parser', ...]`.
   - Access services via `ctx: AppContext` (e.g. `ctx.db`, `ctx.parser`, `ctx.analytics`, `ctx.notifier`, `ctx.config`, `ctx.bot`).
5. **Preserve `kalich.py` Facade**:
   - External consumers (`api_server.py`, `tests/`) import functions and attributes from `kalich`.
   - `kalich.py` contains `_KalichModuleWrapper` to proxy changes to `src.config` and `src.services.parser`. Never remove this wrapper.
6. **Git Authorship**:
   - If committing on behalf of the user, ensure Git author and committer are set to:
     `MayITNick <123010340+mayitnick@users.noreply.github.com>`.

---

## 🛠️ 3. Common Development Commands

```bash
# 1. Run all unit tests
PYTHONPATH=. pytest tests/

# 2. Run flake8 critical syntax/undefined name checks
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# 3. Run specific test file
PYTHONPATH=. pytest tests/test_command_system.py -v

# 4. Check git status
git status
```

---

## 🧭 4. Subdirectory AGENTS.md Index

For focused instructions on specific subsystems, consult:
- [`src/AGENTS.md`](file:///root/kalich-reborn/src/AGENTS.md) — Working inside `src/` modules.
- [`src/core/AGENTS.md`](file:///root/kalich-reborn/src/core/AGENTS.md) — Working with the DI container and scanner.
- [`src/bot/commands/AGENTS.md`](file:///root/kalich-reborn/src/bot/commands/AGENTS.md) — Writing and testing bot commands.
- [`tests/AGENTS.md`](file:///root/kalich-reborn/tests/AGENTS.md) — Testing patterns, fixtures, and mocks.
- [`archive/AGENTS.md`](file:///root/kalich-reborn/archive/AGENTS.md) — Information regarding the archived PWA.
