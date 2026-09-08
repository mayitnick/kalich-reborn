import os
import re
import json
import sqlite3
import logging
from datetime import datetime, timedelta
import src.config as config
from src.config import (
    DB_FILE,
    MONITORS_FILE,
    CUSTOM_NAMES_FILE,
    APPROVED_TEACHER_IDS,
    SCHEDULE_CACHE
)

logger = logging.getLogger(__name__)


def get_db_connection():
    """Создает соединение с SQLite базой с включенным WAL и таймаутом занятости."""
    os.makedirs(os.path.dirname(config.DB_FILE), exist_ok=True)
    conn = sqlite3.connect(config.DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db():
    conn = get_db_connection()
    # Таблица для стикеров (для совместимости)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS item_stickers (chat_id INTEGER, item_key TEXT, sticker_id TEXT, PRIMARY KEY (chat_id, item_key))'
    )

    # Таблица для уведомлений
    conn.execute('''CREATE TABLE IF NOT EXISTS user_notifications
                    (chat_id INTEGER, department INTEGER, group_id INTEGER, day INTEGER,
                     last_msg_hash TEXT, PRIMARY KEY (chat_id, department, group_id, day))''')

    # Таблица schedules (кэш текущей недели)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'")
    if cursor.fetchone():
        pragma = conn.execute("PRAGMA table_info(schedules)").fetchall()
        columns = [col[1] for col in pragma]
        if 'department' not in columns:
            conn.execute(
                'CREATE TABLE schedules_new (group_id INTEGER, day INTEGER, content_hash TEXT, lessons_text TEXT, department INTEGER, PRIMARY KEY (group_id, day, department))'
            )
            conn.execute(
                'INSERT INTO schedules_new (group_id, day, content_hash, lessons_text, department) SELECT group_id, day, content_hash, lessons_text, 3 FROM schedules'
            )
            conn.execute('DROP TABLE schedules')
            conn.execute('ALTER TABLE schedules_new RENAME TO schedules')
            conn.commit()
    else:
        conn.execute('CREATE TABLE schedules (group_id INTEGER, day INTEGER, content_hash TEXT, lessons_text TEXT, department INTEGER, PRIMARY KEY (group_id, day, department))')
        conn.commit()

    # Исторический архив по датам
    conn.execute('''CREATE TABLE IF NOT EXISTS schedule_history
                    (group_id INTEGER, department INTEGER, date TEXT,
                     content_hash TEXT, lessons_text TEXT,
                     PRIMARY KEY (group_id, department, date))''')

    # Таблица учителей (статус: pending / approved)
    conn.execute('''CREATE TABLE IF NOT EXISTS teachers
                    (chat_id INTEGER PRIMARY KEY, department INTEGER, rooms TEXT,
                     name TEXT, status TEXT DEFAULT 'pending')''')

    # Таблица замен преподавателей
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

    # Пользовательские настройки
    conn.execute('''CREATE TABLE IF NOT EXISTS user_settings
                    (chat_id INTEGER PRIMARY KEY, notifications INTEGER DEFAULT 1, voice_alerts INTEGER DEFAULT 0)''')
    try:
        conn.execute("ALTER TABLE user_settings ADD COLUMN fluffy_mode INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE user_settings ADD COLUMN voice_effect TEXT DEFAULT 'echo'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE teacher_room_overrides ADD COLUMN date TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


def save_schedule_to_db(department, group_id, day, content_hash, lessons_json, date_str):
    """Сохраняет расписание в текущий недельный кэш и в исторический архив по дате."""
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT OR REPLACE INTO schedules (group_id, day, content_hash, lessons_text, department) VALUES (?, ?, ?, ?, ?)",
            (group_id, day, content_hash, lessons_json, department)
        )
        conn.execute(
            "INSERT OR REPLACE INTO schedule_history (group_id, department, date, content_hash, lessons_text) VALUES (?, ?, ?, ?, ?)",
            (group_id, department, date_str, content_hash, lessons_json)
        )
        conn.commit()
        conn.close()
        SCHEDULE_CACHE.clear()
    except Exception as e:
        logger.error(f"Error saving schedule: {e}")


