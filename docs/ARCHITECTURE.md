# Архитектура и руководство разработчика Kalich 🦊

В этом документе описывается архитектурное устройство платформы **Kalich**, структура модулей пакета `src/`, потоки данных (Data Flow), а также практические рекомендации по добавлению новых функций, команд, сервисов и тестов.

---

## 🏛️ 1. Принципы и общая структура

Проект построен по модульному принципу с разделением ответственности (**Single Responsibility Principle**):

```text
kalich-reborn/
├── src/                        # Основной пакет логики приложения
│   ├── config.py               # Конфигурация, пути, переменные окружения, расписание звонков
│   ├── database.py             # Слой работы с SQLite (WAL, транзакции, менеджеры данных)
│   ├── services/               # Независимые бизнес-сервисы
│   │   ├── parser.py           # Сетевой скрейпинг сайта колледжа (Глорис), кэширование групп
│   │   ├── analytics.py        # Генерация отчетов и диаграмм нагрузки (Matplotlib)
│   │   └── notifier.py         # Фоновые процессы, планировщик рассылок, совмещения кабинетов
│   └── bot/                    # Модули Telegram-бота
│       ├── instance.py         # Экземпляр TeleBot, обертки безопасной отправки сообщений
│       ├── keyboards.py        # Фабрика инлайн- и реплай-клавиатур
│       └── handlers/           # Обработчики команд и диалогов
│           └── teacher.py      # Логика и команды режима преподавателя
├── data/                       # Локальное хранилище данных (SQLite, JSON кэши)
├── tests/                      # Набор unit-тестов (pytest)
├── archive/                    # Законсервированный PWA-фронтенд
├── api_server.py               # Внешний REST API сервер на базе aiohttp
├── kalich.py                   # Точка входа Telegram-бота и фасад совместимости
├── messages.py                 # Шаблоны текстов сообщений и справка
├── requirements.txt            # Зависимости Python
├── ROADMAP.md                  # Дорожная карта проекта
├── CHANGELOG.md                # Журнал изменений
└── README.md                   # Презентационная документация проекта
```

### Назначение ключевых компонентов:

| Модуль | Ответственность |
|---|---|
| `src.config` | Загрузка `.env`, хранение системных констант (`CALLS`, `SYSTEM_FILTERS`), путей к файлам (`DB_FILE`, `GROUPS_CACHE_FILE`). Не содержит бизнес-логики. |
| `src.database` | Инкапсулирует все SQL-запросы к SQLite, гарантируя использование `PRAGMA journal_mode=WAL;` и `busy_timeout = 5000`. Включает классы `MonitorManager` и `CustomNamesManager`. |
| `src.services.parser` | Сетевое взаимодействие с сайтом колледжа (`requests_get_no_proxy`), парсинг отделений 1, 2, 3, интеллектуальный нестрогий поиск групп (`find_group_info`). |
| `src.services.analytics` | Построение графиков без GUI (`matplotlib.use('Agg')`), расчёт загруженности кабинетов и групп, агрегация исторических данных. |
| `src.services.notifier` | Фоновые циклы: `check_loop` (проверка обновлений расписания на сайте раз в 10 минут), `morning_broadcast` (утренняя рассылка в 07:00), `teacher_notification_loop` (отложенная рассылка замен учителей). |
| `src.bot.instance` | Инициализация бота `telebot.TeleBot`, поддержка системных прокси, методы `wrap_code(...)` и `reply_safe(...)`. |
| `src.bot.keyboards` | Генерация `InlineKeyboardMarkup` для настроек, подтверждения преподавателей и меню выбора роли. |
| `kalich.py` | Сборка всех модулей воедино, диспетчеризация команд бота, поддержка обратной совместимости через синхронизационный модуль-обертку. |
| `api_server.py` | Асинхронный REST API на `aiohttp`, предоставляющий эндпоинты мониторинга (`/api/health`), расписаний, замен и аналитики. |

---

## 🔄 2. Потоки данных (Data Flow)

### 2.1. Студент запрашивает расписание (`/r` или `/db`)
```
Telegram Update ──▶ ad_and_execute / cmd_r_today
                         │
                         ├──▶ src.database.is_teacher(chat_id) ──▶ (если учитель: перенаправление)
                         ├──▶ src.database.monitor_manager.get_user_monitors(chat_id)
                         ├──▶ src.database.get_all_schedules_for_day(day)
                         ├──▶ src.database.apply_teacher_overrides(all_data, day)
                         │
                         ▼
                   _render_schedule_msg
                         │
                         ├──▶ src.services.notifier.format_with_overlap(...)
                         ▼
                   src.bot.instance.reply_safe (Markdown-блок с кодом)
```

### 2.2. Преподаватель делает замену (`/move 3 101 п=Алгебра`)
```
Telegram Update ──▶ src.bot.handlers.teacher.cmd_move
                         │
                         ├──▶ src.database.is_teacher(chat_id)
                         ├──▶ src.database.save_teacher_override(...)
                         │      (запись в SQLite: notified=0, notify_after = now + 300)
                         ▼
                   Ответ преподавателю: "Сохранено. Уведомление через ~5 мин."
                         │
                         ▼ (через 5 минут воркер teacher_notification_loop)
                   src.services.notifier.send_teacher_override_notifications_for_day(day)
                         │
                         ▼
                   Точечная рассылка студентам затронутой группы
```

