# Kalich Bot 🦊

[![CI](https://github.com/mayitnick/kalich-reborn/actions/workflows/python-app.yml/badge.svg)](https://github.com/mayitnick/kalich-reborn/actions/workflows/python-app.yml)

Telegram-бот для студентов и преподавателей, автоматизирующий отслеживание расписания, поиск кабинетов и мониторинг замен.

## 🚀 Ключевые возможности
- **Мониторинг изменений**: Автоматические уведомления при смене кабинета или переносе пары.
- **Парсинг расписания**: Быстрый сбор данных с сайта и кэширование в SQLite.
- **Разделение ролей**: Разные сценарии работы для студентов и преподавателей.
- **Аналитика**: Автоматическая генерация инфографики по загруженности и расписанию (matplotlib).
- **Гибкие настройки**: Голосовые уведомления, кастомные темы и система стикеров.

## 🛠️ Установка и запуск

**1. Клонирование и настройка окружения**
```bash
git clone https://github.com/mayitnick/kalich-reborn.git
cd kalich-reborn
python -m venv venv
# Активация: venv\Scripts\activate (Windows) или source venv/bin/activate (Unix)
pip install -r requirements.txt
```

**2. Конфигурация**
Создайте файл `.env` (можно на основе `.env.example`) и добавьте:
```env
BOT_TOKEN=ваш_токен_от_BotFather
MODERATOR_ID=ваш_telegram_id
LOG_GROUP_ID=id_группы_для_логов  # Опционально
```

**3. Запуск**
```bash
python kalich.py
```
*При первом запуске бот автоматически создаст директорию `data/` и инициализирует базу данных `schedules.db`.*

## 🧪 Тестирование
Проект покрыт unit-тестами с использованием `pytest`. Тесты работают в изолированной in-memory БД.
```bash
# Запуск тестов с проверкой покрытия
pytest tests/ --cov=.
```