def get_all_schedules_for_day(day):
    """Извлекает расписание всех групп за указанный день недели."""
    if day in SCHEDULE_CACHE:
        return SCHEDULE_CACHE[day]
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT department, group_id, lessons_text FROM schedules WHERE day=?",
            (day,)
        ).fetchall()
        conn.close()
        data = {}
        for dep, gid, lessons_json in rows:
            try:
                lessons = json.loads(lessons_json)
                data[(dep, gid)] = lessons
            except Exception:
                continue
        SCHEDULE_CACHE[day] = data
        return data
    except Exception as e:
        logger.error(f"Error getting schedules: {e}")
        return {}


def get_schedule_history_for_date(date_str):
    """Извлекает расписание всех групп за конкретную дату YYYY-MM-DD."""
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT department, group_id, lessons_text FROM schedule_history WHERE date=?",
            (date_str,)
        ).fetchall()
        conn.close()
        data = {}
        for dep, gid, lessons_json in rows:
            try:
                data[(dep, gid)] = json.loads(lessons_json)
            except Exception:
                continue
        return data
    except Exception:
        return {}


def get_date_for_weekday(day_num):
    """Возвращает строку YYYY-MM-DD для указанного дня (1-7) текущей недели по МСК."""
    today = getattr(config, 'now_msk', datetime.now)()
    start_of_week = today - timedelta(days=today.weekday())
    target_date = start_of_week + timedelta(days=day_num - 1)
    return target_date.strftime("%Y-%m-%d")


def extract_room(lesson_text):
    """Извлекает содержимое между первой '(' и последней ')'."""
    if not lesson_text:
        return None
    first_open = str(lesson_text).find('(')
    if first_open == -1:
        return None
    last_close = str(lesson_text).rfind(')')
    if last_close == -1 or last_close < first_open:
        return None
    return str(lesson_text)[first_open + 1:last_close].strip()


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


# ====== ПРЕПОДАВАТЕЛИ И ЗАМЕНЫ ======

def is_teacher(chat_id):
    """Проверяет, одобрен ли пользователь как учитель."""
    conn = get_db_connection()
    res = conn.execute("SELECT status FROM teachers WHERE chat_id=?", (chat_id,)).fetchone()
    if res:
        status = res[0]
        if status == 'approved':
            conn.close()
            return True
        if chat_id in APPROVED_TEACHER_IDS:
            conn.execute("UPDATE teachers SET status='approved' WHERE chat_id=?", (chat_id,))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False


def get_teacher_info(chat_id):
    """Возвращает (department, rooms_list) для одобренного учителя."""
    conn = get_db_connection()
    res = conn.execute(
        "SELECT department, rooms FROM teachers WHERE chat_id=? AND status='approved'",
        (chat_id,)
    ).fetchone()
    conn.close()
    if res:
        return res[0], json.loads(res[1])
    return None, []


def apply_teacher_overrides(all_data, day, date_str=None):
    """Применяет замены учителя (кабинет/предмет) поверх расписания с сайта."""
    conn = get_db_connection()
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


def save_teacher_override(teacher_chat_id, department, day, slot_idx, group_id, new_room, new_subject, date_str=None):
    """Сохраняет или обновляет замену учителя. Ставит таймер уведомления на now+5min."""
    import time
    notify_after = time.time() + 300
    conn = get_db_connection()
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
        conn.execute(
            "UPDATE teacher_room_overrides SET new_room=?, new_subject=?, department=?, notify_after=?, date=? WHERE id=?",
            (new_room, new_subject, department, notify_after, date_str, existing[0])
        )
    else:
        conn.execute(
            "INSERT INTO teacher_room_overrides (teacher_chat_id, department, day, slot_idx, group_id, new_room, new_subject, notified, notify_after, date) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
            (teacher_chat_id, department, day, slot_idx, group_id, new_room, new_subject, notify_after, date_str)
        )
    conn.commit()
    conn.close()


# ====== НАСТРОЙКИ ПОЛЬЗОВАТЕЛЕЙ ======

def get_user_settings(chat_id):
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT notifications, voice_alerts, fluffy_mode, voice_effect FROM user_settings WHERE chat_id=?",
            (chat_id,)
        ).fetchone()
        conn.close()
        if row:
            return {
                'notifications': row[0],
                'voice_alerts': row[1],
                'fluffy_mode': row[2],
                'voice_effect': row[3] or 'echo'
            }
    except Exception:
        pass
    return {'notifications': 1, 'voice_alerts': 0, 'fluffy_mode': 0, 'voice_effect': 'echo'}


