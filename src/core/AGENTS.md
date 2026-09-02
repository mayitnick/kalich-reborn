# AGENTS.md — Working with `src/core/` (DI & Command Engine)

This document guides AI Agents on how the Dependency Injection (DI) and Command Discovery engine is structured and how to safely modify it.

---

## 🧩 Components Overview

1. **`container.py`**:
   - `ServiceContainer`: Singleton holder of core services.
     - Pre-registered built-ins: `config`, `db` (alias `database`), `parser`, `analytics`, `notifier`, `bot`.
     - `register(name, instance)`: Registers custom services.
     - `create_context()`: Builds an `AppContext` instance for each execution cycle.
   - `AppContext`: Passed to commands. Contains strongly-typed fields so IDEs provide autocompletion.
   - Typed wrappers: `ConfigService`, `DatabaseService`, `ParserService`, `AnalyticsService`, `NotifierService`.

2. **`command.py`**:
   - `BaseCommand`: Abstract base class for all commands and handlers.
     - Attributes: `name`, `aliases`, `text_patterns`, `content_types`, `requires`, `description`, `role`.
     - `execute(message, ctx, ...)`: Entrypoint for execution.
   - `@command`: Decorator for creating lightweight functional commands.

3. **`scanner.py`**:
   - `CommandScanner`:
     - Discovers `.py` files inside a directory (recursive, excludes `__*`).
     - Loads modules dynamically with `importlib`.
     - Validates `cmd.requires` against `container.has(...)`.
     - Builds dispatch wrappers supporting both `(message, ctx)` and direct parameter injection `(message, db, parser)`.
     - Registers routes with `telebot.TeleBot`.

---

## ⚠️ Critical Rules for Modifying `src/core/`

1. **Do not break the `AppContext` typing**:
   - If adding a new built-in service, add its type hint in `AppContext` and `ServiceContainer` so autocomplete works.
2. **Backward Compatibility in Dispatcher**:
   - The dispatcher in `_create_dispatcher` checks `inspect.signature(cmd.execute)` to support:
     - `execute(message, ctx)`
     - `execute(message, db, parser, ...)`
   - Never break this signature resolution.
3. **Fail-Fast Dependency Validation**:
   - Always raise `DependencyError` if a command's `requires` contains an unregistered service name. Do not silently skip.
