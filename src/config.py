import os
import urllib.request
import urllib3
import requests
from datetime import datetime, timezone, timedelta
from typing import cast, Any
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ====== ЧАСОВОЙ ПОЯС (MSK, UTC+3) ======
try:
    from zoneinfo import ZoneInfo
    MSK_TZ = ZoneInfo("Europe/Moscow")
except Exception:
    MSK_TZ = timezone(timedelta(hours=3))


def now_msk() -> datetime:
    """Возвращает текущую дату и время по московскому времени (MSK, UTC+3)."""
    try:
        return datetime.now(MSK_TZ).replace(tzinfo=None)
    except Exception:
        return datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)


def requests_get_no_proxy(*args, **kwargs):
    s = requests.Session()
    s.trust_env = False
    return s.get(*args, **kwargs)


# ====== ПУТИ К ФАЙЛАМ ======
DATA_DIR = os.getenv('DATA_DIR', 'data')
MONITORS_FILE = os.getenv('MONITORS_FILE', os.path.join(DATA_DIR, 'active_monitors.json'))
CUSTOM_NAMES_FILE = os.getenv('CUSTOM_NAMES_FILE', os.path.join(DATA_DIR, 'custom_names.json'))
GROUPS_CACHE_FILE = os.getenv('GROUPS_CACHE_FILE', os.path.join(DATA_DIR, 'groups_cache.json'))
DB_FILE = os.getenv('DB_FILE', os.path.join(DATA_DIR, 'schedules.db'))

# ====== ТОКЕНЫ И ДОСТУПЫ ======
BOT_TOKEN = os.getenv('BOT_TOKEN') or ""

MODERATOR_IDS = []
mod_ids_env = os.getenv('MODERATOR_ID')
if mod_ids_env:
    for item in mod_ids_env.split(','):
        try:
            MODERATOR_IDS.append(int(item.strip()))
        except ValueError:
            pass
MODERATOR_ID = MODERATOR_IDS[0] if MODERATOR_IDS else None
try:
    LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID') or 0)
except ValueError:
    LOG_GROUP_ID = 0


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

# Глобальные кэши и состояния
SCHEDULE_CACHE = {}
waiting_for_department = {}     # chat_id -> ожидание ввода отделения
user_department = {}            # chat_id -> выбранное отделение
waiting_for_teacher_dept = {}   # chat_id -> True
waiting_for_teacher_rooms = {}  # chat_id -> dept
waiting_for_move = {}           # chat_id -> dict
waiting_for_stats_dates = {}    # chat_id -> True
stats_context = {}              # chat_id -> dict