def set_user_setting(chat_id, key, value):
    try:
        conn = get_db_connection()
        conn.execute("INSERT OR IGNORE INTO user_settings (chat_id) VALUES (?)", (chat_id,))
        conn.execute(f"UPDATE user_settings SET {key}=? WHERE chat_id=?", (value, chat_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Settings err: {e}")


def save_item_sticker(chat_id, item_name, sticker_id):
    pass


def get_item_sticker(chat_id, raw_item_name):
    return None


# ====== МЕНЕДЖЕРЫ МОНИТОРОВ И КАСТОМНЫХ ИМЕН ======

class MonitorManager:
    def __init__(self):
        self.active_monitors = {}
        self.load()

    def load(self):
        if os.path.exists(MONITORS_FILE):
            try:
                with open(MONITORS_FILE, 'r', encoding='utf-8') as f:
                    self.active_monitors = json.load(f)
                for key, value in self.active_monitors.items():
                    if 'department' not in value:
                        value['department'] = 3
            except Exception:
                self.active_monitors = {}

    def save(self):
        os.makedirs(os.path.dirname(MONITORS_FILE), exist_ok=True)
        with open(MONITORS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.active_monitors, f, ensure_ascii=False, indent=2)

    def get_user_monitors(self, chat_id):
        return [m for m in self.active_monitors.values() if str(m["chat_id"]) == str(chat_id)]


class CustomNamesManager:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(CUSTOM_NAMES_FILE):
            try:
                with open(CUSTOM_NAMES_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        os.makedirs(os.path.dirname(CUSTOM_NAMES_FILE), exist_ok=True)
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
        if any(x in text for x in ["Spearhead", "Разработано", "$cript", "Глорис", "Расписание"]):
            return None
        cid = str(cid)
        room_match = re.search(r'(\s*\(?\d{2,4}[А-Яа-я]?\)?)$', text)
        room = room_match.group(1) if room_match else ""
        clean = re.sub(r'[^а-яА-Яa-zA-ZёЁ]', '', text.replace(room, "")).lower()
        if cid in self.data:
            for k, v in self.data[cid].items():
                if k in clean:
                    return f"{v}{room}"
        return text


monitor_manager = MonitorManager()
custom_names_manager = CustomNamesManager()


def get_teacher_schedule(chat_id, day, all_data, date_str=""):
    """Собирает расписание учителя по его кабинетам из данных всех групп."""
    from src.services.parser import GROUP_ID_TO_NAME
    dept, rooms = get_teacher_info(chat_id)
    if not rooms or dept is None:
        return None, [], []

    my_overrides_set = set()
    try:
        conn = get_db_connection()
        if date_str:
            cur = conn.execute(
                "SELECT slot_idx, group_id FROM teacher_room_overrides WHERE teacher_chat_id=? AND department=? AND day=? AND date=?",
                (chat_id, dept, day, date_str)
            )
        else:
            cur = conn.execute(
                "SELECT slot_idx, group_id FROM teacher_room_overrides WHERE teacher_chat_id=? AND department=? AND day=? AND (date IS NULL OR date='')",
                (chat_id, dept, day)
            )
        for row in cur.fetchall():
            my_overrides_set.add((row[0], row[1]))
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching overrides for get_teacher_schedule: {e}")

    max_slots = 10 if day == 1 else 8
    schedule = [[] for _ in range(max_slots)]
    for (dep, gid), lessons in all_data.items():
        if dep != dept:
            continue
        group_name = GROUP_ID_TO_NAME.get(dep, {}).get(gid, "?")
        for idx in range(min(len(lessons), max_slots)):
            l_str = str(lessons[idx])
            room = extract_room(l_str)

            is_my_room = room and any(r.strip() in room for r in rooms)
            is_my_override = (idx, gid) in my_overrides_set

            if is_my_room or is_my_override:
                subj = re.sub(r'\s*\(.*$', '', l_str).strip()
                schedule[idx].append((group_name, subj, room))

    for idx in range(max_slots):
        if not schedule[idx]:
            has_lunch = False
            for (dep, gid), lessons in all_data.items():
                if dep == dept:
                    if idx < len(lessons) and "обед" in str(lessons[idx]).lower():
                        has_lunch = True
                        break
            if has_lunch:
                schedule[idx].append(("", "ОБЕД", ""))

    return dept, rooms, schedule
