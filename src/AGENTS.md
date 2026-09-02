# AGENTS.md — Working with `src/` (Core Logic & Services)

This guide is for AI Agents modifying, extending, or maintaining code in `src/`.

---

## 🏛️ Layer Architecture & Import Hierarchy

To avoid circular imports and maintain a clean architecture, adhere strictly to this layering rule:

```
[Layer 4: Presentation]   src.bot.handlers / src.bot.commands
                                    │
                                    ▼
[Layer 3: Orchestration]  src.core (ServiceContainer, AppContext, Scanner)
                                    │
                                    ▼
[Layer 2: Domain Services]src.services (parser.py, analytics.py, notifier.py)
                                    │
                                    ▼
[Layer 1: Persistence]    src.database.py
                                    │
                                    ▼
[Layer 0: Configuration]  src.config.py
```

### Import Rules:
1. **Never import upwards**: Layer 1 (`database.py`) must never import Layer 4 (`bot`) or Layer 3 (`core`).
2. **Absolute package imports**: Always use `from src.database import ...` or `import src.config as config`.
3. **Module-level references**: When accessing `config.DB_FILE` or `config.requests_get_no_proxy`, access them via the imported `config` module attribute so monkeypatches during testing propagate automatically.

---

## 💾 Database Layer (`src/database.py`)

- **Connection Factory**: Always use `get_db_connection()`. It handles directory creation, WAL mode, and busy timeouts.
- **Transactions**: For multiple write queries, use `conn = get_db_connection()`, execute statements, call `conn.commit()`, and always close in a `try...finally` block.
- **Managers**:
  - `monitor_manager`: Manages subscriptions (`active_monitors.json` and in-memory dict).
  - `custom_names_manager`: Manages user item overrides (`custom_names.json`).
- **Dates & Weekdays**: College schedule uses 1=Monday through 6=Saturday.

---

## 🌐 Network & Parser Layer (`src/services/parser.py`)

- **Proxy Bypass**: College website (`глорис-окту-*.рф`) has issues with certain environment proxies. Always use `config.requests_get_no_proxy(...)` or `requests_get_no_proxy(...)`.
- **In-Memory Cache**: `GROUP_NAME_TO_ID` maps `"GROUP_NAME"` -> `[department_int, group_id_int]`. `GROUP_ID_TO_NAME` is the reverse mapping.
- **Dynamic Matching**: Always use `find_group_info(text)` for user queries; it handles spaces, dashes, case-insensitivity, and auto-fetches fresh lists from Gloris if a group is newly introduced.

---

## 📊 Analytics Layer (`src/services/analytics.py`)

- **Headless Mode**: Matplotlib MUST remain on the `'Agg'` backend (`matplotlib.use('Agg')`). Never invoke `plt.show()`.
- **Thread Safety**: Wrap plot creation, save figure to `io.BytesIO()`, and always close figures via `plt.close(fig)` to prevent memory leaks in daemon threads.

---

## 📢 Notifier Layer (`src/services/notifier.py`)

- Contains daemon thread loops:
  - `check_loop()`: Polling Gloris every 10 min for schedule changes.
  - `morning_broadcast()`: 07:00 AM weekday notification.
  - `teacher_notification_loop()`: 5-minute delayed notification for `/move` replacements.
- **Thread Spawning**: Loops should be launched with `daemon=True`.
