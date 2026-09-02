# AGENTS.md — Testing Guidelines & Invariants

This document guides AI Agents on running, maintaining, and writing tests in `tests/`.

---

## ⚡ Quick Test Commands

```bash
# Run entire test suite
PYTHONPATH=. pytest tests/

# Run with verbose output and stop on first failure
PYTHONPATH=. pytest tests/ -v -x

# Run a single test file
PYTHONPATH=. pytest tests/test_command_system.py
```

---

## 🧰 Key Test Fixtures (`tests/conftest.py`)

1. **`mock_telebot` (autouse=True)**:
   - Automatically replaces `kalich.bot` with a `MagicMock()`.
   - Prevents tests from attempting real Telegram API network requests.
2. **`memory_db`**:
   - Creates an isolated temporary SQLite database file for each test.
   - Points `kalich.DB_FILE` to the temporary file and runs `kalich.init_db()`.
   - Cleans up and deletes the temporary file after test completion.

---

## ⚠️ Critical Rules for AI Agents

1. **Never break existing tests**:
   - All tests in `test_analytics.py`, `test_api.py`, `test_commands.py`, `test_db.py`, `test_parser.py`, and `test_command_system.py` must pass at all times.
2. **Mocking Network Calls**:
   - Never let tests query external college websites (`глорис-окту-*.рф`).
   - Mock `kalich.requests_get_no_proxy` or use `monkeypatch.setattr('src.config.requests_get_no_proxy', mock_fn)`.
3. **Module Synchronization**:
   - Setting `kalich.DB_FILE`, `kalich.GROUP_NAME_TO_ID`, `kalich.bot` dynamically synchronizes with `src.config`, `src.services.parser`, and `src.bot.instance` via `_KalichModuleWrapper`.
