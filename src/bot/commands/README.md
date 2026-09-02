# Команды и обработчики бота (src/bot/commands/) 🤖

Все `.py` файлы в этой директории и любых её подпапках **автоматически обнаруживаются и регистрируются** сканером команд `CommandScanner`.

---

## 📁 Структура папок

- `common/`: Информационные и сервисные команды (`/ping`, `/about`, `/help`, `/cancel`).
- `student/`: Функции для студентов (`/r`, `/db`, `/now`, `/next`, `/time`, `/w`, `/unsub`, `/settings`).
- `teacher/`: Команды для преподавателей (`/move`, `/list`).
- `admin/`: Панель модераторов (`/flush`, `/fill`, `/sendall`, `/stats`).
- `examples/`: Примеры создания обработчиков фото, текста и DI.

---

## ⚡ Быстрый шаблон (Copy-Paste)

```python
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext

class ExampleCommand(BaseCommand):
    name = "mycmd"                      # Сработает на /mycmd
    aliases = ["мойкоманда"]            # Алиас
    description = "Описание команды"
    requires = ["db"]                   # Запрашиваемые модули: 'db', 'parser', 'analytics', 'notifier'

    def execute(self, message: Message, ctx: AppContext):
        # Доступ ко всем модулям с автодополнением в IDE через ctx!
        ctx.reply(message, "Ответ бота")
```

Подробное руководство: [docs/COMMAND_SYSTEM.md](../../../docs/COMMAND_SYSTEM.md)
