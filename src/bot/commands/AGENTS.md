# AGENTS.md — Authoring Bot Commands & Handlers

This document guides AI Agents on adding, modifying, and organizing commands in `src/bot/commands/`.

---

## 📁 Directory Convention

All files in `src/bot/commands/` are automatically scanned and registered. Organize commands into logical folders:

```text
src/bot/commands/
├── common/         # General info: ping, about, help, cancel
├── student/        # Student features: schedule (/r, /db), now, next, search (/w)
├── teacher/        # Teacher workflows: move, list, overrides
├── admin/          # Moderation: flush, fill, sendall, stats
└── examples/       # Reference templates for media, regex, and custom DI
```

---

## 📝 Command Recipe for Agents

When requested to create a new command, follow this template:

```python
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext

class SampleCommand(BaseCommand):
    name = "sample"                     # Command trigger: /sample
    aliases = ["пример"]                # Also triggered by /пример or text "пример"
    description = "Краткое описание для справки"
    requires = ["db", "parser"]         # Declare needed services
    role = "all"                        # 'all' | 'teacher' | 'moderator' | 'student'

    def execute(self, message: Message, ctx: AppContext):
        # 1. Access services via ctx with full type completion:
        #    ctx.db, ctx.parser, ctx.analytics, ctx.notifier, ctx.config, ctx.bot
        # 2. Reply safely using ctx.reply:
        ctx.reply(message, ctx.wrap_code("Результат команды"))
```

### Media / Photos:
Set `content_types = ["photo"]` (or `"document"`, `"voice"`, `"sticker"`).

### Regex Triggers:
Set `text_patterns = [r"^шаблон\s+\d+$"]`.

### Testing:
Whenever you add a command, add a unit test in `tests/test_command_system.py` or a dedicated test file to guarantee 100% test coverage.
