# pyrefly: ignore [missing-import]
import time
_kalich_start_time = time.perf_counter()
#  ___  __        ________      ___           ___      ________      ___  ___     
# |\  \|\  \     |\   __  \    |\  \         |\  \    |\   ____\    |\  \|\  \    
# \ \  \/  /|_   \ \  \|\  \   \ \  \        \ \  \   \ \  \___|    \ \  \\\  \   
#  \ \   ___  \   \ \   __  \   \ \  \        \ \  \   \ \  \        \ \   __  \  
#   \ \  \\ \  \   \ \  \ \  \   \ \  \____    \ \  \   \ \  \____    \ \  \ \  \ 
#    \ \__\\ \__\   \ \__\ \__\   \ \_______\   \ \__\   \ \_______\   \ \__\ \__\
#     \|__| \|__|    \|__|\|__|    \|_______|    \|__|    \|_______|    \|__|\|__|
                                                                                
                                                                                
                                                                                
import io
import os
import re
import json
import time
import random
import hashlib
import logging
import sqlite3
import telebot
import urllib3
import messages
import requests
import textwrap
import threading
import matplotlib
import collections
from gtts import gTTS
import urllib.request
from typing import cast, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydub import AudioSegment
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt  # noqa: E402
matplotlib.use('Agg')


load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def requests_get_no_proxy(*args, **kwargs):
    s = requests.Session()
    s.trust_env = False
    return s.get(*args, **kwargs)


# ====== КОНФИГУРАЦИЯ ======
BOT_TOKEN = os.getenv('BOT_TOKEN') or ""
MONITORS_FILE = 'data/active_monitors.json'
CUSTOM_NAMES_FILE = 'data/custom_names.json'
GROUPS_CACHE_FILE = 'data/groups_cache.json'
DB_FILE = 'data/schedules.db'
MODERATOR_IDS = []
mod_ids_env = os.getenv('MODERATOR_ID')
if mod_ids_env:
    for item in mod_ids_env.split(','):
        try:
            MODERATOR_IDS.append(int(item.strip()))
        except ValueError:
            pass
MODERATOR_ID = MODERATOR_IDS[0] if MODERATOR_IDS else None
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID') or 0)

SCHEDULE_CACHE = {}

# Отключаем лишний спам логов в консоль
logger = telebot.logger
telebot.logger.setLevel(logging.CRITICAL)

SPECIAL_CHATS = {
    -1002949492641: 27602,
    -1003018365933: 360
}
special_chats_env = os.getenv('SPECIAL_CHATS')
if special_chats_env:
    SPECIAL_CHATS = {}
    for item in special_chats_env.split(','):
        if ':' in item:
            try:
                chat_id, thread_id = item.split(':')
                SPECIAL_CHATS[int(chat_id.strip())] = int(thread_id.strip())
            except ValueError:
                pass

APPROVED_TEACHER_IDS = []
teacher_ids_env = os.getenv('TEACHER_IDS')
if teacher_ids_env:
    for tid in teacher_ids_env.split(','):
        try:
            APPROVED_TEACHER_IDS.append(int(tid.strip()))
        except ValueError:
            pass

STICKERS = [
    "CAACAgIAAxkBAAIFPWlzJxrefHjYHVfxp1jM4bAH5fCBAAI-EgACHJpIS7jVPGp6rA90OAQ",
    "CAACAgIAAxkBAAIFO2lzJw5KN7Oc318wfDczcH5jXt-LAAIYEAAC9ceoSnqmhExiqppbOAQ",
    "CAACAgIAAxkBAAIFOWlzJuxZZTnMd3fWZy1yiDGTenbCAAKCMwACd7pgSlDQiqr55dnGOAQ",
    "CAACAgIAAxkBAAIFN2lzJueIxjWq--dVhWItMAiuMqhkAAK7awACj_9gSWki-Q5FMhJNOAQ",
    "CAACAgIAAxkBAAIFNWlzJq-fO1LI7FnCUpKvKK0zrY-tAAIqdAACObZ5SkKD23F0xtcMOAQ",
    "CAACAgIAAxkBAAIFM2lzJqWRoOM0ASLL8kXIn0rAJTDaAAKkHwACU3wYSf-GApQlpWnUOAQ",
    "CAACAgIAAxkBAAIFMWlzJpqVDFpiAwFV2m7zECDzQYe8AAI0FQAChHNJSZuYUiJcpZzcOAQ",
    "CAACAgIAAxkBAAIFL2lzJpREknMK5mY-RWYZ4a37DVvXAAJAFwACIND5SB9jZK-Yut4vOAQ",
    "CAACAgIAAxkBAAIFLWlzJpGeyECqq-JDODtv-ewL-XvtAAJ_FwACST_4SJKlVrU6_QE6OAQ"
]

# Фильтры для удаления системного текста (по отделениям)
SYSTEM_FILTERS = {
    1: ["Spearhead", "Разработано", "$cript", "Глорис", "Расписание", "γверсия:"],
    2: ["Spearhead", "Разработано", "$cript", "Глорис", "Расписание", "γверсия:"],
    3: ["Spearhead", "Разработано", "$cript", "Глорис", "Расписание", "γверсия:"]
}

CALLS = [
    ("08:20", "09:05"), ("09:05", "09:50"), ("10:00", "10:45"), ("10:45", "11:30"),
    ("11:35", "12:20"), ("12:25", "13:10"), ("13:15", "14:00"), ("14:00", "14:45"),
    ("14:50", "15:35"), ("15:40", "16:25")
]

# Глобальные переменные для групп (динамические)
GROUP_NAME_TO_ID = {}
GROUP_ID_TO_NAME = {1: {}, 2: {}, 3: {}}

waiting_for_sticker = {}
waiting_for_department = {}   # chat_id -> ожидание ввода отделения
# chat_id -> выбранное отделение (после выбора, ожидание группы)
user_department = {}
waiting_for_teacher_dept = {}   # chat_id -> True (учитель выбирает отделение)
waiting_for_teacher_rooms = {}  # chat_id -> dept (учитель вводит кабинеты)
waiting_for_move = {}  # chat_id -> dict with step, lesson, room, group
# chat_id -> True (ожидание ввода дат для статистики)
waiting_for_stats_dates = {}
stats_context = {}  # chat_id -> dict (текущий контекст просмотра статистики)

system_proxies = urllib.request.getproxies()
if system_proxies:
    from telebot import apihelper
    cast(Any, apihelper).proxy = system_proxies

bot = telebot.TeleBot(BOT_TOKEN)

# ====== ДИНАМИЧЕСКИЙ ПАРСЕР ГРУПП ======


def load_groups_cache():
    global GROUP_NAME_TO_ID
    if os.path.exists(GROUPS_CACHE_FILE):
        try:
            with open(GROUPS_CACHE_FILE, 'r', encoding='utf-8') as f:
                GROUP_NAME_TO_ID = json.load(f)
            build_reverse_group_dict()
        except Exception as e:
            print(f"Error loading groups cache: {e}")


def build_reverse_group_dict():
    global GROUP_ID_TO_NAME
    GROUP_ID_TO_NAME = {1: {}, 2: {}, 3: {}}
    for name, data in GROUP_NAME_TO_ID.items():
        if isinstance(data, list) and len(data) == 2:
            dep, gid = data
            GROUP_ID_TO_NAME[dep][gid] = name


