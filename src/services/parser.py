import os
import re
import json
import time
import random
import logging
import threading
from bs4 import BeautifulSoup
import src.config as config
from src.config import (
    GROUPS_CACHE_FILE,
    SYSTEM_FILTERS,
)
from src.database import extract_room, get_db_connection, db_transaction

_LAST_PARSER_REQUEST_TIME = 0.0
_PARSER_LOCK = threading.Lock()
_PARSER_MIN_INTERVAL = 0.2  # Минимальный интервал между запросами к Gloris (Phase 3.3)


def requests_get_no_proxy(*args, **kwargs):
    """Обёртка с ограничением частоты запросов (Rate Limiting) к сайту колледжа."""
    global _LAST_PARSER_REQUEST_TIME
    with _PARSER_LOCK:
        elapsed = time.time() - _LAST_PARSER_REQUEST_TIME
        if elapsed < _PARSER_MIN_INTERVAL:
            time.sleep(_PARSER_MIN_INTERVAL - elapsed)
        _LAST_PARSER_REQUEST_TIME = time.time()
    return config.requests_get_no_proxy(*args, **kwargs)


logger = logging.getLogger(__name__)

# Базовый словарь групп 3 отделения
DEFAULT_DEPARTMENT_3_GROUPS = {
    "Э 11-26": 54,
    "МЭП 11-26": 55,
    "МПО 11-26": 56,
    "ОМНС 11-26": 58,
    "РПО 11-26": 59,
    "СЛ 11-26": 60,
    "ТЭ 11-26": 61,
    "ТМ 11-26": 62,
    "Э 21-25": 45,
    "ИС 21-25": 46,
    "МЭП 21-25": 47,
    "МП 21-25": 48,
    "МПО 21-25": 49,
    "ОНМС 21-25": 50,
    "П 21-25": 51,
    "СЛ 21-25": 52,
    "ТМ 21-25": 53,
    "МРА 21-25": 63,
    "ИС 31-24": 36,
    "МЭП 31-24": 37,
    "П 31-24": 38,
    "СЛ 31-24": 39,
    "ТМ 31-24": 42,
    "ИС 41-23": 29,
    "П 41-23": 30,
    "ТЭ 41-23": 33
}

# Глобальные структуры для маппинга групп
GROUP_NAME_TO_ID = {name: [3, gid] for name, gid in DEFAULT_DEPARTMENT_3_GROUPS.items()}
GROUP_ID_TO_NAME = {1: {}, 2: {}, 3: {}}


def build_reverse_group_dict():
    global GROUP_ID_TO_NAME
    GROUP_ID_TO_NAME = {1: {}, 2: {}, 3: {}}
    for name, data in GROUP_NAME_TO_ID.items():
        if isinstance(data, list) and len(data) == 2:
            dep, gid = data
            if dep in GROUP_ID_TO_NAME:
                GROUP_ID_TO_NAME[dep][gid] = name
        elif isinstance(data, int):
            GROUP_ID_TO_NAME[3][data] = name


build_reverse_group_dict()


def load_groups_cache():
    global GROUP_NAME_TO_ID
    # Сначала пытаемся загрузить из SQLite (Phase 2.2)
    try:
        conn = get_db_connection()
        cur = conn.execute("SELECT group_name, department, group_id FROM groups_cache")
        rows = cur.fetchall()
        conn.close()
        if rows:
            loaded = {}
            for name, dep, gid in rows:
                loaded[name] = [dep, gid]
            GROUP_NAME_TO_ID = loaded
            build_reverse_group_dict()
            return
    except Exception as e:
        logger.debug(f"Could not load groups cache from SQLite: {e}")

    # Fallback из JSON-файла и миграция в SQLite
    if os.path.exists(GROUPS_CACHE_FILE):
        try:
            with open(GROUPS_CACHE_FILE, 'r', encoding='utf-8') as f:
                GROUP_NAME_TO_ID = json.load(f)
            build_reverse_group_dict()
            if GROUP_NAME_TO_ID:
                try:
                    with db_transaction() as conn:
                        for gname, info in GROUP_NAME_TO_ID.items():
                            if isinstance(info, list) and len(info) >= 2:
                                conn.execute("INSERT OR REPLACE INTO groups_cache (group_name, department, group_id) VALUES (?, ?, ?)", (gname, info[0], info[1]))
                            elif isinstance(info, int):
                                conn.execute("INSERT OR REPLACE INTO groups_cache (group_name, department, group_id) VALUES (?, ?, ?)", (gname, 3, info))
                except Exception as e:
                    logger.debug(f"Failed to migrate groups cache to DB: {e}")
        except Exception as e:
            logger.error(f"Error loading groups cache: {e}")
    if not GROUP_NAME_TO_ID:
        update_groups_cache()


