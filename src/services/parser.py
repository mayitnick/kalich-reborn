import os
import re
import json
import time
import random
import logging
from bs4 import BeautifulSoup
import src.config as config
from src.config import (
    GROUPS_CACHE_FILE,
    SYSTEM_FILTERS,
)


def requests_get_no_proxy(*args, **kwargs):
    return config.requests_get_no_proxy(*args, **kwargs)


logger = logging.getLogger(__name__)

# Глобальные структуры для маппинга групп
GROUP_NAME_TO_ID = {}
GROUP_ID_TO_NAME = {1: {}, 2: {}, 3: {}}


def build_reverse_group_dict():
    global GROUP_ID_TO_NAME
    GROUP_ID_TO_NAME = {1: {}, 2: {}, 3: {}}
    for name, data in GROUP_NAME_TO_ID.items():
        if isinstance(data, list) and len(data) == 2:
            dep, gid = data
            GROUP_ID_TO_NAME[dep][gid] = name


def load_groups_cache():
    global GROUP_NAME_TO_ID
    if os.path.exists(GROUPS_CACHE_FILE):
        try:
            with open(GROUPS_CACHE_FILE, 'r', encoding='utf-8') as f:
                GROUP_NAME_TO_ID = json.load(f)
            build_reverse_group_dict()
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
            if target.upper() == k.upper():
                return k, v
        # 2. Нормализованное совпадение (пробелы и дефисы)
        for k, v in GROUP_NAME_TO_ID.items():
            k_clean = re.sub(r'[\s\-_]+', ' ', k).strip().upper()
            if clean_target == k_clean:
                return k, v
        # 3. Компактное совпадение (без знаков)
        for k, v in GROUP_NAME_TO_ID.items():
            k_compact = re.sub(r'[\s\-_]+', '', k).upper()
            if compact_target == k_compact:
                return k, v
        # 4. По словам
        for k, v in GROUP_NAME_TO_ID.items():
            k_clean = re.sub(r'[\s\-_]+', ' ', k).strip().upper()
            if clean_target in k_clean.split():
                return k, v
        return None, None

    k, v = _match()
    if not v:
        update_groups_cache()
        k, v = _match()
    return k, v


def get_department_groups(dept):
    if not GROUP_NAME_TO_ID:
        update_groups_cache()
    groups = [k for k, v in GROUP_NAME_TO_ID.items() if v[0] == dept]
    if not groups:
        update_groups_cache()
        groups = [k for k, v in GROUP_NAME_TO_ID.items() if v[0] == dept]
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
