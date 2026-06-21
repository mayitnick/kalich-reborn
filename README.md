# Kalich 🦊

[![CI](https://github.com/mayitnick/kalich-reborn/actions/workflows/python-app.yml/badge.svg)](https://github.com/mayitnick/kalich-reborn/actions/workflows/python-app.yml)

**Kalich** — платформа для студентов и преподавателей колледжа: Telegram-бот + PWA веб-приложение. Автоматический парсинг расписания, мониторинг замен, управление кабинетами, аналитика загруженности — всё в одном месте.

---

## ✨ Возможности

### 📅 Расписание
- Автоматический парсинг расписания с сайта колледжа
- Кэширование в SQLite с дедупликацией по хешу
- Поддержка 3-х отделений и всех учебных групп
- Просмотр по дням недели или конкретной дате

### 🔔 Замены и уведомления
- Мгновенные уведомления при изменении расписания
- Преподаватели могут создавать замены через PWA
- Отмена / отмена отмены пар
- Оффлайн-очередь замен с автоматической синхронизацией
- Утренняя рассылка расписания на день

### 👩‍🏫 Панель преподавателя
- Персональное расписание преподавателя (по привязанным кабинетам)
- Управление заменами: смена предмета, кабинета, отмена пар
- Система заявок на роль преподавателя с одобрением модераторами

### 📊 Аналитика
- Распределение предметов по учебной группе (круговая диаграмма)
- Нагрузка по дням недели (столбчатая диаграмма)
- Анализ загруженности кабинетов
- Генерация инфографики через matplotlib

### 🛡️ Модерация
- Панель администратора для управления заменами
- Массовое кэширование расписания по диапазону дат
- Очистка кэша по отделениям
- Одобрение/отклонение заявок преподавателей

### 📱 PWA (Progressive Web App)
- Полноценное веб-приложение с оффлайн-поддержкой (Service Worker)
- Установка на главный экран телефона
- Автоматические обновления с уведомлением пользователя
- Адаптивный дизайн для мобильных устройств
- Тёмная тема, анимации, glassmorphism UI

---

## 🏗️ Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Telegram Bot  │     │   API Server     │     │   PWA Frontend   │
│   (kalich.py)   │────▶│  (api_server.py) │◀────│   (pwa/)         │
│                 │     │   aiohttp :8080  │     │   HTML/JS/CSS    │
└────────┬────────┘     └────────┬─────────┘     └──────────────────┘
         │                       │
         ▼                       ▼
   ┌───────────┐          ┌──────────┐
   │  SQLite   │          │  Парсер  │
   │ schedules │◀─────────│  сайта   │
   │   .db     │          │ колледжа │
   └───────────┘          └──────────┘
```

| Компонент | Описание |
|-----------|----------|
| `kalich.py` | Ядро: Telegram-бот, парсер расписания, бизнес-логика, утренние рассылки |
| `api_server.py` | REST API (aiohttp) + раздача PWA-файлов |
| `messages.py` | Шаблоны сообщений и текстов |
| `pwa/` | Фронтенд: HTML, CSS, JS, Service Worker, иконки |

---

## 🚀 Быстрый старт

### Предварительные требования
- Python 3.10+
- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))

### 1. Клонирование

```bash
git clone https://github.com/mayitnick/kalich-reborn.git
cd kalich-reborn
```

### 2. Установка зависимостей

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Конфигурация

Скопируйте `.env.example` → `.env` и заполните:

```env
BOT_TOKEN=ваш_токен_от_BotFather
MODERATOR_ID=ваш_telegram_id
LOG_GROUP_ID=id_группы_для_логов        # Опционально

# Специальные топики (формат: CHAT_ID:THREAD_ID,...)
# SPECIAL_CHATS=-100123456789:27602

# ID предодобренных преподавателей (через запятую)
# TEACHER_IDS=123456789,987654321
```

### 4. Запуск

**Только Telegram-бот:**
```bash
python kalich.py
```

**API-сервер + PWA (веб-интерфейс):**
```bash
python api_server.py
# → http://localhost:8080
```

> При первом запуске автоматически создаётся директория `data/` и база данных `schedules.db`.

---

## 🐳 Docker

Проект включает Docker-конфигурацию для продакшн-деплоя.

### Быстрый запуск

```bash
# Соберите и запустите оба контейнера
docker compose up -d --build
```

| Сервис | Порт | Описание |
|--------|------|----------|
| `frontend` | `80` | Nginx + PWA статика |
| `backend` | `8000` | Python API-сервер |

### Индивидуальная сборка

```bash
# Только бэкенд
docker build -f Dockerfile.backend -t kalich-backend .
docker run -d --restart always --env-file .env -p 8000:8000 kalich-backend

# Только фронтенд
docker build -f Dockerfile.frontend -t kalich-frontend .
docker run -d --restart always -p 80:80 kalich-frontend
```

Контейнеры настроены с `restart: always` — автоматический перезапуск при крашах и перезагрузках сервера.

---

## 🔌 API Reference

Базовый URL: `http://localhost:8080`

### Аутентификация и пользователи

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `POST` | `/api/auth` | Авторизация по `device_id` |
| `POST` | `/api/auth/request_teacher` | Заявка на роль преподавателя |
| `POST` | `/api/settings` | Обновление настроек пользователя |

### Расписание

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `GET` | `/api/groups` | Список всех учебных групп |
| `GET` | `/api/schedule` | Расписание группы (`department`, `group_id`, `day`/`date`) |
| `GET` | `/api/teacher/schedule` | Расписание преподавателя (`chat_id`, `day`) |

### Замены

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `POST` | `/api/override` | Создание замены |
| `POST` | `/api/sync` | Синхронизация оффлайн-замен |

### Аналитика

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `GET` | `/api/analytics` | Данные аналитики (`type`=group/teacher, `target`) |

### Администрирование

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `GET` | `/api/admin/overrides` | Список всех активных замен |
| `POST` | `/api/admin/delete_override` | Удаление замены |
| `POST` | `/api/admin/fill` | Массовое кэширование расписания |
| `POST` | `/api/admin/flush` | Очистка кэша расписания |

---

## 🧪 Тестирование

Проект покрыт unit-тестами (`pytest`). Тесты работают в изолированной in-memory SQLite БД.

```bash
# Запуск всех тестов
pytest tests/

# С покрытием
pytest tests/ --cov=.

# Конкретный файл
pytest tests/test_api.py -v
```

### Структура тестов

| Файл | Покрытие |
|------|----------|
| `test_api.py` | REST API: авторизация, расписание, замены, синхронизация, аналитика, админ |
| `test_analytics.py` | Генерация диаграмм и аналитических данных |
| `test_commands.py` | Telegram-команды бота |
| `test_db.py` | Операции с базой данных |
| `test_parser.py` | Парсинг расписания с сайта |

---

## 📁 Структура проекта

```
kalich-reborn/
├── .github/
│   └── workflows/
│       └── python-app.yml      # CI: lint + тесты
├── pwa/                        # PWA фронтенд
│   ├── icons/                  # Иконки приложения
│   ├── index.html              # Главная страница
│   ├── styles.css              # Стили (тёмная тема, glassmorphism)
│   ├── app.js                  # Логика приложения
│   ├── sw.js                   # Service Worker (кэширование, обновления)
│   └── manifest.json           # PWA-манифест
├── tests/                      # Unit-тесты
│   ├── conftest.py             # Фикстуры (in-memory DB)
│   ├── test_api.py
│   ├── test_analytics.py
│   ├── test_commands.py
│   ├── test_db.py
│   └── test_parser.py
├── data/                       # Данные (создаётся автоматически)
│   └── schedules.db            # SQLite база
├── kalich.py                   # Telegram-бот + ядро
├── api_server.py               # REST API сервер (aiohttp)
├── messages.py                 # Шаблоны сообщений
├── requirements.txt            # Python-зависимости
├── Dockerfile.backend          # Docker: Python API
├── Dockerfile.frontend         # Docker: Nginx + PWA
├── docker-compose.yml          # Оркестрация контейнеров
├── .env.example                # Пример конфигурации
└── README.md
```

---

## 🔧 Технологический стек

| Слой | Технология |
|------|-----------|
| Бот | [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) |
| API | [aiohttp](https://docs.aiohttp.org/) |
| БД | SQLite3 |
| Парсинг | BeautifulSoup4 + requests |
| Графики | matplotlib + Pillow |
| Голос | gTTS + pydub |
| Фронтенд | Vanilla HTML/CSS/JS + Service Worker |
| CI | GitHub Actions (flake8 + pytest) |
| Деплой | Docker + docker-compose |

---

## 📄 Лицензия

Проект разработан для внутреннего использования колледжа.