def update_groups_cache():
    global GROUP_NAME_TO_ID
    new_cache = dict(GROUP_NAME_TO_ID)
    headers = {'User-Agent': 'Mozilla/5.0'}
    updated = False
    for dep in [1, 2, 3]:
        url = f"https://xn----{dep}-iddzneycrmpn.xn--p1ai/lesson_table_show/"
        try:
            r = requests_get_no_proxy(url, timeout=10, verify=False, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = str(a['href'])
                    match = re.search(r'group_id=(\d+)', href)
                    if match:
                        try:
                            gid = int(match.group(1))
                            gname = a.get_text(strip=True).replace('*', '').strip()
                            if gname and gname.upper() not in [
                                "ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"
                            ]:
                                new_cache[gname] = [dep, gid]
                                updated = True
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Update groups cache failed for dep {dep}: {e}")

    if updated or new_cache:
        GROUP_NAME_TO_ID = new_cache
        build_reverse_group_dict()

        # Сохранение в SQLite (Phase 2.2)
        try:
            with db_transaction() as conn:
                conn.execute("DELETE FROM groups_cache")
                for gname, info in new_cache.items():
                    if isinstance(info, list) and len(info) >= 2:
                        conn.execute("INSERT OR REPLACE INTO groups_cache (group_name, department, group_id) VALUES (?, ?, ?)", (gname, info[0], info[1]))
                    elif isinstance(info, int):
                        conn.execute("INSERT OR REPLACE INTO groups_cache (group_name, department, group_id) VALUES (?, ?, ?)", (gname, 3, info))
        except Exception as e:
            logger.error(f"Failed to save groups cache to SQLite: {e}")

        # Обратная совместимость с JSON
        try:
            os.makedirs(os.path.dirname(GROUPS_CACHE_FILE), exist_ok=True)
            with open(GROUPS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(new_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save groups cache: {e}")
    return GROUP_NAME_TO_ID


def get_groups(force_refresh=False):
    if force_refresh or not GROUP_NAME_TO_ID:
        update_groups_cache()
    return GROUP_NAME_TO_ID


def find_group_info(target_group):
    """Динамический поиск группы: точное совпадение, нормализованное, по подстроке.
    Если группа не найдена в текущем кэше, выполняет запрос к Глорису для поиска новых групп."""
    if not GROUP_NAME_TO_ID:
        update_groups_cache()

    target = str(target_group).strip()
    clean_target = re.sub(r'[\s\-_]+', ' ', target).strip().upper()
    compact_target = re.sub(r'[\s\-_]+', '', target).upper()

    def _match():
        # 1. Точное совпадение
        for k, v in GROUP_NAME_TO_ID.items():
            info = v if isinstance(v, list) else [3, v]
            if target.upper() == k.upper():
                return k, info
        # 2. Нормализованное совпадение (пробелы и дефисы)
        for k, v in GROUP_NAME_TO_ID.items():
            info = v if isinstance(v, list) else [3, v]
            k_clean = re.sub(r'[\s\-_]+', ' ', k).strip().upper()
            if clean_target == k_clean:
                return k, info
        # 3. Компактное совпадение (без знаков)
        for k, v in GROUP_NAME_TO_ID.items():
            info = v if isinstance(v, list) else [3, v]
            k_compact = re.sub(r'[\s\-_]+', '', k).upper()
            if compact_target == k_compact:
                return k, info
        # 4. По словам
        for k, v in GROUP_NAME_TO_ID.items():
            info = v if isinstance(v, list) else [3, v]
            k_clean = re.sub(r'[\s\-_]+', ' ', k).strip().upper()
            if clean_target in k_clean.split():
                return k, info
        return None, None

    k, v = _match()
    if not v:
        update_groups_cache()
        k, v = _match()
    return k, v


def get_department_groups(dept):
    if not GROUP_NAME_TO_ID:
        update_groups_cache()
    groups = [k for k, v in GROUP_NAME_TO_ID.items() if (v[0] if isinstance(v, list) else 3) == dept]
    if not groups:
        update_groups_cache()
        groups = [k for k, v in GROUP_NAME_TO_ID.items() if (v[0] if isinstance(v, list) else 3) == dept]
    return sorted(groups)


def fetch_lessons(day, group_id, department):
    try:
        v = random.randint(1, 999999)
        url = f"https://xn----{department}-iddzneycrmpn.xn--p1ai/lesson_table_show/?day={day}&group_id={group_id}&v={v}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests_get_no_proxy(url, timeout=15, verify=False, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        lessons = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 1]
        filters = SYSTEM_FILTERS.get(department, SYSTEM_FILTERS[3])
        return [l for l in lessons if not any(x in l for x in filters)]
    except Exception as e:
        logger.error(f"Error fetching lessons: {e}")
        return None


def background_group_updater():
    while True:
        update_groups_cache()
        time.sleep(3600)