### 2.3. Фоновая синхронизация с сайтом колледжа
```
src.services.notifier.check_loop (каждые 600 сек)
         │
         ├──▶ src.services.parser.fetch_lessons(day, gid, dept)
         ├──▶ Сравнение MD5-хеша содержимого с базой данных
         │
         ├──▶ (Если хеш изменился):
         │      ├── src.database.save_schedule_to_db(...)
         │      └── src.services.notifier.send_updates_for_day(day, data)
         └──▶ Засыпает на 10 минут
```

---

## 🛠️ 3. Руководство: Как развивать структуру

### 3.1. Как добавить новую команду в бота

1. **Выберите подходящий модуль хэндлеров** в `src/bot/handlers/`:
   - Если команда для студентов → добавьте её в `src/bot/handlers/student.py` (или в `kalich.py`).
   - Если для преподавателей → `src/bot/handlers/teacher.py`.
   - Если общая/информационная → `src/bot/handlers/common.py`.
   - Если функционал крупный (например, домашние задания или опросы) → создайте новый файл `src/bot/handlers/homework.py`.

2. **Напишите обработчик**:
   ```python
   # src/bot/handlers/student.py
   from src.bot.instance import bot, reply_safe, wrap_code
   import messages

   @bot.message_handler(commands=['mycommand'])
   def cmd_mycommand(message):
       reply_safe(message, wrap_code("Результат команды"))
   ```

3. **Зарегистрируйте команду**:
   Если команда должна отображаться в справке и проверять подписку на канал, добавьте её в `messages.py` (`HELP_TEXT_MAIN`, `ABOUT_COMMANDS`) и в список команд в `ad_and_execute` в `kalich.py`.

4. **Напишите unit-тест** в `tests/test_commands.py`:
   ```python
   @patch('kalich.reply_safe')
   def test_cmd_mycommand(self, mock_reply):
       kalich.cmd_mycommand(self.message)
       mock_reply.assert_called_once()
   ```

---

### 3.2. Как добавить новый сервис или фоновую задачу

1. Создайте модуль в `src/services/` (например, `src/services/exporter.py`):
   - Сервисы не должны напрямую зависеть от хэндлеров бота (во избежание циклических импортов).
   - Все операции с базой выполняйте через методы `src.database` или соединение `get_db_connection()`.

   ```python
   # src/services/exporter.py
   import json
   from src.database import get_db_connection

   def export_group_schedule_to_json(group_id, department):
       conn = get_db_connection()
       rows = conn.execute(
           "SELECT day, lessons_text FROM schedules WHERE group_id=? AND department=?",
           (group_id, department)
       ).fetchall()
       conn.close()
       return [{"day": r[0], "lessons": json.loads(r[1])} for r in rows]
   ```

2. Если требуется **фоновый воркер** (демон):
   - Оформите его как функцию с циклом `while True:` и `time.sleep(...)`.
   - Запустите демон-поток в блоке `if __name__ == '__main__':` в `kalich.py`:
     ```python
     threading.Thread(target=my_background_service, daemon=True).start()
     ```

---

### 3.3. Как расширить базу данных (Database Schema & Methods)

1. **Добавление таблицы**:
   Откройте `src/database.py` и добавьте `CREATE TABLE IF NOT EXISTS` в функцию `init_db()`:
   ```python
   conn.execute('''CREATE TABLE IF NOT EXISTS homework
                   (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    subject TEXT,
                    task TEXT,
                    due_date TEXT)''')
   ```

2. **Работа с соединением**:
   Всегда используйте функцию `get_db_connection()`, которая автоматически включает режим WAL и настраивает таймаут ожидания при параллельном доступе:
   ```python
   conn = get_db_connection()
   try:
       conn.execute("INSERT INTO homework (group_id, subject, task, due_date) VALUES (?, ?, ?, ?)",
                    (group_id, subject, task, due_date))
       conn.commit()
   finally:
       conn.close()
   ```

3. **Тестирование базы**:
   Добавьте проверку в `tests/test_db.py`, используя фикстуру `memory_db`.

---

### 3.4. Как добавить новый REST API эндпоинт

1. Откройте `api_server.py`.
2. Создайте асинхронный хэндлер:
   ```python
   async def handle_get_homework(request):
       group_id = request.query.get('group_id')
       if not group_id:
           return web.json_response({'status': 'error', 'message': 'Missing group_id'}, status=400)
       
       # Вызов функции сервиса или БД
       data = get_homework_for_group(int(group_id))
       return web.json_response({'status': 'success', 'data': data})
   ```
3. Зарегистрируйте маршрут в функции `setup_routes(app)`:
   ```python
   app.router.add_get('/api/homework', handle_get_homework)
   ```
4. Напишите тест эндпоинта в `tests/test_api.py`.

---

## 🔒 4. Соглашения и стандарты кода (Code Standards)

1. **Импорты**:
   - Всегда импортируйте модули через абсолютные пути пакета `src.*`:
     ```python
     from src.config import DB_FILE
     from src.database import get_db_connection
     from src.services.parser import find_group_info
     ```
   - Избегайте циклических зависимостей: слой `database` и `config` являются фундаментальными и не должны импортировать `bot` или `services`.

2. **Линтинг (Flake8)**:
   Проект проверяется CI-пайплайном с жестким контролем синтаксических ошибок:
   ```bash
   flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
   ```
   Убедитесь, что в коде нет неопределенных переменных (`F821`) и синтаксических ошибок.

3. **Unit-тестирование**:
   Любой новый функционал должен сопровождаться тестами:
   ```bash
   PYTHONPATH=. pytest tests/ --cov=.
   ```
   Все тесты изолированы и используют временную базу данных (`tests/conftest.py`).
