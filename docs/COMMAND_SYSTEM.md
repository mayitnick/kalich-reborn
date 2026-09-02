# Руководство по системе команд и внедрению зависимостей (DI) 🧩

В проекте Kalich реализована модульная система команд с **автоматическим сканированием директорий (Auto-discovery)** и **типизированным внедрением зависимостей (Dependency Injection)**.

Она создана для того, чтобы любой разработчик мог быстро добавить команду или обработчик медиа, не трогая основной файл бота и получая **100% автодополнение методов (Type Hints)** в любой современной IDE (VS Code, PyCharm, Cursor и т.д.).

---

## 🏗️ 1. Как это устроено под капотом

Система состоит из трёх ключевых компонентов (`src/core/`):

1. **`ServiceContainer` (`src/core/container.py`)**:
   - Центральный реестр всех долгоживущих сервисов (база данных, парсер расписания, аналитика, нотификатор, конфигурация, бот).
   - Инициализируется один раз при старте приложения.
   - Позволяет регистрировать любые ваши кастомные сервисы.

2. **`AppContext` (`src/core/container.py`)**:
   - Объект контекста, передаваемый в каждую команду.
   - Содержит строго типизированные свойства:
     - `ctx.db` / `ctx.database`: методы работы с SQLite (`DatabaseService`).
     - `ctx.parser`: методы поиска и загрузки расписания (`ParserService`).
     - `ctx.analytics`: генерация графиков и диаграмм (`AnalyticsService`).
     - `ctx.notifier`: статус пар, звонки, форматирование совмещений (`NotifierService`).
     - `ctx.config`: переменные окружения, списки модераторов, пути (`ConfigService`).
     - `ctx.bot`: инстанс `telebot.TeleBot`.
     - `ctx.reply(message, text, ...)`: безопасная отправка ответа в тред/чат.
     - `ctx.wrap_code(text)`: обрамление в Markdown моноширинный блок.

3. **`CommandScanner` (`src/core/scanner.py`)**:
   - При запуске рекурсивно обходит директорию `src/bot/commands/` (включая любые вложенные папки).
   - Находит классы-наследники `BaseCommand` или функции с декоратором `@command`.
   - **Валидирует зависимости**: если команда требует сервис (например, `requires = ['db']`), сканер проверяет его наличие в контейнере. Если модуль забыли зарегистрировать, приложение сразу выбросит понятную ошибку `DependencyError` до запуска бота.
   - Автоматически регистрирует команды, текстовые алиасы, regex-шаблоны и обработчики медиа в `TeleBot`.

---

## 🚀 2. Быстрый старт: Создание новой команды

Чтобы добавить новую команду, просто создайте файл `.py` в директории `src/bot/commands/` (например, `src/bot/commands/student/my_command.py`).

### Способ А: Класс-команда (Рекомендуемый)

```python
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext

class MyCommand(BaseCommand):
    name = "hello"                           # Вызывается как /hello
    aliases = ["привет", "хай"]              # Сработает и на /привет, и на текст "привет"
    description = "Приветственное сообщение"
    requires = ["db"]                        # Запрашиваем модуль базы данных

    def execute(self, message: Message, ctx: AppContext):
        # IDE подскажет все методы ctx.db!
        settings = ctx.db.get_user_settings(message.chat.id)
        user_name = message.from_user.first_name or "друг"
        
        ctx.reply(message, f"Привет, {user_name}! Рад тебя видеть 🦊")
```

### Способ Б: Функциональный декоратор

```python
from telebot.types import Message
from src.core.command import command
from src.core.container import AppContext

@command(name="ping", aliases=["пинг", "живой?"], requires=["db", "config"])
def cmd_ping(message: Message, ctx: AppContext):
    ctx.reply(message, "🏓 Понг! Бот на связи.")
```

---

## 💡 3. Способы запроса модулей (Dependency Injection)

### Вариант 1: Через типизированный `ctx: AppContext` (Автодополнение IDE)
В параметрах метода указывается `ctx: AppContext`:
```python
class ScheduleCommand(BaseCommand):
    name = "r"
    requires = ["db", "parser", "notifier"]

    def execute(self, message: Message, ctx: AppContext):
        day = 1
        data = ctx.db.get_all_schedules_for_day(day)
        # При вводе `ctx.` IDE отобразит db, parser, analytics, notifier, bot!
        ...
```