def update_groups_cache():
    global GROUP_NAME_TO_ID
    new_cache = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    for dep in [1, 2, 3]:
        url = f"https://xn----{dep}-iddzneycrmpn.xn--p1ai/lesson_table_show/"
        try:
            r = requests_get_no_proxy(
                url, timeout=10, verify=False, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = str(a['href'])
                    if '?group_id=' in href:
                        try:
                            gid = int(href.split('group_id=')[1].split('&')[0])
                            # Очистка названия группы от markdown-символов
                            # (если есть)
                            gname = a.get_text(
                                strip=True).replace(
                                '*', '').strip()
                            if gname and gname not in [
                                    "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА"]:
                                # Сохраняем как list для JSON
                                new_cache[gname] = [dep, gid]
                        except BaseException:
                            continue
        except Exception as e:
            print(f"Update groups cache failed for dep {dep}: {e}")

    if new_cache:
        GROUP_NAME_TO_ID = new_cache
        build_reverse_group_dict()
        try:
            with open(GROUPS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(new_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save groups cache: {e}")


def background_group_updater():
    while True:
        update_groups_cache()
        time.sleep(3600)  # Обновление списка групп каждый час

# ====== БАЗА ДАННЫХ ======


def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    # Таблица для стикеров
    conn.execute(
        'CREATE TABLE IF NOT EXISTS item_stickers (chat_id INTEGER, item_key TEXT, sticker_id TEXT, PRIMARY KEY (chat_id, item_key))')

    # Таблица для уведомлений
    conn.execute('''CREATE TABLE IF NOT EXISTS user_notifications
                    (chat_id INTEGER, department INTEGER, group_id INTEGER, day INTEGER,
                     last_msg_hash TEXT, PRIMARY KEY (chat_id, department, group_id, day))''')

    # Проверяем таблицу schedules (кэш текущей недели)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'")
    if cursor.fetchone():
        pragma = conn.execute("PRAGMA table_info(schedules)").fetchall()
        columns = [col[1] for col in pragma]
        if 'department' not in columns:
            conn.execute(
                'CREATE TABLE schedules_new (group_id INTEGER, day INTEGER, content_hash TEXT, lessons_text TEXT, department INTEGER, PRIMARY KEY (group_id, day, department))')
            conn.execute(
                'INSERT INTO schedules_new (group_id, day, content_hash, lessons_text, department) SELECT group_id, day, content_hash, lessons_text, 3 FROM schedules')
            conn.execute('DROP TABLE schedules')
            conn.execute('ALTER TABLE schedules_new RENAME TO schedules')
            conn.commit()
    else:
        conn.execute('CREATE TABLE schedules (group_id INTEGER, day INTEGER, content_hash TEXT, lessons_text TEXT, department INTEGER, PRIMARY KEY (group_id, day, department))')
        conn.commit()

    # НОВАЯ ТАБЛИЦА: Исторический архив по датам
    conn.execute('''CREATE TABLE IF NOT EXISTS schedule_history
                    (group_id INTEGER, department INTEGER, date TEXT,
                     content_hash TEXT, lessons_text TEXT,
                     PRIMARY KEY (group_id, department, date))''')
    # Таблица учителей (статус: pending / approved)
    conn.execute('''CREATE TABLE IF NOT EXISTS teachers
                    (chat_id INTEGER PRIMARY KEY, department INTEGER, rooms TEXT,
                     name TEXT, status TEXT DEFAULT 'pending')''')
    conn.execute('''CREATE TABLE IF NOT EXISTS teacher_room_overrides
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     teacher_chat_id INTEGER,
                     department INTEGER,
                     day INTEGER,
                     slot_idx INTEGER,
                     group_id INTEGER,
                     new_room TEXT,
                     new_subject TEXT,
                     notified INTEGER DEFAULT 0,
                     notify_after REAL,
                     date TEXT)''')
    # Пользовательские настройки (для /settings)
    conn.execute('''CREATE TABLE IF NOT EXISTS user_settings
                    (chat_id INTEGER PRIMARY KEY, notifications INTEGER DEFAULT 1, voice_alerts INTEGER DEFAULT 0)''')
    try:
        conn.execute(
            "ALTER TABLE user_settings ADD COLUMN fluffy_mode INTEGER DEFAULT 0")
    except BaseException:
        pass
    try:
        conn.execute(
            "ALTER TABLE user_settings ADD COLUMN voice_effect TEXT DEFAULT 'echo'")
    except BaseException:
        pass
    try:
        conn.execute(
            "ALTER TABLE teacher_room_overrides ADD COLUMN date TEXT")
    except BaseException:
        pass
    conn.commit()
    conn.close()


def save_item_sticker(chat_id, item_name, sticker_id):
    clean_name = re.sub(r'\(?\d{2,4}[А-Яа-я]?\)?', '', item_name).strip()
    key = re.sub(r'[^а-яА-Яa-zA-ZёЁ]', '', clean_name).lower()
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR REPLACE INTO item_stickers VALUES (?, ?, ?)",
        (chat_id,
         key,
         sticker_id))
    conn.commit()
    conn.close()


def get_item_sticker(chat_id, raw_item_name):
    if not raw_item_name:
        return None
    clean_name = re.sub(r'\(?\d{2,4}[А-Яа-я]?\)?', '', raw_item_name).strip()
    key = re.sub(r'[^а-яА-Яa-zA-ZёЁ]', '', clean_name).lower()
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute(
        "SELECT sticker_id FROM item_stickers WHERE chat_id=? AND item_key=?",
        (chat_id,
         key)).fetchone()
    conn.close()
    return res[0] if res else None


def save_schedule_to_db(department, group_id, day,
                        content_hash, lessons_json, date_str):
    try:
        conn = sqlite3.connect(DB_FILE)
        # Сохранение в быстрый кэш текущей недели
        conn.execute("INSERT OR REPLACE INTO schedules (group_id, day, content_hash, lessons_text, department) VALUES (?, ?, ?, ?, ?)",
                     (group_id, day, content_hash, lessons_json, department))
        # Сохранение в архив с привязкой к конкретной дате (YYYY-MM-DD)
        conn.execute("INSERT OR REPLACE INTO schedule_history (group_id, department, date, content_hash, lessons_text) VALUES (?, ?, ?, ?, ?)",
                     (group_id, department, date_str, content_hash, lessons_json))
        conn.commit()
        conn.close()
        SCHEDULE_CACHE.clear()
    except Exception as e:
        logger.error(f"Error saving schedule: {e}")


def get_all_schedules_for_day(day):
    if day in SCHEDULE_CACHE:
        return SCHEDULE_CACHE[day]
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute(
            "SELECT department, group_id, lessons_text FROM schedules WHERE day=?",
            (day,
             )).fetchall()
        conn.close()
        data = {}
        for dep, gid, lessons_json in rows:
            try:
                lessons = json.loads(lessons_json)
                data[(dep, gid)] = lessons
            except BaseException:
                continue
        SCHEDULE_CACHE[day] = data
        return data
    except Exception as e:
        logger.error(f"Error getting schedules: {e}")
        return {}


def get_schedule_history_for_date(date_str):
    """Извлекает расписание всех групп за конкретную дату YYYY-MM-DD"""
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute(
            "SELECT department, group_id, lessons_text FROM schedule_history WHERE date=?",
            (date_str,
             )).fetchall()
        conn.close()
        data = {}
        for dep, gid, lessons_json in rows:
            try:
                data[(dep, gid)] = json.loads(lessons_json)
            except BaseException:
                continue
        return data
    except Exception:
        return {}


def get_date_for_weekday(day_num):
    """Возвращает строку YYYY-MM-DD для указанного дня (1-7) текущей недели."""
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    target_date = start_of_week + timedelta(days=day_num - 1)
    return target_date.strftime("%Y-%m-%d")


def extract_room(lesson_text):
    """Извлекает содержимое между первой '(' и последней ')' (включая внутренние скобки)."""
    if not lesson_text:
        return None
    first_open = lesson_text.find('(')
    if first_open == -1:
        return None
    last_close = lesson_text.rfind(')')
    if last_close == -1 or last_close < first_open:
        return None
    return lesson_text[first_open + 1:last_close].strip()


# ====== АНАЛИТИКА И ГРАФИКИ ======

def parse_date_range(text):
    """Парсит даты в формате ДД.ММ.ГГГГ - ДД.ММ.ГГГГ или одну дату."""
    if not text:
        return None, None
    matches = re.findall(r'(\d{2})\.(\d{2})\.(\d{4})', text)
    if not matches:
        return None, None

    dates = []
    for d, m, y in matches:
        try:
            dt = datetime(int(y), int(m), int(d))
            dates.append(dt.strftime('%Y-%m-%d'))
        except ValueError:
            continue

    if len(dates) == 1:
        return dates[0], dates[0]
    elif len(dates) >= 2:
        d1, d2 = dates[0], dates[1]
        if d1 > d2:
            return d2, d1
        return d1, d2
    return None, None


def apply_chart_style():
    """Применяет темную тему для графиков Matplotlib."""
    plt.style.use('dark_background')
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans',
                                       'Segoe UI', 'Arial', 'sans-serif']
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['figure.facecolor'] = '#181825'
    plt.rcParams['axes.facecolor'] = '#1e1e2e'
    plt.rcParams['axes.edgecolor'] = '#45475a'
    plt.rcParams['axes.labelcolor'] = '#cdd6f4'
    plt.rcParams['xtick.color'] = '#bac2de'
    plt.rcParams['ytick.color'] = '#bac2de'
    plt.rcParams['grid.color'] = '#313244'
    plt.rcParams['text.color'] = '#cdd6f4'


def generate_group_subject_chart(
        group_id, department, group_name, start_date=None, end_date=None, chat_id=None):
    """Генерирует круговую/столбчатую диаграмму предметов для группы."""
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT lessons_text FROM schedule_history WHERE group_id = ? AND department = ?"
    params = [group_id, department]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    subject_counts = collections.Counter()
    for (lessons_json,) in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
        for lesson in lessons:
            l_str = str(lesson).strip()
            if not l_str or l_str.lower() == "обед" or l_str in [
                    "—", "о", "О", "x", "X", "."]:
                continue

            if chat_id:
                applied = custom_names_manager.apply(chat_id, l_str)
                if not applied:
                    continue
                l_str = applied

            subj = re.sub(r'\s*\(.*$', '', l_str).strip()
            if subj:
                subject_counts[subj] += 1

    if not subject_counts:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    sorted_data = sorted(subject_counts.items(), key=lambda x: x[1])
    subjects = [x[0] for x in sorted_data]
    counts = [x[1] for x in sorted_data]

    colors = [
        '#89b4fa',
        '#b4befe',
        '#cba6f7',
        '#f5c2e7',
        '#a6e3a1',
        '#f9e2af',
        '#fab387',
        '#f38ba8']
    bar_colors = [colors[i % len(colors)] for i in range(len(subjects))]

    bars = ax.barh(
        subjects,
        counts,
        color=bar_colors,
        edgecolor='#1e1e2e',
        height=0.6)

    for bar in bars:
        width = bar.get_width()
        pairs = width / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f'{int(width)}ч{pairs_str}',
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    ax.set_title(
        f"Распределение часов по предметам{date_range_str}\nГруппа: {group_name}",
        fontsize=12,
        pad=15,
        fontweight='bold')
    ax.set_xlabel("Академические часы (пара = 2 ч)", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def generate_group_daily_chart(
        group_id, department, group_name, start_date=None, end_date=None):
    """Генерирует график нагрузки группы по дням."""
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT date, lessons_text FROM schedule_history WHERE group_id = ? AND department = ?"
    params = [group_id, department]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    daily_stats = {}
    for date_str, lessons_json in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
        hours = sum(1 for l in lessons if str(l).strip() and str(l).strip().lower(
        ) != "обед" and str(l).strip() not in ["—", "о", "О", "x", "X", "."])
        parts = date_str.split('-')
        formatted_date = f"{parts[2]}.{parts[1]}"
        daily_stats[formatted_date] = hours

    if not daily_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    dates = list(daily_stats.keys())
    counts = list(daily_stats.values())

    bars = ax.bar(
        dates,
        counts,
        color='#94e2d5',
        edgecolor='#1e1e2e',
        width=0.4 if len(dates) > 1 else 0.2)

    for bar in bars:
        height = bar.get_height()
        pairs = height / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.1, f'{int(height)}ч{pairs_str}',
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    ax.set_title(
        f"Учебная нагрузка по дням{date_range_str}\nГруппа: {group_name}",
        fontsize=12,
        pad=15,
        fontweight='bold')
    ax.set_ylabel("Академические часы", labelpad=10)
    ax.set_ylim(0, max(counts) + 2 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def get_teacher_aggregated_data(
        teacher_rooms, department, start_date=None, end_date=None, chat_id=None):
    """Стягивает агрегированные данные по кабинетам преподавателя."""
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT date, group_id, lessons_text FROM schedule_history WHERE department = ?"
    params = [department]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    teacher_active_slots_by_date = collections.defaultdict(set)
    hours_by_group = collections.Counter()
    hours_by_subject = collections.Counter()

    for date_str, group_id, lessons_json in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue

        group_name = GROUP_ID_TO_NAME.get(
            department, {}).get(
            group_id, f"Гр. {group_id}")

        for idx, lesson in enumerate(lessons):
            l_str = str(lesson).strip()
            if not l_str or l_str.lower() == "обед" or l_str in [
                    "—", "о", "О", "x", "X", "."]:
                continue

            room = extract_room(l_str)
            if room and any(r.strip() in room for r in teacher_rooms):
                teacher_active_slots_by_date[date_str].add(idx)

                subj = re.sub(r'\s*\(.*$', '', l_str).strip()
                if chat_id:
                    applied = custom_names_manager.apply(chat_id, l_str)
                    if applied:
                        subj = re.sub(r'\s*\(.*$', '', applied).strip()

                hours_by_group[group_name] += 1
                hours_by_subject[subj] += 1

    hours_by_date = {d: len(slots)
                     for d, slots in teacher_active_slots_by_date.items()}
    sorted_hours_by_date = dict(sorted(hours_by_date.items()))

    return {
        "daily": sorted_hours_by_date,
        "groups": dict(hours_by_group),
        "subjects": dict(hours_by_subject)
    }


def generate_teacher_daily_chart(
        teacher_name, teacher_rooms, department, start_date=None, end_date=None):
    """Генерирует график нагрузки преподавателя по дням."""
    data = get_teacher_aggregated_data(
        teacher_rooms, department, start_date, end_date)
    daily_stats = data["daily"]
    if not daily_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    dates = []
    for d in daily_stats.keys():
        parts = d.split('-')
        dates.append(f"{parts[2]}.{parts[1]}")
    counts = list(daily_stats.values())

    bars = ax.bar(
        dates,
        counts,
        color='#fab387',
        edgecolor='#1e1e2e',
        width=0.4 if len(dates) > 1 else 0.2)

    for bar in bars:
        height = bar.get_height()
        pairs = height / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.1, f'{int(height)}ч{pairs_str}',
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(
        f"Преподаватель: {teacher_name} (каб. {rooms_str})\nУчебные часы по дням{date_range_str}",
        fontsize=11,
        pad=15,
        fontweight='bold')
    ax.set_ylabel("Академические часы", labelpad=10)
    ax.set_ylim(0, max(counts) + 2 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def generate_teacher_groups_chart(
        teacher_name, teacher_rooms, department, start_date=None, end_date=None):
    """Генерирует график нагрузки преподавателя по учебным группам."""
    data = get_teacher_aggregated_data(
        teacher_rooms, department, start_date, end_date)
    group_stats = data["groups"]
    if not group_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    sorted_data = sorted(group_stats.items(), key=lambda x: x[1])
    groups = [x[0] for x in sorted_data]
    counts = [x[1] for x in sorted_data]

    colors = [
        '#a6e3a1',
        '#94e2d5',
        '#89b4fa',
        '#b4befe',
        '#cba6f7',
        '#f5c2e7',
        '#fab387',
        '#f38ba8']
    bar_colors = [colors[i % len(colors)] for i in range(len(groups))]

    bars = ax.barh(
        groups,
        counts,
        color=bar_colors,
        edgecolor='#1e1e2e',
        height=0.6)

    for bar in bars:
        width = bar.get_width()
        pairs = width / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f'{int(width)}ч{pairs_str}',
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(
        f"Преподаватель: {teacher_name} (каб. {rooms_str})\nРаспределение часов по группам{date_range_str}",
        fontsize=11,
        pad=15,
        fontweight='bold')
    ax.set_xlabel("Академические часы", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def generate_teacher_subjects_chart(
        teacher_name, teacher_rooms, department, start_date=None, end_date=None, chat_id=None):
    """Генерирует график распределения предметов у преподавателя."""
    data = get_teacher_aggregated_data(
        teacher_rooms, department, start_date, end_date, chat_id)
    subject_stats = data["subjects"]
    if not subject_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    sorted_data = sorted(subject_stats.items(), key=lambda x: x[1])
    subjects = [x[0] for x in sorted_data]
    counts = [x[1] for x in sorted_data]

    colors = [
        '#89b4fa',
        '#b4befe',
        '#cba6f7',
        '#f5c2e7',
        '#a6e3a1',
        '#f9e2af',
        '#fab387',
        '#f38ba8']
    bar_colors = [colors[i % len(colors)] for i in range(len(subjects))]

    bars = ax.barh(
        subjects,
        counts,
        color=bar_colors,
        edgecolor='#1e1e2e',
        height=0.6)

    for bar in bars:
        width = bar.get_width()
        pairs = width / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f'{int(width)}ч{pairs_str}',
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(
        f"Преподаватель: {teacher_name} (каб. {rooms_str})\nНагрузка по предметам{date_range_str}",
        fontsize=11,
        pad=15,
        fontweight='bold')
    ax.set_xlabel("Академические часы", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def get_time_distribution_stats(
        department=None, start_date=None, end_date=None):
    """Считает общую статистику занятости пар по слотам."""
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT lessons_text FROM schedule_history"
    conditions = []
    params = []
    if department is not None:
        conditions.append("department = ?")
        params.append(department)
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    slot_counts = [0] * 10
    for (lessons_json,) in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
        for idx in range(min(len(lessons), 10)):
            l_str = str(lessons[idx]).strip()
            if not l_str or l_str.lower() == "обед" or l_str in [
                    "—", "о", "О", "x", "X", "."]:
                continue
            slot_counts[idx] += 1

    return slot_counts


def generate_time_distribution_chart(
        department=None, start_date=None, end_date=None):
    """Генерирует график распределения занятий по времени (номерам пар)."""
    slot_counts = get_time_distribution_stats(department, start_date, end_date)
    if sum(slot_counts) == 0:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    slots = [f"{i+1} пара\n({CALLS[i][0]})" for i in range(len(slot_counts))]
    counts = slot_counts

    bars = ax.bar(
        slots,
        counts,
        color='#b4befe',
        edgecolor='#1e1e2e',
        width=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.1, f'{int(height)}',
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    dep_str = f" | Отделение {department}" if department is not None else ""
    ax.set_title(
        f"Распределение занятий по времени (парам){date_range_str}{dep_str}\n(Загруженность расписания)",
        fontsize=11,
        pad=15,
        fontweight='bold')
    ax.set_ylabel("Количество проведенных часов (слотов)", labelpad=10)
    ax.set_ylim(0, max(counts) + max(counts) * 0.15 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.xticks(rotation=15)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


# ====== МЕНЕДЖЕРЫ ======
class MonitorManager:
    def __init__(self):
        self.active_monitors = {}
        self.load()

    def load(self):
        if os.path.exists(MONITORS_FILE):
            try:
                with open(MONITORS_FILE, 'r', encoding='utf-8') as f:
                    self.active_monitors = json.load(f)
                # Добавляем department=3 для старых записей
                for key, value in self.active_monitors.items():
                    if 'department' not in value:
                        value['department'] = 3
            except BaseException:
                self.active_monitors = {}

    def save(self):
        with open(MONITORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.active_monitors, f, ensure_ascii=False, indent=2)

    def get_user_monitors(self, chat_id):
        return [m for m in self.active_monitors.values() if str(
            m["chat_id"]) == str(chat_id)]


class CustomNamesManager:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(CUSTOM_NAMES_FILE):
            try:
                with open(CUSTOM_NAMES_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except BaseException:
                self.data = {}

    def save(self):
        with open(CUSTOM_NAMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def set_name(self, cid, old, new):
        cid = str(cid)
        if cid not in self.data:
            self.data[cid] = {}
        key = re.sub(r'[^а-яА-Яa-zA-ZёЁ]', '', old).lower()
        if key:
            self.data[cid][key] = str(new).strip()
            self.save()

    def apply(self, cid, text):
        if not text or not isinstance(text, str):
            return text
        if any(x in text for x in [
               "Spearhead", "Разработано", "$cript", "Глорис", "Расписание"]):
            return None
        cid = str(cid)
        room_match = re.search(r'(\s*\(?\d{2,4}[А-Яа-я]?\)?)$', text)
        room = room_match.group(1) if room_match else ""
        clean = re.sub(
            r'[^а-яА-Яa-zA-ZёЁ]',
            '',
            text.replace(
                room,
                "")).lower()
        if cid in self.data:
            for k, v in self.data[cid].items():
                if k in clean:
                    return f"{v}{room}"
        return text


monitor_manager = MonitorManager()
custom_names_manager = CustomNamesManager()

# ====== УЧИТЕЛЬСКИЙ РЕЖИМ ======


def is_teacher(chat_id):
    """Проверяет, одобрен ли пользователь как учитель."""
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute(
        "SELECT status FROM teachers WHERE chat_id=?", (chat_id,)).fetchone()
    if res:
        status = res[0]
        if status == 'approved':
            conn.close()
            return True
        if chat_id in APPROVED_TEACHER_IDS:
            conn.execute(
                "UPDATE teachers SET status='approved' WHERE chat_id=?", (chat_id,))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False


def get_teacher_info(chat_id):
    """Возвращает (department, rooms_list) для одобренного учителя."""
    conn = sqlite3.connect(DB_FILE)
    res = conn.execute(
        "SELECT department, rooms FROM teachers WHERE chat_id=? AND status='approved'",
        (chat_id,
         )).fetchone()
    conn.close()
    if res:
        return res[0], json.loads(res[1])
    return None, []


def get_teacher_schedule(chat_id, day, all_data):
    """Собирает расписание учителя по его кабинетам из данных всех групп."""
    dept, rooms = get_teacher_info(chat_id)
    if not rooms or dept is None:
        return None, [], []
    max_slots = 10 if day == 1 else 8
    schedule = [[] for _ in range(max_slots)]
    for (dep, gid), lessons in all_data.items():
        if dep != dept:
            continue
        group_name = GROUP_ID_TO_NAME.get(dep, {}).get(gid, "?")
        for idx in range(min(len(lessons), max_slots)):
            l_str = str(lessons[idx])
            room = extract_room(l_str)
            if room and any(r.strip() in room for r in rooms):
                subj = re.sub(r'\s*\(.*$', '', l_str).strip()
                schedule[idx].append((group_name, subj, room))

    # Добавляем обед для свободных слотов
    for idx in range(max_slots):
        if not schedule[idx]:
            has_lunch = False
            for (dep, gid), lessons in all_data.items():
                if dep == dept:
                    if idx < len(lessons) and "обед" in str(
                            lessons[idx]).lower():
                        has_lunch = True
                        break
            if has_lunch:
                schedule[idx].append(("", "ОБЕД", ""))

    return dept, rooms, schedule


def format_teacher_schedule(rooms, schedule, day):
    """Форматирует расписание учителя в строку."""
    max_slots = 10 if day == 1 else 8
    res_lines = []
    has_lessons = False
    for i in range(max_slots):
        slot = schedule[i] if i < len(schedule) else []
        if slot:
            has_lessons = True
            subj_groups = {}
            for gname, subj, room in slot:
                key = (subj, room)
                if key not in subj_groups:
                    subj_groups[key] = []
                subj_groups[key].append(gname)
            for (subj, room), groups in subj_groups.items():
                if subj == "ОБЕД":
                    res_lines.append(f"{i+1}. ОБЕД")
                else:
                    room_str = f" (каб.{room})" if room else ""
                    res_lines.append(f"{i+1}. {subj}{room_str}")
                    groups_clean = [g for g in groups if g]
                    if groups_clean:
                        res_lines.append(
                            f"   {', '.join(sorted(groups_clean))}")
    if not has_lessons:
        res_lines.append("Нет пар в ваших кабинетах.")
    return "\n".join(res_lines)


def cmd_teacher_r(message, day=None, label=None):
    """Выводит расписание учителя на указанный день."""
    if day is None:
        day = datetime.now().isoweekday()
    # Оригинальные данные — для определения, какие слоты принадлежат учителю
    original_data = get_all_schedules_for_day(day)
    # Данные с заменами — для отображения актуального состояния
    overridden_data = apply_teacher_overrides(original_data, day)

    dept, rooms = get_teacher_info(message.chat.id)
    if not rooms or dept is None:
        return reply_safe(message, "❌ Нет данных. Зарегистрируйтесь: /start")

    # Определяем слоты учителя по ОРИГИНАЛЬНЫМ данным (до замен)
    max_slots = 10 if day == 1 else 8
    schedule = [[] for _ in range(max_slots)]
    for (dep, gid), lessons in original_data.items():
        if dep != dept:
            continue
        group_name = GROUP_ID_TO_NAME.get(dep, {}).get(gid, "?")
        for idx in range(min(len(lessons), max_slots)):
            l_str = str(lessons[idx])
            room = extract_room(l_str)
            if room and any(r.strip() in room for r in rooms):
                # Слот принадлежит учителю — берём АКТУАЛЬНЫЕ данные с заменами
                overridden_lessons = overridden_data.get((dep, gid))
                if overridden_lessons is None:
                    overridden_lessons = lessons
                if idx < len(overridden_lessons):
                    o_str = str(overridden_lessons[idx])
                    o_room = extract_room(o_str) or room
                    o_subj = re.sub(r'\s*\(.*$', '', o_str).strip()
                else:
                    o_room = room
                    o_subj = re.sub(r'\s*\(.*$', '', l_str).strip()
                schedule[idx].append((group_name, o_subj, o_room))

    # Добавляем обед для свободных слотов
    for idx in range(max_slots):
        if not schedule[idx]:
            has_lunch = False
            for (dep, gid), lessons in overridden_data.items():
                if dep == dept:
                    if idx < len(lessons) and "обед" in str(
                            lessons[idx]).lower():
                        has_lunch = True
                        break
            if has_lunch:
                schedule[idx].append(("", "ОБЕД", ""))

    rooms_str = ', '.join(rooms)
    if label is None:
        day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда",
                     4: "Четверг", 5: "Пятница", 6: "Суббота"}
        label = day_names.get(day, "?")
    header = f"📅 {label} | каб. {rooms_str}"
    body = format_teacher_schedule(rooms, schedule, day)
    reply_safe(message, wrap_code(f"{header}\n\n{body}"))


def cmd_teacher_db(message):
    """Роутер /db для учителя."""
    args = message.text.replace('/db', '').strip().lower()
    day_map = {'пн': 1, 'вт': 2, 'ср': 3, 'чт': 4, 'пт': 5, 'сб': 6}
    day_labels = {1: "ПН", 2: "ВТ", 3: "СР", 4: "ЧТ", 5: "ПТ", 6: "СБ"}
    _, rooms = get_teacher_info(message.chat.id)
    rooms_str = ', '.join(rooms) if rooms else '?'

    # Конкретная дата /db 16.06.2026
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', args):
        try:
            target_date = datetime.strptime(
                args, "%d.%m.%Y").strftime("%Y-%m-%d")
            all_data = get_schedule_history_for_date(target_date)
            target_weekday = datetime.strptime(args, "%d.%m.%Y").isoweekday()
            if all_data:
                all_data = apply_teacher_overrides(all_data, target_weekday)
            if not all_data:
                return reply_safe(message, wrap_code(
                    f"🗄 Нет данных в архиве за {args}"))
            target_weekday = datetime.strptime(args, "%d.%m.%Y").isoweekday()
            dept, rooms, schedule = get_teacher_schedule(
                message.chat.id, target_weekday, all_data)
            body = format_teacher_schedule(rooms, schedule, target_weekday)
            return reply_safe(message, wrap_code(
                f"🗄 Архив ({args}) | каб. {rooms_str}\n\n{body}"))
        except ValueError:
            return reply_safe(message, wrap_code(
                "Неверный формат даты. Используйте ДД.ММ.ГГГГ"))

    # День недели /db пн
    if args in day_map:
        target_day = day_map[args]
        all_data = get_all_schedules_for_day(target_day)
        all_data = apply_teacher_overrides(all_data, target_day)
        dept, rooms, schedule = get_teacher_schedule(
            message.chat.id, target_day, all_data)
        body = format_teacher_schedule(rooms, schedule, target_day)
        return reply_safe(message, wrap_code(
            f"🗓 {day_labels[target_day]} | каб. {rooms_str}\n\n{body}"))

    # Классический /db (завтра)
    curr_day = datetime.now().isoweekday()
    next_day = 1 if curr_day >= 5 else curr_day + 1
    all_data = get_all_schedules_for_day(next_day)
    all_data = apply_teacher_overrides(all_data, next_day)
    dept, rooms, schedule = get_teacher_schedule(
        message.chat.id, next_day, all_data)
    body = format_teacher_schedule(rooms, schedule, next_day)
    reply_safe(message, wrap_code(
        f"📦 {day_labels[next_day]} | каб. {rooms_str}\n\n{body}"))


def cmd_teacher_now(message):
    """Показывает текущий урок учителя."""
    status, _, idx = get_status()
    if status == "rest" or idx is None:
        return reply_safe(message, wrap_code(
            "Отдыхай\n(Используй /db)") + "\n\n/db")
    day = datetime.now().isoweekday()
    all_data = get_all_schedules_for_day(day)
    all_data = apply_teacher_overrides(all_data, day)
    dept, rooms, schedule = get_teacher_schedule(
        message.chat.id, day, all_data)
    slot = schedule[idx] if schedule and idx < len(schedule) else []
    if not slot:
        return reply_safe(message, wrap_code(
            "Сейчас окно (нет пар в ваших кабинетах)"))
    start_t = CALLS[idx][0]
    end_t = CALLS[idx][1]
    now_str = datetime.now().strftime("%H:%M")
    curr_dt = datetime.strptime(now_str, "%H:%M")
    end_dt = datetime.strptime(end_t, "%H:%M")
    total_sec = (end_dt - datetime.strptime(start_t, "%H:%M")).seconds
    elapsed_sec = max(
        0,
        (curr_dt -
         datetime.strptime(
             start_t,
             "%H:%M")).seconds)
    percent = min(100, max(0, (elapsed_sec / total_sec) * 100)
                  ) if total_sec else 0
    bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
    td = end_dt - curr_dt
    h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
    rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
    lines = []
    for gname, subj, room in slot:
        if subj == "ОБЕД":
            lines.append("ОБЕД")
        else:
            lines.append(f"{subj} (каб.{room})\n   {gname}")
    res = "\n".join(lines) + f"\n{bar} {int(percent)}%\nДо конца пары: {rem}"
    reply_safe(message, wrap_code(res))


def cmd_teacher_next(message):
    """Показывает следующий урок учителя."""
    day = datetime.now().isoweekday()
    all_data = get_all_schedules_for_day(day)
    all_data = apply_teacher_overrides(all_data, day)
    dept, rooms, schedule = get_teacher_schedule(
        message.chat.id, day, all_data)
    status, _, idx = get_status()
    start_from = (idx + 1) if idx is not None else 0
    next_slot = None
    next_idx = None
    for i in range(start_from, len(schedule)):
        if schedule[i]:
            next_slot = schedule[i]
            next_idx = i
            break
    if not next_slot or next_idx is None or next_idx >= len(CALLS):
        return reply_safe(message, wrap_code("Пар больше нет") + "\n\n/db")
    now_str = datetime.now().strftime("%H:%M")
    start_t = CALLS[next_idx][0]
    td = datetime.strptime(start_t, "%H:%M") - \
        datetime.strptime(now_str, "%H:%M")
    h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
    rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
    lines = []
    for gname, subj, room in next_slot:
        if subj == "ОБЕД":
            lines.append("ОБЕД")
        else:
            lines.append(f"{subj} (каб.{room})\n   {gname}")
    res = "Далее:\n" + "\n".join(lines) + f"\nЧерез: {rem}"
    reply_safe(message, wrap_code(res))

# ====== ЗАМЕНЫ УЧИТЕЛЯ (OVERRIDES) ======


def apply_teacher_overrides(all_data, day, date_str=None):
    """Применяет замены учителя (кабинет/предмет) к данным расписания поверх сайта."""
    conn = sqlite3.connect(DB_FILE)
    if date_str:
        rows = conn.execute(
            "SELECT slot_idx, group_id, department, new_room, new_subject FROM teacher_room_overrides WHERE day=? AND (date IS NULL OR date='' OR date=?)",
            (day, date_str)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT slot_idx, group_id, department, new_room, new_subject FROM teacher_room_overrides WHERE day=? AND (date IS NULL OR date='')",
            (day,)
        ).fetchall()
    conn.close()
    if not rows:
        return all_data
    # {(dep, slot_idx, group_id): (new_room, new_subject)}
    omap = {}
    for slot_idx, group_id, dep, new_room, new_subject in rows:
        omap[(dep, slot_idx, group_id)] = (new_room, new_subject)
    result = dict(all_data)
    for (dep, gid), lessons in all_data.items():
        new_lessons = list(lessons)
        changed = False
        for i, lesson in enumerate(lessons):
            ls = str(lesson).strip()
            override = omap.get((dep, i, gid)) or omap.get((dep, i, -1))
            if not override:
                continue
            new_room, new_subject = override
            if new_room:
                if re.search(r'\([^)]+\)$', ls):
                    ls = re.sub(r'\([^)]+\)$', f'({new_room})', ls)
                else:
                    ls = ls + f' ({new_room})'
            if new_subject:
                if '(' in ls:
                    room_part = ls[ls.rfind('('):]
                    ls = f'{new_subject} {room_part}'
                else:
                    ls = new_subject
            new_lessons[i] = ls
            changed = True
        if changed:
            result[(dep, gid)] = new_lessons
    return result


def save_teacher_override(teacher_chat_id, department,
                          day, slot_idx, group_id, new_room, new_subject, date_str=None):
    """Сохраняет или обновляет замену учителя. Сбрасывает notify_after на now+5min."""
    notify_after = time.time() + 300  # 5 минут
    conn = sqlite3.connect(DB_FILE)
    if date_str:
        existing = conn.execute(
            "SELECT id FROM teacher_room_overrides WHERE teacher_chat_id=? AND day=? AND slot_idx=? AND group_id=? AND date=? AND notified=0",
            (teacher_chat_id, day, slot_idx, group_id, date_str)
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id FROM teacher_room_overrides WHERE teacher_chat_id=? AND day=? AND slot_idx=? AND group_id=? AND (date IS NULL OR date='') AND notified=0",
            (teacher_chat_id, day, slot_idx, group_id)
        ).fetchone()
        
    if existing:
        if date_str:
            conn.execute(
                "UPDATE teacher_room_overrides SET new_room=?, new_subject=?, department=?, notify_after=?, date=? WHERE id=?",
                (new_room, new_subject, department, notify_after, date_str, existing[0])
            )
        else:
            conn.execute(
                "UPDATE teacher_room_overrides SET new_room=?, new_subject=?, department=?, notify_after=? WHERE id=?",
                (new_room, new_subject, department, notify_after, existing[0])
            )
    else:
        conn.execute(
            "INSERT INTO teacher_room_overrides (teacher_chat_id, department, day, slot_idx, group_id, new_room, new_subject, notified, notify_after, date) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (teacher_chat_id, department, day, slot_idx,
             group_id, new_room, new_subject, notify_after, date_str)
        )
    conn.commit()
    conn.close()


def send_teacher_override_notifications_for_day(day):
    """Отправляет ученикам батч-уведомление об изменениях учителя (один раз на чат)."""
    now = time.time()
    conn = sqlite3.connect(DB_FILE)
    pending = conn.execute(
        "SELECT id, department, slot_idx, group_id, new_room, new_subject FROM teacher_room_overrides "
        "WHERE notified=0 AND notify_after <= ? AND day=?",
        (now, day)
    ).fetchall()
    if not pending:
        conn.close()
        return
    # Собираем: {(dep, gid) -> [(slot_idx, new_room, new_subject)]}
    affected = {}
    notified_ids = []
    all_data = get_all_schedules_for_day(day)
    for row_id, dep, slot_idx, group_id, new_room, new_subject in pending:
        notified_ids.append(row_id)
        if group_id == -1:
            for (d, gid) in all_data:
                if d == dep:
                    affected.setdefault(
                        (dep, gid), []).append(
                        (slot_idx, new_room, new_subject))
        else:
            affected.setdefault(
                (dep, group_id), []).append(
                (slot_idx, new_room, new_subject))
    day_of_week = {1: "понедельник", 2: "вторник", 3: "среда",
                   4: "четверг", 5: "пятница", 6: "суббота"}.get(day, "?")
    # Отправляем по одному сообщению на чат
    for m in monitor_manager.active_monitors.values():
        dep = m['department']
        gid = m['group_id']
        key = (dep, gid)
        if key not in affected:
            continue
        changes = sorted(affected[key], key=lambda x: x[0])
        lessons = all_data.get(key, [])
        lines = [f"🔄 Замена\n{m['group_name']} | {day_of_week}\n"]
        for slot_idx, new_room, new_subject in changes:
            orig = str(lessons[slot_idx]) if slot_idx < len(lessons) else "?"
            orig_subj = re.sub(r'\s*\(.*$', '', orig).strip()
            orig_room = extract_room(orig) or "?"
            parts = []
            if new_subject:
                parts.append(f"{orig_subj} → {new_subject}")
            if new_room:
                parts.append(f"каб. {orig_room} → {new_room}")
            lines.append(
                f"{slot_idx + 1}. {' | '.join(parts) if parts else orig_subj}")
        msg = "\n".join(lines)
        try:
            thread_id = m.get(
                'message_thread_id') or SPECIAL_CHATS.get(m['chat_id'])
            bot.send_message(m['chat_id'], wrap_code(msg), parse_mode='Markdown',
                             message_thread_id=thread_id)
        except Exception as e:
            print(f"Override notify error: {e}")
    # Помечаем как отправленные
    for row_id in notified_ids:
        conn.execute(
            "UPDATE teacher_room_overrides SET notified=1 WHERE id=?", (row_id,))
    conn.commit()
    conn.close()


def teacher_notification_loop():
    """Фоновый поток: каждую минуту ищет готовые к отправке уведомления об изменениях учителя."""
    while True:
        try:
            now = time.time()
            conn = sqlite3.connect(DB_FILE)
            pending_days = conn.execute(
                "SELECT DISTINCT day FROM teacher_room_overrides WHERE notified=0 AND notify_after <= ?",
                (now,)
            ).fetchall()
            conn.close()
            for (d,) in pending_days:
                send_teacher_override_notifications_for_day(d)
        except Exception as e:
            print(f"Teacher notify loop error: {e}")
        time.sleep(60)


def wrap_code(text):
    """Оборачивает текст в блок кода, заменяя пробелы на ㅤ только в первой строке."""
    if not text:
        return "```...```"
    lines = text.split('\n')
    lines[0] = lines[0].replace(" ", "ㅤ")
    joined = '\n'.join(lines)
    return f"```{joined}```"

# ====== ВСПОМОГАТЕЛЬНЫЕ ======


def send_random_sticker(message, force=False):
    pass  # Стикеры отключены


def fetch_lessons(day, group_id, department):
    try:
        v = random.randint(1, 999999)
        url = f"https://xn----{department}-iddzneycrmpn.xn--p1ai/lesson_table_show/?day={day}&group_id={group_id}&v={v}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests_get_no_proxy(
            url, timeout=15, verify=False, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        lessons = [
            p.get_text(
                strip=True) for p in soup.find_all("p") if len(
                p.get_text(
                    strip=True)) > 1]
        filters = SYSTEM_FILTERS.get(department, SYSTEM_FILTERS[3])
        return [l for l in lessons if not any(x in l for x in filters)]
    except Exception as e:
        print(f"Error fetching lessons: {e}")
        return None


def get_status():
    now = datetime.now()
    curr = now.strftime("%H:%M")
    wd = now.isoweekday()
    if wd > 5:
        return "rest", None, None
    max_l = 10 if wd == 1 else 8
    last_call = CALLS[max_l - 1][1]
    if curr >= last_call:
        return "rest", None, None
    td = datetime.strptime(last_call, "%H:%M") - \
        datetime.strptime(curr, "%H:%M")
    h, m = td.seconds // 3600, (td.seconds // 60) % 60
    t_str = f"{f'{h}ч ' if h > 0 else ''}{m}м"
    active_idx = next((i for i, c in enumerate(
        CALLS[:max_l]) if c[0] <= curr <= c[1]), None)
    return "work", t_str, active_idx


def format_with_overlap(cid, department, gid, day,
                        idx, raw_text, all_day_data):
    if not raw_text or raw_text == "Кл/час":
        return [custom_names_manager.apply(cid, raw_text) or "Кл/час"]
    base_name = custom_names_manager.apply(cid, raw_text)
    if not base_name:
        return []
    room = extract_room(raw_text)
    if not room:
        return [base_name]
    clean_subject = re.sub(r'\s*\(.*$', '', base_name).strip()
    results = [f"{clean_subject} ({room})"]
    overlaps = []
    for (other_dep, other_gid), lessons in all_day_data.items():
        if other_dep != department:
            continue
        if other_gid == gid:
            continue
        if len(lessons) > idx:
            other_l = str(lessons[idx])
            other_room = extract_room(other_l)
            if other_room and other_room == room:
                gname = GROUP_ID_TO_NAME.get(other_dep, {}).get(other_gid)
                if gname:
                    overlaps.append(gname)
    if overlaps:
        results.append(f"Сов. {', '.join(sorted(set(overlaps)))}")
    return results


def reply_safe(message, text, parse_mode='Markdown'):
    try:
        bot.send_message(
            message.chat.id,
            text,
            parse_mode=parse_mode,
            message_thread_id=message.message_thread_id)
    except BaseException:
        pass

# ====== ФУНКЦИИ ДЛЯ СОЗДАНИЯ СТИКЕРОВ ======


def get_sticker_font(name, size):
    fonts = {'s1': 'bold.ttf', 's2': 'soft.ttf', 's3': 'cursive.ttf'}
    f_file = fonts.get(name, 'bold.ttf')
    if os.path.exists(f_file):
        return ImageFont.truetype(f_file, size)
    return ImageFont.load_default()


def create_custom_sticker(text, command, author=None):
    size = 512
    bg_color = (40, 40, 40, 255) if author else (255, 255, 255, 0)
    img = Image.new('RGBA', (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    if author:
        text = f"«{text}»"
    lines = textwrap.wrap(
        text, width=15 if command in [
            's_fire', 's_blood'] else 18)
    display_text = "\n".join(lines)
    if author:
        display_text += f"\n\n— {author}"

    f_size = 100
    f_name = command if command in ['s1', 's2', 's3'] else 's1'
    font = get_sticker_font(f_name, f_size)

    while f_size > 20:
        bbox = draw.multiline_textbbox(
            (0, 0), display_text, font=font, align="center", spacing=10)
        if (bbox[2] - bbox[0]) < size - \
                80 and (bbox[3] - bbox[1]) < size - 100:
            break
        f_size -= 5
        font = get_sticker_font(f_name, f_size)

    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((size - w) / 2, (size - h) / 2)

    if command == 's_fire':
        draw.multiline_text(
            pos,
            display_text,
            fill="black",
            font=font,
            stroke_width=10,
            align="center",
            spacing=10)
        draw.multiline_text(
            pos,
            display_text,
            fill="#FF4500",
            font=font,
            align="center",
            spacing=10)
        draw.multiline_text(
            (pos[0],
             pos[1] - 3),
            display_text,
            fill="#FFD700",
            font=font,
            align="center",
            spacing=10)
    elif command == 's_blood':
        for offset in range(8, 0, -2):
            draw.multiline_text(
                (pos[0],
                 pos[1] + offset),
                display_text,
                fill="#8B0000",
                font=font,
                align="center",
                spacing=10)
        draw.multiline_text(
            pos,
            display_text,
            fill="#FF0000",
            font=font,
            stroke_width=2,
            stroke_fill="black",
            align="center",
            spacing=10)
    elif command == 's_glitch':
        draw.multiline_text(
            (pos[0] - 4,
             pos[1]),
            display_text,
            fill="#00FFFF",
            font=font,
            align="center",
            spacing=10)
        draw.multiline_text(
            (pos[0] + 4,
             pos[1]),
            display_text,
            fill="#FF00FF",
            font=font,
            align="center",
            spacing=10)
        draw.multiline_text(
            pos,
            display_text,
            fill="white",
            font=font,
            align="center",
            spacing=10)
    else:
        draw.multiline_text(
            pos,
            display_text,
            fill="white",
            font=font,
            stroke_width=8 if not author else 0,
            stroke_fill="black",
            align="center",
            spacing=10)

    buf = io.BytesIO()
    img.save(buf, format='WEBP')
    buf.seek(0)
    return buf


# ====== ФУНКЦИИ ДЛЯ ОБРАБОТКИ АУДИО ======
LANGUAGES = {
    'ru': 'Русский', 'en': 'Английский', 'de': 'Немецкий', 'fr': 'Французский',
    'es': 'Испанский', 'it': 'Итальянский', 'pt': 'Португальский', 'nl': 'Голландский',
    'pl': 'Польский', 'uk': 'Украинский', 'be': 'Белорусский', 'cs': 'Чешский',
    'sk': 'Словацкий', 'bg': 'Болгарский', 'sr': 'Сербский', 'hr': 'Хорватский',
    'sl': 'Словенский', 'lt': 'Литовский', 'lv': 'Латышский', 'et': 'Эстонский',
    'ro': 'Румынский', 'hu': 'Венгерский', 'el': 'Греческий', 'da': 'Датский',
    'sv': 'Шведский', 'no': 'Норвежский', 'fi': 'Финский', 'is': 'Исландский',
    'zh-cn': 'Китайский (упрощ.)', 'zh-tw': 'Китайский (трад.)', 'ja': 'Японский',
    'ko': 'Корейский', 'vi': 'Вьетнамский', 'th': 'Тайский', 'id': 'Индонезийский',
    'ms': 'Малайский', 'tl': 'Тагальский', 'km': 'Кхмерский', 'lo': 'Лаосский',
    'my': 'Бирманский', 'mn': 'Монгольский', 'ne': 'Непальский', 'si': 'Сингальский',
    'hi': 'Хинди', 'bn': 'Бенгальский', 'ta': 'Тамильский', 'te': 'Телугу',
    'mr': 'Маратхи', 'gu': 'Гуджарати', 'kn': 'Каннада', 'ml': 'Малаялам',
    'pa': 'Панджаби', 'ur': 'Урду', 'sa': 'Санскрит',
    'ar': 'Арабский', 'he': 'Иврит', 'fa': 'Персидский', 'tr': 'Турецкий',
    'ku': 'Курдский', 'ps': 'Пушту', 'dv': 'Дивехи',
    'sw': 'Суахили', 'ha': 'Хауса', 'ig': 'Игбо', 'yo': 'Йоруба',
    'am': 'Амхарский', 'ti': 'Тигринья', 'om': 'Оромо', 'sn': 'Шона',
    'st': 'Сесото', 'tn': 'Тсвана', 'xh': 'Коса', 'zu': 'Зулу',
    'af': 'Африкаанс', 'mg': 'Малагасийский',
    'ca': 'Каталанский', 'gl': 'Галисийский', 'eu': 'Баскский',
    'cy': 'Валлийский', 'gd': 'Шотландский', 'ga': 'Ирландский',
    'mt': 'Мальтийский', 'lb': 'Люксембургский',
    'hy': 'Армянский', 'ka': 'Грузинский', 'az': 'Азербайджанский',
    'kk': 'Казахский', 'ky': 'Киргизский', 'uz': 'Узбекский',
    'tg': 'Таджикский', 'tk': 'Туркменский', 'bs': 'Боснийский',
    'mk': 'Македонский', 'sq': 'Албанский', 'la': 'Латынь',
}

RUSSIAN_TO_CODE = {v.lower(): k for k, v in LANGUAGES.items()}
RUSSIAN_TO_CODE.update({
    'россия': 'ru', 'рф': 'ru', 'рус': 'ru',
    'сша': 'en', 'usa': 'en', 'америка': 'en', 'англия': 'en',
    'германия': 'de', 'франция': 'fr', 'италия': 'it',
    'испания': 'es', 'португалия': 'pt', 'польша': 'pl',
    'украина': 'uk', 'беларусь': 'be', 'белоруссия': 'be',
    'чехия': 'cs', 'словакия': 'sk', 'болгария': 'bg',
    'сербия': 'sr', 'хорватия': 'hr', 'словения': 'sl',
    'литва': 'lt', 'латвия': 'lv', 'эстония': 'et',
    'румыния': 'ro', 'венгрия': 'hu', 'греция': 'el',
    'дания': 'da', 'швеция': 'sv', 'норвегия': 'no',
    'финляндия': 'fi', 'исландия': 'is', 'нидерланды': 'nl',
    'китай': 'zh-cn', 'япония': 'ja', 'корея': 'ko',
    'вьетнам': 'vi', 'таиланд': 'th', 'индонезия': 'id',
    'индия': 'hi', 'арабские': 'ar', 'турция': 'tr',
    'израиль': 'he', 'казахстан': 'kk', 'грузия': 'ka',
    'армения': 'hy', 'азербайджан': 'az', 'узбекистан': 'uz',
    'киргизия': 'ky', 'таджикистан': 'tg', 'туркмения': 'tk',
    'монголия': 'mn', 'египет': 'ar', 'оаэ': 'ar'
})


def get_language_code(text):
    if not text:
        return None
    clean = text.lower().strip()
    if clean in LANGUAGES:
        return clean
    return RUSSIAN_TO_CODE.get(clean)


def process_audio_effects(voice_io, effect=None):
    try:
        song: Any = AudioSegment.from_file(voice_io, format="mp3")
        if effect == "chip":
            new_sample_rate = int(song.frame_rate * 1.5)
            song = song._spawn(
                song.raw_data, overrides={
                    'frame_rate': new_sample_rate})
            song = song.set_frame_rate(44100)
        elif effect == "demon":
            new_sample_rate = int(song.frame_rate * 0.7)
            song = song._spawn(
                song.raw_data, overrides={
                    'frame_rate': new_sample_rate})
            song = song.set_frame_rate(44100)
        elif effect == "echo":
            echo = song - 10
            song = song.overlay(
                echo, position=200).overlay(
                echo - 5, position=400)
        elif effect == "robot":
            combined = song
            for i in range(1, 5):
                delayed = song - (i * 3)
                combined = combined.overlay(delayed, position=i * 150)
            song = combined
        elif effect == "radio":
            song = song.high_pass_filter(1500).low_pass_filter(3000) + 5
        elif effect == "vibe":
            chunk_size = 100
            chunks = []
            for i in range(0, len(song), chunk_size):
                chunk = song[i:i + chunk_size]
                if (i // chunk_size) % 2 == 0:
                    chunks.append(chunk - 10)
                else:
                    chunks.append(chunk)
            if chunks:
                song = chunks[0]
                for chunk in chunks[1:]:
                    song += chunk
        elif effect == "reverb":
            reverb = song - 15
            for i in range(1, 4):
                reverb_part = reverb - (i * 2)
                song = song.overlay(reverb_part, position=i * 100)
        elif effect == "fast":
            song = song.speedup(playback_speed=1.5)
        elif effect == "slow":
            song = song.speedup(playback_speed=0.7)
        out_io = io.BytesIO()
        song.export(out_io, format="ogg", codec="libopus")
        out_io.seek(0)
        return out_io
    except Exception as e:
        print(f"Pydub error: {e}")
        voice_io.seek(0)
        return voice_io

# ====== ФУНКЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ ======


def send_updates_for_day(day, data):
    """Отправляет уведомления об изменениях расписания (включая совмещения)."""
    conn = sqlite3.connect(DB_FILE)
    for m in monitor_manager.active_monitors.values():
        dep = m['department']
        gid = m['group_id']
        key = (dep, gid)
        lessons = data.get(key)
        if not lessons:
            continue

        day_of_week = {
            1: "понедельник",
            2: "вторник",
            3: "среда",
            4: "четверг",
            5: "пятница",
            6: "суббота"}.get(
            day,
            "неизвестно")
        msg = f"📢 Обновление\n{m['group_name']} на {day_of_week}\n\n"
        cnt = 1
        for i, l in enumerate(lessons):
            lines = format_with_overlap(
                m['chat_id'], dep, gid, day, i, str(l), data)
            if not lines:
                continue
            # Добавляем "+К/Ч" к первому уроку в понедельник
            if day == 1 and cnt == 1 and lines:
                lines[0] = lines[0] + " +К/Ч"
            msg += f"{cnt}. {lines[0]}\n"
            if len(lines) > 1:
                msg += f"   {lines[1]}\n"
            cnt += 1
        msg = msg.strip()
        msg_hash = hashlib.md5(msg.encode()).hexdigest()

        cur = conn.execute("SELECT last_msg_hash FROM user_notifications WHERE chat_id=? AND department=? AND group_id=? AND day=?",
                           (m['chat_id'], dep, gid, day))
        row = cur.fetchone()
        thread_id = m.get(
            'message_thread_id') or SPECIAL_CHATS.get(m['chat_id'])
        if row is None:
            try:
                bot.send_message(
                    m['chat_id'],
                    wrap_code(msg),
                    parse_mode='Markdown',
                    message_thread_id=thread_id)
                conn.execute("INSERT INTO user_notifications (chat_id, department, group_id, day, last_msg_hash) VALUES (?, ?, ?, ?, ?)",
                             (m['chat_id'], dep, gid, day, msg_hash))
                conn.commit()
            except Exception as e:
                print(f"Error sending update: {e}")
        elif row[0] != msg_hash:
            try:
                bot.send_message(
                    m['chat_id'],
                    wrap_code(msg),
                    parse_mode='Markdown',
                    message_thread_id=thread_id)
                conn.execute("UPDATE user_notifications SET last_msg_hash=? WHERE chat_id=? AND department=? AND group_id=? AND day=?",
                             (msg_hash, m['chat_id'], dep, gid, day))
                conn.commit()
            except Exception as e:
                print(f"Error sending update: {e}")
    conn.close()

# ====== КОМАНДЫ ======


@bot.message_handler(commands=['r', 'db', 'time',
                     'unsub', 'start', 'about', 'help', 'stats'])
def ad_and_execute(message):
    try:
        bot.send_message(
            message.chat.id,
            "Sub on @kalichoctu",
            message_thread_id=message.message_thread_id)
    except BaseException:
        pass
    raw_cmd = message.text.split()[0].lower()
    cmd = raw_cmd.replace('/', '').split('@')[0]
    if cmd == 'r':
        cmd_r_today(message)
    elif cmd == 'db':
        cmd_db_router(message)
    elif cmd == 'time':
        cmd_time(message)
    elif cmd == 'unsub':
        cmd_unsub(message)
    elif cmd == 'start':
        cmd_start(message)
    elif cmd == 'about':
        cmd_about(message)
    elif cmd == 'help':
        cmd_help(message)
    elif cmd == 'stats':
        cmd_stats(message)


@bot.message_handler(commands=['cs'])
def cmd_clear_stickers(message):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "DELETE FROM item_stickers WHERE chat_id = ?", (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(
            message.chat.id,
            "✅ Все привязки стикеров в этом чате удалены.")
        bot.send_message(
            message.chat.id,
            "Подписывайтесь на @kalichoctu",
            message_thread_id=message.message_thread_id)
    except Exception as e:
        reply_safe(message, wrap_code(f"Ошибка при очистке: {e}"))


def _render_schedule_msg(message, monitor, all_data,
                         day, header_text, send_stickers=False):
    key = (monitor['department'], monitor['group_id'])
    lessons = all_data.get(key)
    if not lessons:
        return reply_safe(message, wrap_code(
            f"{header_text}\n\nНет пар или данных."))

    if send_stickers:
        sent_stickers = set()
        for l_raw in lessons:
            stk = get_item_sticker(message.chat.id, str(l_raw))
            if stk and stk not in sent_stickers:
                bot.send_sticker(
                    message.chat.id,
                    stk,
                    message_thread_id=message.message_thread_id)
                sent_stickers.add(stk)
        if not sent_stickers:
            pass

    res = f"{header_text}\n\n"
    cnt = 1
    for i, l in enumerate(lessons):
        lines = format_with_overlap(
            message.chat.id,
            monitor['department'],
            monitor['group_id'],
            day,
            i,
            str(l),
            all_data)
        if not lines:
            continue
        if day == 1 and cnt == 1 and lines:
            lines[0] = lines[0] + " +К/Ч"
        res += f"{cnt}. {lines[0]}\n"
        if len(lines) > 1:
            res += f"   {lines[1]}\n"
        cnt += 1
    reply_safe(message, wrap_code(res.strip()))


@bot.message_handler(commands=['r'])
def cmd_r_today(message):
    if is_teacher(message.chat.id):
        return cmd_teacher_r(message)
    day = datetime.now().isoweekday()
    if day > 5:
        return reply_safe(message, wrap_code("Отдыхай (выходной)"))
    mons = monitor_manager.get_user_monitors(message.chat.id)
    if not mons:
        return reply_safe(message, "❌ Нет подписок.")
    all_day_data = get_all_schedules_for_day(day)
    all_day_data = apply_teacher_overrides(all_day_data, day)
    for m in mons:
        _render_schedule_msg(
            message,
            m,
            all_day_data,
            day,
            f"📅 Сегодня: {m['group_name']}",
            send_stickers=True)

    settings = get_user_settings(message.chat.id)
    if settings.get('voice_alerts'):
        cmd_r_voice(message)


@bot.message_handler(regexp=r'^/db(\s+.*)?$')
def cmd_db_router(message):
    if is_teacher(message.chat.id):
        return cmd_teacher_db(message)
    args = message.text.replace('/db', '').strip().lower()
    mons = monitor_manager.get_user_monitors(message.chat.id)
    if not mons:
        return reply_safe(message, "❌ Нет подписок.")

    day_map = {'пн': 1, 'вт': 2, 'ср': 3, 'чт': 4, 'пт': 5, 'сб': 6}
    day_labels = {1: "ПН", 2: "ВТ", 3: "СР", 4: "ЧТ", 5: "ПТ", 6: "СБ"}

    # Обработка конкретной даты /db 16.06.2026
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', args):
        try:
            target_date = datetime.strptime(
                args, "%d.%m.%Y").strftime("%Y-%m-%d")
            all_data = get_schedule_history_for_date(target_date)
            if not all_data:
                return reply_safe(message, wrap_code(
                    f"🗄 Нет данных в архиве за {args}"))

            target_weekday = datetime.strptime(args, "%d.%m.%Y").isoweekday()
            all_data = apply_teacher_overrides(all_data, target_weekday)
            for m in mons:
                header = f"🗄 Архив ({args}): {m['group_name']}"
                _render_schedule_msg(
                    message,
                    m,
                    all_data,
                    target_weekday,
                    header,
                    send_stickers=False)
            return
        except ValueError:
            return reply_safe(message, wrap_code(
                "Неверный формат даты. Используйте ДД.ММ.ГГГГ"))

    # Обработка дня недели /db пн
    if args in day_map:
        target_day = day_map[args]
        all_data = get_all_schedules_for_day(target_day)
        if not all_data:
            all_data = {}
            for name, info in GROUP_NAME_TO_ID.items():
                dep, gid = info[0], info[1]
                if dep == mons[0]['department']:
                    lessons = fetch_lessons(target_day, gid, dep)
                    if lessons:
                        all_data[(dep, gid)] = lessons

        for m in mons:
            header = f"🗓 Расписание на {day_labels[target_day]}: {m['group_name']}"
            _render_schedule_msg(
                message,
                m,
                all_data,
                target_day,
                header,
                send_stickers=False)
        return

    # Классический /db (завтра/понедельник)
    curr_day = datetime.now().isoweekday()
    next_day = 1 if curr_day >= 5 else curr_day + 1
    all_data = get_all_schedules_for_day(next_day)
    all_data = apply_teacher_overrides(all_data, next_day)
    for m in mons:
        header = f"📦 БД на {day_labels[next_day]}: {m['group_name']}"
        _render_schedule_msg(
            message,
            m,
            all_data,
            next_day,
            header,
            send_stickers=True)


@bot.message_handler(commands=['now'])
def cmd_now(message):
    bot.send_chat_action(message.chat.id, 'typing')
    if is_teacher(message.chat.id):
        return cmd_teacher_now(message)
    status, _, idx = get_status()
    if status == "rest" or idx is None:
        return reply_safe(message, wrap_code(
            "Отдыхай\n(Используй /db)") + "\n\n/db")
    mons = monitor_manager.get_user_monitors(message.chat.id)
    if not mons:
        return
    day = datetime.now().isoweekday()
    all_data = get_all_schedules_for_day(day)
    all_data = apply_teacher_overrides(all_data, day)
    m = mons[0]
    key = (m['department'], m['group_id'])
    lessons = all_data.get(key)
    if lessons and len(lessons) > idx:
        curr_l_raw = lessons[idx]
        stk = get_item_sticker(message.chat.id, str(curr_l_raw))
        if stk:
            bot.send_sticker(
                message.chat.id,
                stk,
                message_thread_id=message.message_thread_id)
        else:
            pass
        def clean_n(t): return re.sub(
            r'\(?\d{2,4}[А-Яа-я]?\)?', '', str(t)).strip().lower()
        target_n = clean_n(curr_l_raw)
        first_idx = idx
        while first_idx > 0 and clean_n(lessons[first_idx - 1]) == target_n:
            first_idx -= 1
        last_idx = idx
        while last_idx < len(lessons) - \
                1 and clean_n(lessons[last_idx + 1]) == target_n:
            last_idx += 1
        now_dt = datetime.now()
        fmt = "%H:%M"
        start_dt = datetime.strptime(CALLS[first_idx][0], fmt)
        end_dt = datetime.strptime(CALLS[last_idx][1], fmt)
        curr_dt = datetime.strptime(now_dt.strftime(fmt), fmt)
        total_sec = (end_dt - start_dt).seconds
        elapsed_sec = (curr_dt - start_dt).seconds
        percent = min(100, max(0, (elapsed_sec / total_sec) * 100))
        bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))
        lines = format_with_overlap(
            message.chat.id,
            m['department'],
            m['group_id'],
            day,
            idx,
            str(curr_l_raw),
            all_data)
        res_line = lines[0] if lines else str(curr_l_raw)
        td = end_dt - curr_dt
        h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
        rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
        lbl = "До конца блока:" if last_idx > first_idx else "До конца пары:"
        reply_safe(message, wrap_code(
            f"{res_line}\n{bar} {int(percent)}%\n{lbl} {rem}"))


@bot.message_handler(commands=['time'])
def cmd_time(message):
    bot.send_chat_action(message.chat.id, 'typing')
    status, left, _ = get_status()
    wd = datetime.now().isoweekday()
    now = datetime.now()
    curr_time = now.strftime("%H:%M")

    if wd == 1:
        monday_calls = list(CALLS[:8])
        monday_calls.append(("14:50", "15:35"))
        calls_to_show = monday_calls
        end_time = datetime.strptime("15:35", "%H:%M")
    else:
        max_l = 8 if 2 <= wd <= 5 else 0
        calls_to_show = CALLS[:max_l]
        if max_l > 0:
            end_time = datetime.strptime(CALLS[max_l - 1][1], "%H:%M")
        else:
            end_time = None

    if status == 'work' and end_time:
        curr_dt = datetime.strptime(curr_time, "%H:%M")
        if curr_dt < end_time:
            td = end_time - curr_dt
            h, m = td.seconds // 3600, (td.seconds // 60) % 60
            left = f"{f'{h}ч ' if h > 0 else ''}{m}м"
        else:
            left = "0м"
    header = f"До конца дня: {left}" if status != 'rest' else "Отдыхай"

    res = f"{header}\n" + \
        "\n".join([f"{i+1}. {c[0]} - {c[1]}" for i,
                  c in enumerate(calls_to_show)])
    reply_safe(message, wrap_code(res))


@bot.message_handler(commands=['mem'])
def cmd_mem(message):
    raw_text = message.text.replace('/mem', '', 1).strip()
    sep = next((s for s in ['-', '—', ':'] if s in raw_text), None)
    if not sep:
        return reply_safe(message, wrap_code(
            "Ошибка.\nФормат: /mem Предмет - Замена"))
    try:
        old, new = [p.strip() for p in raw_text.split(sep, 1)]
        custom_names_manager.set_name(message.chat.id, old, new)
        reply_safe(message, wrap_code(f"Успех.\n{old} -> {new}"))
    except BaseException:
        reply_safe(message, wrap_code("Ошибка."))


@bot.message_handler(commands=['setsticker'])
def cmd_setsticker(message):
    item_name = message.text.replace('/setsticker', '').strip()
    if not item_name:
        return reply_safe(message, "⚠️ Введите название предмета.")
    waiting_for_sticker[message.chat.id] = item_name
    reply_safe(message, f"🎯 Предмет '{item_name}' выбран. Отправь стикер.")


@bot.message_handler(content_types=['sticker'])
def handle_sticker_save(message):
    if message.chat.id in waiting_for_sticker:
        item = waiting_for_sticker.pop(message.chat.id)
        save_item_sticker(message.chat.id, item, message.sticker.file_id)
        reply_safe(message, f"✅ Стикер привязан к '{item}'!")


@bot.message_handler(commands=['list'])
def cmd_list(message):
    if is_teacher(message.chat.id):
        dept, rooms = get_teacher_info(message.chat.id)
        return reply_safe(
            message, f"🧑‍🏫 *Учитель*\nОтделение: {dept}\nКабинеты: {', '.join(rooms)}")
    mons = monitor_manager.get_user_monitors(message.chat.id)
    reply_safe(message, "📋 *Подписки:*\n" +
               "\n".join([f"- {m['group_name']}" for m in mons]))


@bot.message_handler(commands=['unsub'])
def cmd_unsub(message):
    if is_teacher(message.chat.id):
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM teachers WHERE chat_id=?",
                     (message.chat.id,))
        conn.commit()
        conn.close()
        return reply_safe(
            message, "🗑 Учительский профиль удалён. /start — зарегистрироваться снова.")
    to_del = [
        k for k,
        v in monitor_manager.active_monitors.items() if str(
            v['chat_id']) == str(
            message.chat.id)]
    for k in to_del:
        del monitor_manager.active_monitors[k]
    monitor_manager.save()
    reply_safe(message, "🗑 Подписки удалены.")


@bot.message_handler(commands=['move'])
def cmd_move(message):
    """Команда учителя для замены кабинета/предмета на конкретную пару."""
    if not is_teacher(message.chat.id):
        return
    dept, rooms = get_teacher_info(message.chat.id)
    if not dept:
        return reply_safe(message, "❌ Вы не зарегистрированы как учитель.")

    args_str = message.text.replace('/move', '', 1).strip()
    day_map = {'пн': 1, 'вт': 2, 'ср': 3, 'чт': 4, 'пт': 5, 'сб': 6}
    day_names = {1: "ПН", 2: "ВТ", 3: "СР", 4: "ЧТ", 5: "ПТ", 6: "СБ"}
    today = datetime.now().isoweekday()

    # Справка
    if not args_str:
        return reply_safe(message, wrap_code(
            "Формат /move:\n"
            "/move <пара> <кабинет>          — сегодня, все группы\n"
            "/move <пара> <кабинет> <группа> — для конкретной группы\n"
            "/move <день> <пара> <кабинет>   — другой день\n"
            "/move <пара> п=<предмет>        — изменить предмет\n"
            "/move <пара> <каб> п=<предмет>  — и то и другое\n"
            "/move clear                     — сброс на сегодня\n"
            "/move clear <день>              — сброс на день\n\n"
            "Примеры:\n"
            "/move 3 101\n"
            "/move пн 3 101 ИС-41-22\n"
            "/move 3 п=Алгебра\n"
            "/move 3 101 п=Алгебра"
        ))

    tokens = args_str.split()

    # /move clear [день]
    if tokens[0].lower() == 'clear':
        rest = tokens[1].lower() if len(tokens) > 1 else ''
        target_day = day_map.get(rest, today)
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM teacher_room_overrides WHERE teacher_chat_id=? AND day=?",
                     (message.chat.id, target_day))
        conn.commit()
        conn.close()
        return reply_safe(message, wrap_code(
            f"🗑 Замены на {day_names.get(target_day, '?')} сброшены."))

    # Определяем день
    target_day = today
    if tokens[0].lower() in day_map:
        target_day = day_map[tokens.pop(0).lower()]

    if not tokens:
        return reply_safe(message, "❌ Укажите номер пары.")

    # Номер пары
    try:
        slot_num = int(tokens.pop(0))
        slot_idx = slot_num - 1
    except ValueError:
        return reply_safe(message, "❌ Номер пары должен быть цифрой (1–10).")
    if slot_idx < 0 or slot_idx >= 10:
        return reply_safe(message, "❌ Номер пары от 1 до 10.")

    # Разбираем остаток: кабинет, п=предмет, название группы
    new_room = None
    new_subject = None
    group_id = -1  # -1 = все группы
    remaining = []

    for t in tokens:
        tl = t.lower()
        if tl.startswith('п=') or tl.startswith('предм='):
            new_subject = t.split('=', 1)[1]
        elif re.match(r'^\d+[А-Яа-яA-Za-z]?$', t) and new_room is None:
            new_room = t
        else:
            remaining.append(t)

    # Остаток — возможно название группы
    if remaining:
        group_str = ' '.join(remaining).upper()
        for k, v in GROUP_NAME_TO_ID.items():
            if group_str == k.upper() or group_str == k.upper().replace('-', ' '):
                dept = v[0]  # Изменяем отделение на отделение найденной группы!
                group_id = v[1]
                break
        if group_id == -1 and remaining:
            return reply_safe(message, wrap_code(
                f"❌ Группа '{group_str}' не найдена."))

    if new_room is None and new_subject is None:
        return reply_safe(
            message, "❌ Укажите кабинет (число) и/или предмет (п=Название).")

    # Сохраняем
    save_teacher_override(
        message.chat.id,
        dept,
        target_day,
        slot_idx,
        group_id,
        new_room,
        new_subject)

    # Формируем подтверждение
    all_data = get_all_schedules_for_day(target_day)
    sample_lesson = None
    if group_id == -1:
        # Ищем пример урока в своих кабинетах
        _, teacher_rooms = get_teacher_info(message.chat.id)
        for (d, gid2), ls in all_data.items():
            if d == dept and slot_idx < len(ls):
                r = extract_room(str(ls[slot_idx]))
                if r and teacher_rooms and any(
                        tr.strip() in r for tr in teacher_rooms):
                    sample_lesson = str(ls[slot_idx])
                    break
        # Если не нашли по кабинетам — берём любой
        if not sample_lesson:
            for (d, gid2), ls in all_data.items():
                if d == dept and slot_idx < len(ls):
                    sample_lesson = str(ls[slot_idx])
                    break
    else:
        ls = all_data.get((dept, group_id), [])
        if slot_idx < len(ls):
            sample_lesson = str(ls[slot_idx])

    orig_room = extract_room(sample_lesson) or "?" if sample_lesson else "?"
    orig_subj = re.sub(
        r'\s*\(.*$', '', sample_lesson).strip() if sample_lesson else "?"
    group_label = GROUP_ID_TO_NAME.get(dept, {}).get(
        group_id, "?") if group_id != -1 else "все группы"

    conf = [f"✅ Сохранено | {day_names.get(target_day, '?')}, пара {slot_num}"]
    if new_room:
        conf.append(f"Кабинет: {orig_room} → {new_room}")
    if new_subject:
        conf.append(f"Предмет: {orig_subj} → {new_subject}")
    conf.append(f"Группа: {group_label}")
    conf.append("⏳ Уведомление ученикам через ~5 мин")
    reply_safe(message, wrap_code("\n".join(conf)))


@bot.message_handler(commands=['s', 's1', 's2',
                     's3', 's_fire', 's_blood', 's_glitch'])
def cmd_text_to_sticker(message):
    cmd = message.text.split()[0][1:]
    if cmd == 's':
        cmd = 's1'
    parts = message.text.split(maxsplit=1)
    text = parts[1] if len(parts) > 1 else ""
    author = None
    if not text and message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text
        u = message.reply_to_message.from_user
        author = f"@{u.username}" if u.username else u.first_name
    if not text:
        return reply_safe(message, "Напиши текст или ответь на сообщение!")
    bot.send_chat_action(message.chat.id, 'choose_sticker')
    try:
        sticker = create_custom_sticker(text, cmd, author)
        bot.send_sticker(
            message.chat.id,
            sticker,
            message_thread_id=message.message_thread_id)
    except Exception as e:
        reply_safe(message, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['gs'])
def cmd_gs(message):
    args = message.text.split(maxsplit=2)
    effect = None
    lang = 'ru'
    text = ""
    known_effects = [
        'chip',
        'demon',
        'echo',
        'robot',
        'radio',
        'vibe',
        'slow',
        'fast',
        'reverb']

    if message.reply_to_message and (
            message.reply_to_message.text or message.reply_to_message.caption):
        text = message.reply_to_message.text or message.reply_to_message.caption
        if len(args) > 1:
            val = args[1].lower()
            if val in known_effects:
                effect = val
            else:
                code = get_language_code(val)
                if code:
                    lang = code
                elif val == 'slow':
                    effect = 'slow'
    else:
        if len(args) < 2:
            popular_langs = ['русский', 'английский', 'немецкий', 'французский',
                             'испанский', 'китайский', 'японский', 'арабский']
            popular_effects = ['robot', 'demon', 'radio', 'fast']
            reply_text = (
                "🎤 *Голосовой синтезатор*\n\n"
                "`/gs [эффект] текст` – озвучить текст\n"
                "`/gs [страна] текст` – выбрать язык\n\n"
                "*Примеры:*\n"
                "`/gs robot Привет`\n"
                "`/gs английский Hello`\n"
                "`/gs китайский 你好`\n"
                "Ответь на сообщение: `/gs японский`\n\n"
                f"*Популярные языки:* {', '.join(popular_langs)}\n"
                f"*Эффекты:* {', '.join(popular_effects)}, slow, vibe, reverb\n\n"
                "📚 *Все языки:* используй /langs для полного списка"
            )
            return reply_safe(message, reply_text, parse_mode="Markdown")

        val = args[1].lower()
        if val in known_effects:
            effect = val
            text = args[2] if len(args) > 2 else ""
        else:
            code = get_language_code(val)
            if code:
                lang = code
                text = args[2] if len(args) > 2 else ""
            else:
                text = message.text.replace('/gs', '', 1).strip()

    if not text:
        return reply_safe(message, "❌ Текст не найден.")

    try:
        bot.send_chat_action(
            message.chat.id,
            'record_audio',
            message_thread_id=message.message_thread_id)
        lang_name = LANGUAGES.get(lang, lang)
        tts = gTTS(text=text[:500], lang=lang, slow=False)
        temp_io = io.BytesIO()
        tts.write_to_fp(temp_io)
        temp_io.seek(0)
        final_voice = process_audio_effects(temp_io, effect=effect)
        caption = f"🗣 {lang_name}"
        if effect:
            caption += f" + эффект {effect}"
        bot.send_voice(
            message.chat.id,
            final_voice,
            caption=caption,
            reply_to_message_id=message.message_id,
            message_thread_id=message.message_thread_id
        )
    except Exception as e:
        error_msg = f"❌ Ошибка: {e}"
        if "lang" in str(e).lower():
            error_msg += f"\nЯзык '{lang}' может не поддерживаться. Попробуй другой."
        reply_safe(message, error_msg)


@bot.message_handler(commands=['langs'])
def cmd_langs(message):
    regions = {
        '🇪🇺 Европа': ['ru', 'en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'uk', 'be', 'cs', 'sk', 'bg', 'sr', 'hr', 'sl', 'lt', 'lv', 'et', 'ro', 'hu', 'el', 'da', 'sv', 'no', 'fi', 'is', 'ca', 'gl', 'eu', 'cy', 'gd', 'ga', 'mt', 'lb'],
        '🇷🇺 СНГ': ['ru', 'uk', 'be', 'kk', 'ky', 'uz', 'tg', 'tk', 'hy', 'ka', 'az'],
        '🇨🇳 Азия': ['zh-cn', 'zh-tw', 'ja', 'ko', 'vi', 'th', 'id', 'ms', 'tl', 'km', 'lo', 'my', 'mn', 'ne'],
        '🇮🇳 Индия': ['hi', 'bn', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'pa', 'ur', 'sa'],
        '🌍 Ближний Восток': ['ar', 'he', 'fa', 'tr', 'ku', 'ps', 'dv'],
        '🌍 Африка': ['sw', 'ha', 'ig', 'yo', 'am', 'ti', 'om', 'sn', 'st', 'tn', 'xh', 'zu', 'af', 'mg'],
    }
    text = "📚 *Все доступные языки:*\n\n"
    for region, codes in regions.items():
        text += f"{region}\n"
        lang_list = []
        for code in codes:
            if code in LANGUAGES:
                lang_list.append(f"{LANGUAGES[code]} (`{code}`)")
        text += " • " + "\n • ".join(lang_list[:5])
        if len(lang_list) > 5:
            text += f"\n • ... и ещё {len(lang_list)-5}"
        text += "\n\n"
    text += "💡 *Как использовать:*\n"
    text += "`/gs французский Привет`\n"
    text += "`/gs японский こんにちは`"
    reply_safe(message, text, parse_mode="Markdown")


@bot.message_handler(commands=['r_voice'])
def cmd_r_voice(message):
    bot.send_chat_action(message.chat.id, 'typing')
    day = datetime.now().isoweekday()
    if day > 5:
        return reply_safe(message, "Хм, в выходные я тоже отдыхаю, а ты? >w<")
    mons = monitor_manager.get_user_monitors(message.chat.id)
    if not mons:
        return reply_safe(message, "❌ Нет активных подписок.")
    all_day_data = get_all_schedules_for_day(day)
    for m in mons:
        key = (m['department'], m['group_id'])
        lessons = all_day_data.get(key)
        if not lessons:
            continue
        text = f"Расписание на сегодня для группы {m['group_name']}. "
        for i, l in enumerate(lessons):
            lines = format_with_overlap(
                message.chat.id,
                m['department'],
                m['group_id'],
                day,
                i,
                str(l),
                all_day_data)
            if lines:
                subject = re.sub(r'\(.*?\)', '', lines[0]).strip()
                text += f"Пара {i+1}: {subject}. "
        try:
            bot.send_chat_action(
                message.chat.id,
                'record_audio',
                message_thread_id=message.message_thread_id)
            settings = get_user_settings(message.chat.id)
            tts = gTTS(text=text, lang='ru')
            temp_io = io.BytesIO()
            tts.write_to_fp(temp_io)
            temp_io.seek(0)

            # Использовать выбранный эффект из настроек
            chosen_effect = settings.get('voice_effect', 'echo')
            final_voice = process_audio_effects(
                temp_io, effect=chosen_effect if chosen_effect != 'none' else None)
            bot.send_voice(
                message.chat.id,
                final_voice,
                message_thread_id=message.message_thread_id)
        except Exception as e:
            reply_safe(
                message,
                f"❌ Ошибка при генерации голосового расписания: {e}")


@bot.message_handler(commands=['flush'])
def cmd_flush(message):
    if message.from_user.id in MODERATOR_IDS:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM schedules")
        conn.commit()
        conn.close()
        reply_safe(message, "♻️ База очищена.")


hdxvhgv = 'CAACAgIAAxkBAAIJ-mmMschzUfv2_1N4Y0ML4VqTgt9LAAICnAAChC1oSPR48gzQTUpZOgQ'


@bot.message_handler(commands=['clear'])
def handle_clear(message):
    try:
        for _ in range(4):
            bot.send_sticker(
                message.chat.id,
                hdxvhgv,
                message_thread_id=message.message_thread_id)
            time.sleep(0.3)
    except Exception as e:
        print(f"Ошибка: {e}")


@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_chat_action(message.chat.id, 'typing')
    waiting_for_department[message.chat.id] = True
    if message.chat.id in user_department:
        del user_department[message.chat.id]
    settings = get_user_settings(message.chat.id)
    if settings.get('fluffy_mode'):
        welcome_text = (
            "👋 Привет! Я — Калич, ваш пушистый лисёнок‑помощник! 🦊\n"
            "С радостью помогу вам быстро узнать расписание и любые замены.\n\n"
            "Выберите свою роль:"
        )
    else:
        welcome_text = (
            "Добро пожаловать в систему расписания.\n"
            "Пожалуйста, выберите вашу роль:"
        )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton(
            "1️⃣ Первое отделение",
            callback_data="start_role_1"),
        telebot.types.InlineKeyboardButton(
            "2️⃣ Второе отделение", callback_data="start_role_2")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "3️⃣ Третье отделение",
            callback_data="start_role_3"),
        telebot.types.InlineKeyboardButton(
            "🧑‍🏫 Я учитель", callback_data="start_role_4")
    )
    try:
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
    except BaseException:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith(
    'approve_teacher_') or c.data.startswith('deny_teacher_'))
def handle_teacher_approval(call):
    """Callback-обработчик одобрения/отклонения учителя модератором."""
    if call.from_user.id not in MODERATOR_IDS:
        return bot.answer_callback_query(call.id, "Нет доступа.")
    parts = call.data.split('_')
    action = parts[0]  # 'approve' или 'deny'
    teacher_chat_id = int(parts[2])
    if action == 'approve':
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "UPDATE teachers SET status='approved' WHERE chat_id=?", (teacher_chat_id,))
        conn.commit()
        conn.close()
        try:
            bot.send_message(teacher_chat_id,
                             "✅ Ваша регистрация одобрена! Теперь доступны команды:\n/r, /db, /now, /next, /time, /f, /list")
        except BaseException:
            pass
        try:
            bot.edit_message_text(
                "✅ Одобрено.",
                call.message.chat.id,
                call.message.message_id)
        except BaseException:
            pass
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM teachers WHERE chat_id=?",
                     (teacher_chat_id,))
        conn.commit()
        conn.close()
        try:
            bot.send_message(teacher_chat_id,
                             "❌ Заявка отклонена. Попробуйте ещё раз: /start")
        except BaseException:
            pass
        try:
            bot.edit_message_text(
                "❌ Отклонено.",
                call.message.chat.id,
                call.message.message_id)
        except BaseException:
            pass
    bot.answer_callback_query(call.id)


def get_user_settings(chat_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute(
            "SELECT notifications, voice_alerts, fluffy_mode, voice_effect FROM user_settings WHERE chat_id=?",
            (chat_id,
             )).fetchone()
        conn.close()
        if row:
            return {'notifications': row[0], 'voice_alerts': row[1],
                    'fluffy_mode': row[2], 'voice_effect': row[3] or 'echo'}
    except BaseException:
        pass
    return {'notifications': 1, 'voice_alerts': 0,
            'fluffy_mode': 0, 'voice_effect': 'echo'}


def set_user_setting(chat_id, key, value):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (chat_id) VALUES (?)", (chat_id,))
        conn.execute(
            f"UPDATE user_settings SET {key}=? WHERE chat_id=?", (value, chat_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Settings err: {e}")


@bot.message_handler(commands=['settings'])
def cmd_settings(message):
    bot.send_chat_action(message.chat.id, 'typing')
    settings = get_user_settings(message.chat.id)
    markup = telebot.types.InlineKeyboardMarkup()
    notif_btn = "✅ Уведомления" if settings['notifications'] else "❌ Уведомления"
    voice_btn = "✅ Голосовые ответы" if settings['voice_alerts'] else "❌ Голосовые ответы"
    fluffy_btn = "🦊 Fluffy mode" if settings['fluffy_mode'] else "🤖 Строгий бот"
    effect_btn = f"🎧 Эффект: {settings.get('voice_effect', 'echo')}"

    markup.add(telebot.types.InlineKeyboardButton(
        notif_btn, callback_data="toggle_notifications"))
    markup.add(telebot.types.InlineKeyboardButton(
        voice_btn, callback_data="toggle_voice_alerts"))
    markup.add(telebot.types.InlineKeyboardButton(
        effect_btn, callback_data="cycle_voice_effect"))
    markup.add(telebot.types.InlineKeyboardButton(
        fluffy_btn, callback_data="toggle_fluffy_mode"))

    msg_text = "⚙️ Ваши настройки:\n(Включите Fluffy mode, если хотите чтобы бот общался как милый лисёнок!)"
    bot.send_message(message.chat.id, msg_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith('toggle_')
                            or c.data.startswith('cycle_'))
def handle_settings_toggle(call):
    chat_id = call.message.chat.id
    settings = get_user_settings(chat_id)

    if call.data == "toggle_notifications":
        new_val = 0 if settings['notifications'] else 1
        set_user_setting(chat_id, 'notifications', new_val)
    elif call.data == "toggle_voice_alerts":
        new_val = 0 if settings['voice_alerts'] else 1
        set_user_setting(chat_id, 'voice_alerts', new_val)
    elif call.data == "toggle_fluffy_mode":
        new_val = 0 if settings['fluffy_mode'] else 1
        set_user_setting(chat_id, 'fluffy_mode', new_val)
    elif call.data == "cycle_voice_effect":
        effects = [
            'echo',
            'robot',
            'chip',
            'demon',
            'radio',
            'vibe',
            'slow',
            'fast',
            'reverb',
            'none']
        current = str(settings.get('voice_effect', 'echo'))
        try:
            nxt_idx = (effects.index(current) + 1) % len(effects)
        except ValueError:
            nxt_idx = 0
        set_user_setting(chat_id, 'voice_effect', effects[nxt_idx])

    settings = get_user_settings(chat_id)
    markup = telebot.types.InlineKeyboardMarkup()
    notif_btn = "✅ Уведомления" if settings['notifications'] else "❌ Уведомления"
    voice_btn = "✅ Голосовые ответы" if settings['voice_alerts'] else "❌ Голосовые ответы"
    fluffy_btn = "🦊 Fluffy mode" if settings['fluffy_mode'] else "🤖 Строгий бот"
    effect_btn = f"🎧 Эффект: {settings.get('voice_effect', 'echo')}"

    markup.add(telebot.types.InlineKeyboardButton(
        notif_btn, callback_data="toggle_notifications"))
    markup.add(telebot.types.InlineKeyboardButton(
        voice_btn, callback_data="toggle_voice_alerts"))
    markup.add(telebot.types.InlineKeyboardButton(
        effect_btn, callback_data="cycle_voice_effect"))
    markup.add(telebot.types.InlineKeyboardButton(
        fluffy_btn, callback_data="toggle_fluffy_mode"))

    bot.edit_message_reply_markup(
        chat_id,
        call.message.message_id,
        reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    bot.send_chat_action(message.chat.id, 'typing')
    settings = get_user_settings(message.chat.id)
    if settings.get('fluffy_mode'):
        reply_safe(message, messages.PING_FLUFFY)
    else:
        reply_safe(message, messages.PING_NORMAL)


@bot.message_handler(commands=['cancel'])
def cmd_cancel(message):
    bot.send_chat_action(message.chat.id, 'typing')
    cid = message.chat.id
    canceled = False
    for d in (waiting_for_department, user_department, waiting_for_teacher_dept,
              waiting_for_teacher_rooms, waiting_for_sticker, waiting_for_stats_dates):
        if cid in d:
            del d[cid]
            canceled = True
    if canceled:
        reply_safe(message, messages.CANCEL_SUCCESS)
    else:
        reply_safe(message, messages.CANCEL_NOTHING)


@bot.message_handler(commands=['about'])
def cmd_about(message):
    settings = get_user_settings(message.chat.id)
    if settings.get('fluffy_mode'):
        about_text = messages.ABOUT_FLUFFY
    else:
        about_text = messages.ABOUT_NORMAL
    cmds = [wrap_code(c) for c in messages.ABOUT_COMMANDS]
    reply_safe(message, about_text + "\n\n" + "\n\n".join(cmds))

# ====== HELP COMMAND ======


@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.send_chat_action(message.chat.id, 'typing')
    """Send a detailed help message with usage instructions for all bot commands."""
    help_text = messages.HELP_TEXT_MAIN

    if is_teacher(message.chat.id):
        help_text += messages.HELP_TEXT_TEACHER

    help_text += messages.HELP_TEXT_EXTRA
    reply_safe(message, help_text)


def get_next_block_info(cid, department, gid, day, data, current_idx=None):
    try:
        lessons = data.get((department, gid), [])
        if not lessons:
            return None
        now_dt = datetime.now()
        curr_time = now_dt.strftime("%H:%M")
        next_idx = None
        if current_idx is not None:
            def clean_n(t): return re.sub(
                r'\(?\d{2,4}[А-Яа-я]?\)?', '', str(t)).strip().lower()
            target_n = clean_n(lessons[current_idx])
            check_idx = current_idx
            while check_idx < len(
                    lessons) - 1 and clean_n(lessons[check_idx + 1]) == target_n:
                check_idx += 1
            if check_idx + 1 < len(lessons):
                next_idx = check_idx + 1
        else:
            for i, call in enumerate(CALLS):
                if call[0] > curr_time and i < len(lessons):
                    next_idx = i
                    break
        if next_idx is None or next_idx >= len(lessons):
            return None

        def clean_n(t): return re.sub(
            r'\(?\d{2,4}[А-Яа-я]?\)?', '', str(t)).strip().lower()
        next_name_raw = clean_n(lessons[next_idx])
        block_count = 1
        temp_idx = next_idx
        while temp_idx < len(
                lessons) - 1 and clean_n(lessons[temp_idx + 1]) == next_name_raw:
            temp_idx += 1
            block_count += 1
        start_time = CALLS[next_idx][0]
        td = datetime.strptime(start_time, "%H:%M") - \
            datetime.strptime(curr_time, "%H:%M")
        h, m = td.seconds // 3600, (td.seconds // 60) % 60
        rem_str = f"{f'{h}ч ' if h > 0 else ''}{m}м"
        lines = format_with_overlap(
            cid,
            department,
            gid,
            day,
            next_idx,
            lessons[next_idx],
            data)
        clean_name = lines[0] if lines else str(lessons[next_idx])
        return {
            "name": clean_name,
            "count": block_count,
            "time_to": rem_str,
            "raw_name": lessons[next_idx]
        }
    except BaseException:
        return None


@bot.message_handler(commands=['next'])
def cmd_next(message):
    bot.send_chat_action(message.chat.id, 'typing')
    if is_teacher(message.chat.id):
        return cmd_teacher_next(message)
    mons = monitor_manager.get_user_monitors(message.chat.id)
    if not mons:
        return reply_safe(
            message, "❌ Нет подписок. Сначала отправь номер группы.")
    day = datetime.now().isoweekday()
    data = get_all_schedules_for_day(day)
    m = mons[0]
    status, _, idx = get_status()
    info = get_next_block_info(
        message.chat.id,
        m['department'],
        m['group_id'],
        day,
        data,
        idx)
    if info:
        stk = get_item_sticker(message.chat.id, str(info['raw_name']))
        if stk:
            bot.send_sticker(
                message.chat.id,
                stk,
                message_thread_id=message.message_thread_id)
        else:
            send_random_sticker(message)
        res = (
            f"Далее: {info['name']}\n"
            f"Длительность: {format_lessons_count(info['count'])}\n"
            f"Через: {info['time_to']}"
        )
        reply_safe(message, wrap_code(res))
    else:
        reply_safe(message, wrap_code("Пар больше нет") + "\n\n/db")


def format_lessons_count(count):
    if count == 1:
        return "пол пары"
    if count == 2:
        return "1 пара"
    if count == 3:
        return "полторы пары"
    if count == 4:
        return "2 пары"
    return f"{count / 2} пары"


@bot.message_handler(commands=['sendall'])
def cmd_sendall(message):
    bot.send_chat_action(message.chat.id, 'typing')
    if message.from_user.id not in MODERATOR_IDS:
        return
    source_text = ""
    if message.reply_to_message:
        source_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    else:
        source_text = message.text.replace('/sendall', '', 1).strip()
    if not source_text:
        return reply_safe(message, "⚠️ Нет текста для рассылки.")
    header = "Новости:ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ"
    full_block_text = f"```{header}\n{source_text}```"
    found_commands = re.findall(r'(/[a-zA-Z0-9_]+)', source_text)
    commands_message = " ".join(dict.fromkeys(found_commands))
    sent_targets = set()
    for m in monitor_manager.active_monitors.values():
        cid = m['chat_id']
        thread = m.get('message_thread_id') or SPECIAL_CHATS.get(cid)
        target_key = (cid, thread)
        if target_key in sent_targets:
            continue
        sent_targets.add(target_key)
        try:
            bot.send_message(
                cid,
                full_block_text,
                parse_mode='Markdown',
                message_thread_id=thread)
            if commands_message:
                bot.send_message(
                    cid, commands_message, message_thread_id=thread)
            time.sleep(0.1)
        except BaseException:
            continue
    reply_safe(message, "✅ Рассылка выполнена.")


@bot.message_handler(commands=['f'])
def cmd_find_by_room(message):
    bot.send_chat_action(message.chat.id, 'typing')
    room_target = message.text.replace('/f', '', 1).strip()
    if not room_target:
        return reply_safe(message, wrap_code(
            "Ошибка: введите номер кабинета.\nПример: /f 44"))

    mons = monitor_manager.get_user_monitors(message.chat.id)
    if not mons:
        return reply_safe(
            message, "❌ Нет активных подписок. Сначала подпишитесь на группу, чтобы определить отделение.")

    user_department = mons[0]['department']
    day = datetime.now().isoweekday()
    if day > 5:
        return reply_safe(message, wrap_code("Сегодня выходной, занятий нет."))

    all_data = get_all_schedules_for_day(day)
    max_lessons = 10
    schedule = [{} for _ in range(max_lessons)]

    for (dep, gid), lessons in all_data.items():
        if dep != user_department:
            continue
        group_name = GROUP_ID_TO_NAME.get(dep, {}).get(gid, "?")
        for idx in range(min(len(lessons), max_lessons)):
            l_str = str(lessons[idx])
            room = extract_room(l_str)
            if room and room_target in room:
                applied = custom_names_manager.apply(
                    message.chat.id, l_str) or ""
                subj = re.sub(r'\s*\([^)]*\)$', '', applied).strip()
                if subj:
                    if subj not in schedule[idx]:
                        schedule[idx][subj] = []
                    schedule[idx][subj].append(group_name)

    res_lines = [f"Кабинет {room_target} (отделение {user_department}):"]
    for i, hour in enumerate(schedule):
        if hour:
            row = " / ".join([f"{s} ({', '.join(g)})" for s,
                             g in hour.items()])
            res_lines.append(f"{i+1}. {row}")
        else:
            res_lines.append(f"{i+1}. ---")

    reply_safe(message, wrap_code("\n".join(res_lines)))


@bot.message_handler(commands=['w'])
def cmd_find_by_group(message):
    bot.send_chat_action(message.chat.id, 'typing')
    target_group = message.text.replace('/w', '', 1).strip().upper()
    if not target_group:
        return reply_safe(message, wrap_code(
            "Ошибка: введите группу.\nПример: /w ИС-41-22"))

    clean_target = target_group.replace('-', ' ').replace('_', ' ')
    group_info = None

    # Ищем точное совпадение
    for k, v in GROUP_NAME_TO_ID.items():
        if clean_target == k.upper().replace('-', ' ').replace('_', ' '):
            group_info = v
            target_group = k
            break

    # Если не нашли, ищем по вхождению
    if not group_info:
        for k, v in GROUP_NAME_TO_ID.items():
            if clean_target in k.upper().replace('-', ' ').replace('_', ' ').split():
                group_info = v
                target_group = k
                break

    if not group_info:
        return reply_safe(message, wrap_code(
            f"Группа {target_group} не найдена."))
    department, gid = group_info[0], group_info[1]

    day = datetime.now().isoweekday()
    if day > 5:
        return reply_safe(message, wrap_code(
            f"{target_group}: отдых (выходной)"))

    all_day_data = get_all_schedules_for_day(day)
    lessons = all_day_data.get(
        (department, gid)) or fetch_lessons(
        day, gid, department)

    if lessons:
        res = f"Группа {target_group}:\n\n"
        cnt = 1
        for i, l in enumerate(lessons):
            lines = format_with_overlap(
                message.chat.id, department, gid, day, i, l, all_day_data)
            if not lines:
                continue
            if day == 1 and cnt == 1 and lines:
                lines[0] = lines[0] + " +К/Ч"
            res += f"{cnt}. {lines[0]}\n"
            if len(lines) > 1:
                res += f"   {lines[1]}\n"
            cnt += 1
        reply_safe(message, wrap_code(res.strip()))
    else:
        reply_safe(message, wrap_code(
            f"Нет данных для {target_group} на сегодня."))


@bot.message_handler(commands=['fill'])
def cmd_fill(message):
    bot.send_chat_action(message.chat.id, 'typing')
    if message.from_user.id not in MODERATOR_IDS:
        return
    reply_safe(message, "⏳ Заполнение базы (ПН-ПТ) для всех отделений...")
    try:
        c = 0
        for d in [1, 2, 3, 4, 5]:
            date_str = get_date_for_weekday(d)
            for name, info in GROUP_NAME_TO_ID.items():
                dep, gid = info[0], info[1]
                raw = fetch_lessons(d, gid, dep)
                if raw:
                    h = hashlib.md5("".join(raw).encode()).hexdigest()
                    save_schedule_to_db(
                        dep, gid, d, h, json.dumps(
                            raw, ensure_ascii=False), date_str)
                    c += 1
                time.sleep(0.05)
        reply_safe(message, f"✅ База заполнена! Записей: {c}")
    except Exception as e:
        reply_safe(message, f"❌ Ошибка: {e}")

# ====== ФОНОВЫЕ ПРОЦЕССЫ ======


def morning_broadcast():
    sent_today = False
    while True:
        try:
            now = datetime.now()
            if now.hour == 7 and now.minute == 0 and now.isoweekday() <= 5 and not sent_today:
                day = now.isoweekday()
                data = get_all_schedules_for_day(day)
                chats = {}
                for m in monitor_manager.active_monitors.values():
                    cid = m['chat_id']
                    if cid not in chats:
                        chats[cid] = []
                    chats[cid].append(m)
                for cid, ms in chats.items():
                    for m in ms:
                        lessons = data.get((m['department'], m['group_id']))
                        if lessons:
                            res = f"☀️ Доброе утро!\n📅 Расписание: {m['group_name']}\n\n"
                            cnt = 1
                            for i, l in enumerate(lessons):
                                lines = format_with_overlap(
                                    cid, m['department'], m['group_id'], day, i, str(l), data)
                                if not lines:
                                    continue
                                if day == 1 and cnt == 1 and lines:
                                    lines[0] = lines[0] + " +К/Ч"
                                res += f"{cnt}. {lines[0]}\n"
                                if len(lines) > 1:
                                    res += f"   {lines[1]}\n"
                                cnt += 1
                            try:
                                thread_id = m.get(
                                    'message_thread_id') or SPECIAL_CHATS.get(cid)
                                bot.send_message(
                                    cid,
                                    wrap_code(
                                        res.strip()),
                                    parse_mode='Markdown',
                                    message_thread_id=thread_id)
                            except BaseException:
                                pass
                sent_today = True
            if now.hour == 8:
                sent_today = False
        except BaseException:
            pass
        time.sleep(30)


def check_loop():
    while True:
        try:
            now = datetime.now()
            is_silent = (now.hour >= 23 or now.hour < 6)
            wd = now.isoweekday()
            days = [wd] if wd <= 5 else []
            days.append(wd + 1 if wd < 5 else 1)

            for d in set(days):
                data = get_all_schedules_for_day(d)
                date_str = get_date_for_weekday(d)

                for name, info in GROUP_NAME_TO_ID.items():
                    dep, gid = info[0], info[1]
                    raw = fetch_lessons(d, gid, dep)
                    if not raw:
                        continue
                    h = hashlib.md5("".join(raw).encode()).hexdigest()

                    conn = sqlite3.connect(DB_FILE)
                    old = conn.execute(
                        "SELECT content_hash FROM schedules WHERE group_id=? AND day=? AND department=?",
                        (gid,
                         d,
                         dep)).fetchone()
                    conn.close()

                    if not old or old[0] != h:
                        save_schedule_to_db(
                            dep, gid, d, h, json.dumps(
                                raw, ensure_ascii=False), date_str)
                        if is_silent:
                            continue
                        data = get_all_schedules_for_day(d)
                send_updates_for_day(d, data)
        except Exception as e:
            print(f"Check loop error: {e}")
        time.sleep(600)


def process_start_role_selection(chat_id, text, message_thread_id=None):
    if text == '4':
        if chat_id in waiting_for_department:
            del waiting_for_department[chat_id]
        if chat_id in user_department:
            del user_department[chat_id]
        waiting_for_teacher_dept[chat_id] = True
        bot.send_message(
            chat_id,
            "🧑‍🏫 Регистрация учителя.\nВыберите ваше отделение:\n1 - Первое\n2 - Второе\n3 - Третье",
            message_thread_id=message_thread_id)
    elif text in ('1', '2', '3'):
        user_department[chat_id] = int(text)
        if chat_id in waiting_for_department:
            del waiting_for_department[chat_id]
        dept = int(text)
        groups = [k for k, v in GROUP_NAME_TO_ID.items() if v[0] == dept]
        bot.send_message(
            chat_id,
            f"Выбрано отделение {dept}. Введите название группы:\n\n" +
            "\n".join(
                sorted(groups)),
            message_thread_id=message_thread_id)
    else:
        bot.send_message(
            chat_id,
            "Пожалуйста, выберите роль с помощью кнопок или введите 1, 2, 3 или 4.",
            message_thread_id=message_thread_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith('start_role_'))
def handle_start_role(call):
    chat_id = call.message.chat.id
    if chat_id not in waiting_for_department:
        return bot.answer_callback_query(call.id, "Меню устарело.")
    role_num = call.data.split('_')[-1]
    process_start_role_selection(
        chat_id, role_num, call.message.message_thread_id)
    try:
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, call.message.message_id)
    except BaseException:
        pass


@bot.message_handler(func=lambda m: True)
def handle_all(message):
    text = message.text.strip() if message.text else ""
    chat_id = message.chat.id

    # ====== Ожидание ввода дат для статистики ======
    if chat_id in waiting_for_stats_dates:
        if text.lower() in ('все', 'всё'):
            if chat_id in stats_context:
                stats_context[chat_id]['start_date'] = None
                stats_context[chat_id]['end_date'] = None
            del waiting_for_stats_dates[chat_id]
            reply_safe(message, "✅ Период сброшен. Выбрано всё время.")
            if chat_id in stats_context:
                show_target_stats_menu_by_chat_id(
                    chat_id, message.message_thread_id)
            return

        start, end = parse_date_range(text)
        if not start:
            reply_safe(
                message,
                "❌ Неверный формат дат. Введите диапазон, например: `15.06.2026 - 19.06.2026` или одну дату `15.06.2026` (или напишите `все` / `/cancel`).")
            return

        if chat_id in stats_context:
            stats_context[chat_id]['start_date'] = start
            stats_context[chat_id]['end_date'] = end

        del waiting_for_stats_dates[chat_id]
        reply_safe(message, f"✅ Установлен период: с {start} по {end}")
        if chat_id in stats_context:
            show_target_stats_menu_by_chat_id(
                chat_id, message.message_thread_id)
        return

    # ====== Регистрация учителя: выбор отделения ======
    if chat_id in waiting_for_teacher_dept:
        if text in ('1', '2', '3'):
            waiting_for_teacher_rooms[chat_id] = int(text)
            del waiting_for_teacher_dept[chat_id]
            bot.send_message(
                chat_id, "Введите номера ваших кабинетов через запятую.\nПример: 44, 12, 203")
        else:
            bot.send_message(chat_id, "Введите цифру 1, 2 или 3.")
        return

    # ====== Регистрация учителя: ввод кабинетов ======
    if chat_id in waiting_for_teacher_rooms:
        dept = waiting_for_teacher_rooms[chat_id]
        rooms_raw = [r.strip() for r in text.split(',') if r.strip()]
        if rooms_raw:
            u = message.from_user
            teacher_name = (u.first_name or "") + \
                (f" {u.last_name}" if u.last_name else "")
            username_str = f" (@{u.username})" if u.username else ""
            status = 'approved' if chat_id in APPROVED_TEACHER_IDS else 'pending'
            conn = sqlite3.connect(DB_FILE)
            conn.execute(
                "INSERT OR REPLACE INTO teachers (chat_id, department, rooms, name, status) VALUES (?, ?, ?, ?, ?)",
                (chat_id, dept, json.dumps(rooms_raw,
                 ensure_ascii=False), teacher_name, status)
            )
            conn.commit()
            conn.close()
            del waiting_for_teacher_rooms[chat_id]

            if status == 'approved':
                reply_safe(
                    message,
                    "✅ Вы успешно зарегистрированы как учитель! Доступные команды:\n/r, /db, /now, /next, /time, /f, /list")
            else:
                reply_safe(
                    message,
                    "⏳ Заявка отправлена на проверку модератору.\nОжидайте одобрения — вы получите уведомление.")
                # Уведомляем модератора с inline-кнопками
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(
                    telebot.types.InlineKeyboardButton(
                        "✅ Одобрить", callback_data=f"approve_teacher_{chat_id}"),
                    telebot.types.InlineKeyboardButton(
                        "❌ Отклонить", callback_data=f"deny_teacher_{chat_id}")
                )
                mod_text = (
                    f"🧑‍🏫 Заявка учителя\n"
                    f"Имя: {teacher_name}{username_str}\n"
                    f"ID: {chat_id}\n"
                    f"Отделение: {dept}\n"
                    f"Кабинеты: {', '.join(rooms_raw)}"
                )
                try:
                    for mod_id in MODERATOR_IDS:
                        try:
                            bot.send_message(
                                mod_id, mod_text, reply_markup=markup)
                        except Exception as e:
                            logger.error(
                                f"Failed to notify moderator {mod_id}: {e}")
                except Exception as e:
                    logger.error(f"Failed to notify moderators: {e}")
        else:
            bot.send_message(
                chat_id, "Введите хотя бы один номер кабинета через запятую.")
        return

    # ====== Выбор отделения / роли при /start ======
    if chat_id in waiting_for_department:
        process_start_role_selection(
            chat_id, text, getattr(
                message, 'message_thread_id', None))
        return

    if chat_id in user_department:
        dept = user_department[chat_id]
        input_group = text.upper()
        clean_input = input_group.replace('-', ' ').replace('_', ' ')
        found_name = None
        found_gid = None
        # Сначала ищем точное совпадение
        for k, v in GROUP_NAME_TO_ID.items():
            if v[0] == dept and (clean_input == k.upper().replace(
                    '-', ' ') or input_group == k.upper()):
                found_name = k
                found_gid = v[1]
                break
        # Если не нашли — ищем по частичному вхождению
        if not found_name:
            for k, v in GROUP_NAME_TO_ID.items():
                if v[0] == dept and (clean_input in k.upper().replace(
                        '-', ' ') or input_group in k.upper()):
                    found_name = k
                    found_gid = v[1]
                    break

        if found_name:
            mid = f"{chat_id}_{dept}_{found_gid}"
            monitor_manager.active_monitors[mid] = {
                "chat_id": chat_id, "group_id": found_gid,
                "group_name": found_name, "department": dept,
                "message_thread_id": getattr(message, 'message_thread_id', None)
            }
            monitor_manager.save()
            del user_department[chat_id]
            reply_safe(message, f"✅ {found_name} (отделение {dept}) активна!")
        else:
            groups = [k for k, v in GROUP_NAME_TO_ID.items() if v[0] == dept]
            bot.send_message(
                chat_id,
                "Группа не найдена. Список:\n" +
                "\n".join(
                    sorted(groups)))
        return

    clean_text = text.upper().replace('-', ' ').replace('_', ' ')
    for k, v in GROUP_NAME_TO_ID.items():
        if clean_text == k.upper().replace('-', ' ') or text.upper() == k.upper():
            dept, gid = v[0], v[1]
            mid = f"{chat_id}_{dept}_{gid}"
            monitor_manager.active_monitors[mid] = {
                "chat_id": chat_id, "group_id": gid,
                "group_name": k, "department": dept,
                "message_thread_id": getattr(message, 'message_thread_id', None)
            }
            monitor_manager.save()
            return reply_safe(message, f"✅ {k} активна!")

    if chat_id != LOG_GROUP_ID:
        try:
            bot.forward_message(LOG_GROUP_ID, chat_id, message.message_id)
        except BaseException:
            pass


# ====== КОМАНДЫ СТАТИСТИКИ И ГРАФИКОВ ======

def cmd_stats(message):
    bot.send_chat_action(message.chat.id, 'typing')
    text_args = message.text.replace('/stats', '', 1).strip()

    # Parse dates from text_args
    start_date, end_date = parse_date_range(text_args)
    clean_args = text_args
    if start_date:
        clean_args = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', clean_args).strip()
        clean_args = re.sub(r'[\s\-—]+$', '', clean_args).strip()
        clean_args = re.sub(r'^[\s\-—]+', '', clean_args).strip()

    target_type = None  # 'group', 'teacher', 'room'
    target_id = None
    target_name = None
    dept = None

    tokens = clean_args.split()
    if tokens:
        first = tokens[0].lower()
        if first in ['учитель', 'teacher']:
            name_query = " ".join(tokens[1:]).strip()
            if not name_query:
                return reply_safe(message, wrap_code(
                    "❌ Укажите имя преподавателя.\nПример: /stats учитель Hhh"))

            conn = sqlite3.connect(DB_FILE)
            res = conn.execute(
                "SELECT chat_id, name, department, rooms FROM teachers WHERE name LIKE ? AND status='approved'",
                (f"%{name_query}%",
                 )).fetchall()
            conn.close()
            if not res:
                return reply_safe(message, wrap_code(
                    f"❌ Преподаватель '{name_query}' не найден или не одобрен."))
            elif len(res) > 1:
                match_list = "\n".join([f"- {r[1]} (отд.{r[2]})" for r in res])
                return reply_safe(message, wrap_code(
                    f"🔍 Найдено несколько преподавателей:\n{match_list}\nУточните запрос."))

            teacher_chat_id, target_name, dept, rooms_json = res[0]
            target_id = json.loads(rooms_json)
            target_type = 'teacher'
        elif first in ['каб', 'room', 'кабинет']:
            room_query = " ".join(tokens[1:]).strip()
            if not room_query:
                return reply_safe(message, wrap_code(
                    "❌ Укажите номер кабинета.\nПример: /stats каб 44"))
            target_id = [room_query]
            target_name = f"Кабинет {room_query}"
            target_type = 'room'
            mons = monitor_manager.get_user_monitors(message.chat.id)
            dept = mons[0]['department'] if mons else 1
        else:
            group_query = clean_args.upper()
            clean_query = group_query.replace('-', ' ').replace('_', ' ')
            group_info = None

            for k, v in GROUP_NAME_TO_ID.items():
                if clean_query == k.upper().replace('-', ' ') or group_query == k.upper():
                    group_info = v
                    target_name = k
                    break
            if not group_info:
                for k, v in GROUP_NAME_TO_ID.items():
                    if clean_query in k.upper().replace('-', ' ').split():
                        group_info = v
                        target_name = k
                        break

            if group_info:
                dept, target_id = group_info[0], group_info[1]
                target_type = 'group'
            else:
                return reply_safe(message, wrap_code(
                    f"❌ Группа или команда '{clean_args}' не распознана."))
    else:
        if is_teacher(message.chat.id):
            dept, rooms = get_teacher_info(message.chat.id)
            target_id = rooms
            conn = sqlite3.connect(DB_FILE)
            row = conn.execute(
                "SELECT name FROM teachers WHERE chat_id=?",
                (message.chat.id,
                 )).fetchone()
            conn.close()
            target_name = row[0] if row else "Моя нагрузка"
            target_type = 'teacher'
        else:
            mons = monitor_manager.get_user_monitors(message.chat.id)
            if mons:
                dept, target_id = mons[0]['department'], mons[0]['group_id']
                target_name = mons[0]['group_name']
                target_type = 'group'
            else:
                return show_general_stats_menu(message)

    # Инициализируем контекст сессии для чата
    stats_context[message.chat.id] = {
        'target_type': target_type,
        'target_id': target_id,
        'target_name': target_name,
        'dept': dept,
        'start_date': start_date,
        'end_date': end_date
    }

    show_target_stats_menu_by_chat_id(
        message.chat.id, message.message_thread_id)


def show_general_stats_menu(message):
    title_msg = (
        "📊 *Статистика*\n\n"
        "Вы не подписаны ни на одну группу. Укажите цель для отчёта в аргументах или посмотрите общую загруженность пар.\n\n"
        "*Примеры:* \n"
        "• `/stats ИС-41-22` — статистика группы\n"
        "• `/stats каб 44` — статистика кабинета\n"
        "• `/stats учитель ФИО` — статистика преподавателя\n"
        "• `/stats 15.06.2026-19.06.2026` — с фильтрацией дат\n\n"
        "Показать общую статистику пар?"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🕒 Загруженность пар в колледже",
            callback_data="stats_general_time")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "❌ Закрыть", callback_data="stats_close")
    )
    bot.send_message(
        message.chat.id,
        title_msg,
        reply_markup=markup,
        parse_mode='Markdown',
        message_thread_id=message.message_thread_id)


def show_target_stats_menu_by_chat_id(chat_id, message_thread_id=None):
    ctx = stats_context.get(chat_id)
    if not ctx:
        return

    target_type = ctx['target_type']
    target_name = ctx['target_name']
    start_date = ctx['start_date']
    end_date = ctx['end_date']

    period_str = "все время"
    if start_date and end_date:
        if start_date == end_date:
            period_str = start_date
        else:
            period_str = f"{start_date} - {end_date}"

    title_msg = f"📊 Статистика: {target_name}\n📅 Период: {period_str}\n\nВыберите тип отчета:"

    markup = telebot.types.InlineKeyboardMarkup()
    if target_type == 'group':
        markup.add(
            telebot.types.InlineKeyboardButton(
                "📚 По предметам", callback_data="stats_view_subj"),
            telebot.types.InlineKeyboardButton(
                "📅 Нагрузка по дням", callback_data="stats_view_daily")
        )
    elif target_type in ('teacher', 'room'):
        markup.add(
            telebot.types.InlineKeyboardButton(
                "📚 По предметам", callback_data="stats_view_subj"),
            telebot.types.InlineKeyboardButton(
                "📅 Нагрузка по дням", callback_data="stats_view_daily")
        )
        markup.add(
            telebot.types.InlineKeyboardButton(
                "👥 По группам", callback_data="stats_view_groups")
        )

    markup.add(
        telebot.types.InlineKeyboardButton(
            "🕒 Загруженность пар",
            callback_data="stats_view_time")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "📅 Выбрать период", callback_data="stats_view_dates"),
        telebot.types.InlineKeyboardButton(
            "❌ Закрыть", callback_data="stats_close")
    )

    bot.send_message(
        chat_id,
        title_msg,
        reply_markup=markup,
        message_thread_id=message_thread_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith('stats_'))
def handle_stats_callbacks(call):
    chat_id = call.message.chat.id
    action = call.data

    if action == 'stats_close':
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except BaseException:
            pass
        if chat_id in stats_context:
            del stats_context[chat_id]
        if chat_id in waiting_for_stats_dates:
            del waiting_for_stats_dates[chat_id]
        bot.answer_callback_query(call.id)
        return

    if action == 'stats_general_time':
        bot.answer_callback_query(call.id, "Генерирую график...")
        buf = generate_time_distribution_chart()
        if buf:
            bot.send_photo(
                chat_id,
                buf,
                caption="🕒 Общая загруженность учебных пар в колледже",
                message_thread_id=call.message.message_thread_id)
        else:
            bot.send_message(chat_id, wrap_code(
                "❌ Нет данных для построения графика."))
        return

    ctx = stats_context.get(chat_id)
    if not ctx:
        bot.answer_callback_query(
            call.id, "❌ Сессия истекла. Введите /stats заново.")
        return

    target_type = ctx['target_type']
    target_id = ctx['target_id']
    target_name = ctx['target_name']
    dept = ctx['dept']
    start_date = ctx['start_date']
    end_date = ctx['end_date']

    if action == 'stats_view_dates':
        waiting_for_stats_dates[chat_id] = True
        prompt = (
            "📅 *Выбор периода*\n\n"
            "Введите диапазон дат в формате `ДД.ММ.ГГГГ - ДД.ММ.ГГГГ` или одну дату `ДД.ММ.ГГГГ`:\n"
            "Пример: `15.06.2026 - 19.06.2026`\n\n"
            "Напишите `все`, чтобы сбросить фильтр дат.\n"
            "Или напишите `/cancel` для отмены."
        )
        try:
            bot.edit_message_text(
                prompt,
                chat_id,
                call.message.message_id,
                parse_mode='Markdown')
        except BaseException:
            reply_safe(call.message, prompt)
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id, "Строю график...")
    buf = None
    caption_str = ""

    period_str = "за все время"
    if start_date and end_date:
        if start_date == end_date:
            period_str = f"за {start_date}"
        else:
            period_str = f"с {start_date} по {end_date}"

    if action == 'stats_view_subj':
        if target_type == 'group':
            buf = generate_group_subject_chart(
                target_id, dept, target_name, start_date, end_date, chat_id)
            caption_str = f"📚 Распределение учебных часов по предметам для группы {target_name} {period_str}"
        elif target_type in ('teacher', 'room'):
            buf = generate_teacher_subjects_chart(
                target_name, target_id, dept, start_date, end_date, chat_id)
            caption_str = f"📚 Распределение учебных часов по предметам для {target_name} {period_str}"

    elif action == 'stats_view_daily':
        if target_type == 'group':
            buf = generate_group_daily_chart(
                target_id, dept, target_name, start_date, end_date)
            caption_str = f"📅 Учебная нагрузка по дням для группы {target_name} {period_str}"
        elif target_type in ('teacher', 'room'):
            buf = generate_teacher_daily_chart(
                target_name, target_id, dept, start_date, end_date)
            caption_str = f"📅 Учебная нагрузка по дням для {target_name} {period_str}"

    elif action == 'stats_view_groups':
        if target_type in ('teacher', 'room'):
            buf = generate_teacher_groups_chart(
                target_name, target_id, dept, start_date, end_date)
            caption_str = f"👥 Распределение часов по группам для {target_name} {period_str}"

    elif action == 'stats_view_time':
        buf = generate_time_distribution_chart(dept, start_date, end_date)
        caption_str = f"🕒 Распределение занятий по парам {period_str} (отд. {dept})"

    if buf:
        bot.send_photo(chat_id, buf, caption=caption_str,
                       message_thread_id=call.message.message_thread_id)
    else:
        reply_safe(call.message, wrap_code(
            f"❌ Нет данных для графика за указанный период ({period_str})."))


if __name__ == '__main__':
    load_groups_cache()
    init_db()
    threading.Thread(target=background_group_updater, daemon=True).start()
    threading.Thread(target=check_loop, daemon=True).start()
    threading.Thread(target=morning_broadcast, daemon=True).start()
    
    # Start PWA/API Web Server
    import api_server
    threading.Thread(target=api_server.start_server, daemon=True).start()
    
    init_time = time.perf_counter() - _kalich_start_time
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Инициализация кода и баз данных завершена за {init_time:.3f} сек.")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Бот запущен в бессмертном режиме.")
    print(f"Групп в кэше: {len(GROUP_NAME_TO_ID)}")
    while True:
        try:
            bot.polling(non_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling error: {e}")
            time.sleep(10)
