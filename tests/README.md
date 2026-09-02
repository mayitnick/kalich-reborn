# Набор тестов (tests/) 🧪

В этой директории расположены автоматические тесты проекта, написанные на фреймворке **`pytest`**.

---

## 🚀 Запуск тестов

```bash
# Запустить все тесты
PYTHONPATH=. pytest tests/

# Запустить с подробным выводом
PYTHONPATH=. pytest tests/ -v

# Запустить конкретный файл
PYTHONPATH=. pytest tests/test_command_system.py
```

---

## 📁 Структура тестов

| Файл | Что тестирует |
|---|---|
| `test_analytics.py` | Построение графиков Matplotlib и расчёт статистики. |
| `test_api.py` | Все REST API эндпоинты (`/api/health`, `/api/schedule`, `/api/analytics` и др.). |
| `test_command_system.py` | Контейнер зависимостей (`ServiceContainer`), сканер команд и валидацию `requires`. |
| `test_commands.py` | Обработчики команд Telegram-бота. |
| `test_db.py` | Слой SQLite, транзакции, историю и замены. |
| `test_parser.py` | Динамический парсер сайта колледжа и нестрогий поиск групп. |
| `conftest.py` | Глобальные фикстуры (мок Telegram бота, временная изолированная база данных). |
