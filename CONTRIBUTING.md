# Руководство для контрибьюторов (Contributing Guide) 🤝

Привет! Спасибо за интерес к развитию проекта **Kalich Reborn**! Этот документ поможет вам быстро развернуть проект, понять архитектуру и начать писать код в соответствии с нашими стандартами.

---

## 🚀 1. Быстрый старт и окружение

### Требования:
- Python 3.10+ (рекомендуется 3.11–3.14)
- Git
- SQLite 3

### Установка:
```bash
# 1. Клонируйте репозиторий
git clone https://github.com/mayitnick/kalich-reborn.git
cd kalich-reborn

# 2. Создайте и активируйте виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# .\venv\Scripts\activate # Windows

# 3. Установите зависимости
pip install -r requirements.txt
pip install pytest pytest-cov flake8

# 4. Настройте файл .env (скопируйте пример)
cp .env.example .env  # или создайте .env с BOT_TOKEN
```

---

## 🏛️ 2. Структура проекта

- **`src/`**: Ядро платформы.
  - `src/core/`: Контейнер зависимостей (`ServiceContainer`), контекст выполнения (`AppContext`), сканер команд (`CommandScanner`).
  - `src/database.py`: База данных SQLite (WAL-режим, таймаут 5000 мс).
  - `src/services/`: Бизнес-логика (парсер расписания, аналитика, нотификатор).
  - `src/bot/commands/`: Все команды и обработчики бота (автоматически сканируются!).
- **`kalich.py`**: Главный файл запуска Telegram-бота.
- **`api_server.py`**: Асинхронный REST API сервер (`aiohttp`).
- **`docs/`**: Подробная техническая документация:
  - [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — детальное описание архитектуры и потоков данных.
  - [`docs/COMMAND_SYSTEM.md`](docs/COMMAND_SYSTEM.md) — создание команд, DI и автодополнение IDE.

---

## 💡 3. Как добавить новую команду

Для добавления команды не нужно редактировать `kalich.py`! Просто создайте файл в `src/bot/commands/`:

```python
# src/bot/commands/student/my_cmd.py
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext

class MyCommand(BaseCommand):
    name = "mycmd"                      # Вызывается через /mycmd
    aliases = ["мойкоманда"]            # Алиас
    description = "Полезное действие"
    requires = ["db", "parser"]         # Запрос нужных сервисов

    def execute(self, message: Message, ctx: AppContext):
        # IDE подскажет все методы ctx.db и ctx.parser!
        ctx.reply(message, "Команда успешно выполнена!")
```

---

## 🧪 4. Тестирование и линтинг

Перед отправкой изменений обязательно запустите тесты и линтер:

```bash
# 1. Запуск всех тестов (все 33 теста должны пройти успешно!)
PYTHONPATH=. pytest tests/

# 2. Проверка линтером (должно вернуть 0)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

---

## 🌿 5. Процесс разработки (Git Flow)

1. Создайте отдельную ветку под вашу задачу:
   ```bash
   git checkout -b feat/my-awesome-feature
   ```
2. Пишите понятные коммиты по конвенции Conventional Commits:
   - `feat(...)`: новый функционал
   - `fix(...)`: исправление багов
   - `docs(...)`: обновление документации
   - `refactor(...)`: рефакторинг кода
   - `test(...)`: добавление тестов
3. Откройте Pull Request в ветку `main`.