### Вариант 2: Прямая инъекция параметров
Сканер анализирует имена аргументов метода `execute` и автоматически передает запрошенные объекты из контейнера:
```python
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import DatabaseService, ParserService

class LookupCommand(BaseCommand):
    name = "find"
    requires = ["db", "parser"]

    # Диспетчер сам подставит db и parser из контейнера!
    def execute(self, message: Message, db: DatabaseService, parser: ParserService):
        name, info = parser.find_group_info(message.text)
        ...
```

---

## 🖼️ 4. Обработка изображений и медиа

Если ваша команда должна реагировать на фотографии, голосовые или документы, укажите `content_types`:

```python
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext

class PhotoProcessor(BaseCommand):
    name = "photo_handler"
    content_types = ["photo"]                # Перехватываем фотографии
    description = "Обработчик входящих фото"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext):
        photo = message.photo[-1]  # Наибольшее разрешение
        caption = message.caption or "без текста"
        
        ctx.reply(
            message,
            f"📸 Принято фото!\n"
            f"Размер: {photo.width}x{photo.height}\n"
            f"File ID: `{photo.file_id}`\n"
            f"Подпись: {caption}",
            parse_mode="Markdown"
        )
```

Поддерживаемые типы: `"photo"`, `"document"`, `"voice"`, `"video"`, `"sticker"`, `"audio"`.

---

## 🔤 5. Текстовые алиасы и регулярные выражения

Вы можете активировать команду по фразам в тексте сообщения с помощью `text_patterns`:

```python
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext

class CallQuestionHandler(BaseCommand):
    name = "call_question"
    # Сработает на: "когда пара?", "когда звонок", "пара когда?"
    text_patterns = [
        r"^когда\s+(пара|звонок)\??$",
        r"^(пара|звонок)\s+когда\??$"
    ]
    requires = ["notifier"]

    def execute(self, message: Message, ctx: AppContext):
        status, left, idx = ctx.notifier.get_status()
        if status == "work":
            ctx.reply(message, f"Идет пара №{idx+1}. До звонка: {left}.")
        else:
            ctx.reply(message, "Сейчас занятий нет.")
```

---

## 👮 6. Ограничение прав и роли пользователей

Вместо ручных проверок в теле функции используйте параметр `role`:

| Роль | Поведение |
|---|---|
| `role = "all"` *(по умолчанию)* | Доступно всем пользователям. |
| `role = "teacher"` | Бот автоматически проверит `ctx.db.is_teacher(message.chat.id)`. Если пользователь не учитель, команда просто проигнорируется. |
| `role = "moderator"` | Бот проверит `message.from_user.id in ctx.config.MODERATOR_IDS`. |

```python
class TeacherOnlyCommand(BaseCommand):
    name = "mycabinet"
    role = "teacher"          # Доступно только подтвержденным преподавателям
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext):
        dept, rooms = ctx.db.get_teacher_info(message.chat.id)
        ctx.reply(message, f"Ваши кабинеты: {', '.join(rooms)}")
```

---

## 🔌 7. Как добавить свой сервис в `ServiceContainer`

Если вам нужно интегрировать сторонний API (погоду, нейросеть, генератор QR-кодов, внешнюю БД):

1. **Опишите класс сервиса** (желательно в `src/services/`):
   ```python
   # src/services/weather.py
   class WeatherService:
       def get_temperature(self, city: str = "Москва") -> str:
           return "+18°C, солнечно"
   ```

2. **Зарегистрируйте сервис в контейнере**:
   В основном файле при инициализации:
   ```python
   from src.core.container import ServiceContainer
   from src.services.weather import WeatherService

   container = ServiceContainer(bot=bot)
   container.register("weather", WeatherService())
   ```

3. **Используйте сервис в любой команде**:
   ```python
   class WeatherCommand(BaseCommand):
       name = "weather"
       requires = ["weather"]   # Зависимость валидируется автоматически!

       def execute(self, message: Message, ctx: AppContext):
           weather: WeatherService = ctx.get_service("weather")
           ctx.reply(message, f"Погода: {weather.get_temperature()}")
   ```

---

## 🧪 8. Тестирование команд

Тестировать модульные команды предельно просто, так как зависимости передаются извне:

```python
# tests/test_my_command.py
from unittest.mock import MagicMock
from src.core.container import ServiceContainer
from src.bot.commands.common.ping import PingCommand

def test_ping_command():
    mock_db = MagicMock()
    mock_db.get_user_settings.return_value = {'fluffy_mode': False}

    container = ServiceContainer()
    container.db = mock_db
    ctx = container.create_context()
    ctx.reply = MagicMock()

    cmd = PingCommand()
    mock_msg = MagicMock()
    mock_msg.chat.id = 12345

    cmd.execute(mock_msg, ctx)
    ctx.reply.assert_called_once()
```
