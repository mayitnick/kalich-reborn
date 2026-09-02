# pyrefly: ignore [missing-import]
import time
_kalich_start_time = time.perf_counter()

import io
import os
import re
import json
import random
import hashlib
import logging
import sqlite3
import telebot
import urllib3
import requests
import threading
import matplotlib
import collections
import urllib.request
from typing import cast, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
matplotlib.use('Agg')

import messages
from src.config import (
    DATA_DIR, MONITORS_FILE, CUSTOM_NAMES_FILE, GROUPS_CACHE_FILE, DB_FILE,
    BOT_TOKEN, MODERATOR_IDS, MODERATOR_ID, LOG_GROUP_ID, SPECIAL_CHATS,
    APPROVED_TEACHER_IDS, SYSTEM_FILTERS, CALLS, SCHEDULE_CACHE,
    waiting_for_department, user_department, waiting_for_teacher_dept,
    waiting_for_teacher_rooms, waiting_for_move, waiting_for_stats_dates,
    stats_context, requests_get_no_proxy
)
from src.database import (
    get_db_connection, init_db, save_schedule_to_db, get_all_schedules_for_day,
    get_schedule_history_for_date, get_date_for_weekday, extract_room,
    parse_date_range, is_teacher, get_teacher_info, get_teacher_schedule,
    apply_teacher_overrides, save_teacher_override, get_user_settings,
    set_user_setting, save_item_sticker, get_item_sticker,
    MonitorManager, CustomNamesManager, monitor_manager, custom_names_manager
)
from src.services.parser import (
    GROUP_NAME_TO_ID, GROUP_ID_TO_NAME, build_reverse_group_dict,
    load_groups_cache, get_groups, find_group_info,
    get_department_groups, fetch_lessons, background_group_updater
)
from src.services.analytics import (
    apply_chart_style, generate_group_subject_chart, generate_group_daily_chart,
    get_teacher_aggregated_data, generate_teacher_daily_chart,
    generate_teacher_groups_chart, generate_teacher_subjects_chart,
    get_time_distribution_stats, generate_time_distribution_chart
)
from src.services.notifier import (
    format_with_overlap, send_updates_for_day,
    send_teacher_override_notifications_for_day, teacher_notification_loop,
    morning_broadcast, check_loop, get_status
)
from src.bot.instance import bot, reply_safe, wrap_code, logger
from src.bot.keyboards import (
    get_start_roles_markup, get_settings_markup, get_teacher_approval_markup
)
from src.bot.handlers.teacher import (
    format_teacher_schedule, cmd_teacher_r, cmd_teacher_db,
    cmd_teacher_now, cmd_teacher_next
)
import sys
import src.config
import src.database
import src.services.parser
import src.services.notifier
import src.bot.instance

class _KalichModuleWrapper(sys.modules[__name__].__class__):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == 'DB_FILE':
            src.config.DB_FILE = value
            src.database.config.DB_FILE = value
        elif name == 'GROUP_NAME_TO_ID':
            src.services.parser.GROUP_NAME_TO_ID = value
            src.services.parser.build_reverse_group_dict()
            super().__setattr__('GROUP_ID_TO_NAME', src.services.parser.GROUP_ID_TO_NAME)
        elif name == 'GROUP_ID_TO_NAME':
            src.services.parser.GROUP_ID_TO_NAME = value
        elif name == 'requests_get_no_proxy':
            src.config.requests_get_no_proxy = value
        elif name == 'bot':
            src.bot.instance.bot = value
            src.services.notifier.bot = value

sys.modules[__name__].__class__ = _KalichModuleWrapper


def update_groups_cache():
    res = src.services.parser.update_groups_cache()
    kalich_mod = sys.modules.get('kalich') or sys.modules.get(__name__)
    if kalich_mod:
        kalich_mod.__dict__['GROUP_NAME_TO_ID'] = src.services.parser.GROUP_NAME_TO_ID
        kalich_mod.__dict__['GROUP_ID_TO_NAME'] = src.services.parser.GROUP_ID_TO_NAME
    return res

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


def _render_schedule_msg(message, monitor, all_data,
                         day, header_text, send_stickers=False):
    key = (monitor['department'], monitor['group_id'])
    lessons = all_data.get(key)
    if not lessons:
        return reply_safe(message, wrap_code(
            f"{header_text}\n\nНет пар или данных."))

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
        group_str = ' '.join(remaining)
        matched_name, group_info = find_group_info(group_str)
        if group_info:
            dept = group_info[0]
            group_id = group_info[1]
        else:
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


@bot.message_handler(commands=['flush'])
def cmd_flush(message):
    if message.from_user.id in MODERATOR_IDS:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM schedules")
        conn.commit()
        conn.close()
        reply_safe(message, "♻️ База очищена.")


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
              waiting_for_teacher_rooms, waiting_for_stats_dates):
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
    matched_name, group_info = find_group_info(target_group)
    if not group_info:
        return reply_safe(message, wrap_code(
            f"Группа {target_group} не найдена."))
    target_group = matched_name
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

# ====== РЕГИСТРАЦИЯ И ВЫБОР РОЛИ ======


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
        groups = get_department_groups(dept)
        bot.send_message(
            chat_id,
            f"Выбрано отделение {dept}. Введите название группы:\n\n" +
            "\n".join(groups),
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
        found_name, group_info = find_group_info(input_group)
        found_gid = None
        if group_info and group_info[0] == dept:
            found_gid = group_info[1]
        else:
            found_name = None
            for k, v in GROUP_NAME_TO_ID.items():
                if v[0] == dept and (clean_input in k.upper().replace(
                        '-', ' ') or input_group in k.upper()):
                    found_name = k
                    found_gid = v[1]
                    break

        if found_name and found_gid:
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
            groups = get_department_groups(dept)
            bot.send_message(
                chat_id,
                "Группа не найдена. Список:\n" +
                "\n".join(groups))
        return

    matched_k, group_info = find_group_info(text)
    if group_info:
        dept, gid = group_info[0], group_info[1]
        mid = f"{chat_id}_{dept}_{gid}"
        monitor_manager.active_monitors[mid] = {
            "chat_id": chat_id, "group_id": gid,
            "group_name": matched_k, "department": dept,
            "message_thread_id": getattr(message, 'message_thread_id', None)
        }
        monitor_manager.save()
        return reply_safe(message, f"✅ {matched_k} активна!")

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


# =================== TEACHER APPROVAL FLOW ===================
def send_teacher_approval_request(device_id, name, department, rooms):
    rooms_str = ", ".join(rooms) if rooms else "Не указаны"
    msg = (
        f"👨‍🏫 *Новая заявка на преподавателя*\n\n"
        f"Имя: {name}\n"
        f"Отделение: {department}\n"
        f"Кабинеты: {rooms_str}\n"
        f"Device ID: {device_id}\n\n"
        f"Одобрить или отклонить?"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"teacher_approve:{device_id}"),
        telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"teacher_reject:{device_id}")
    )
    
    for mod_id in MODERATOR_IDS:
        try:
            bot.send_message(mod_id, msg, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            print(f"Failed to send approval request to mod {mod_id}: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('teacher_'))
def handle_teacher_approval(call):
    chat_id = call.message.chat.id
    if chat_id not in MODERATOR_IDS:
        bot.answer_callback_query(call.id, "Нет прав!")
        return

    action, device_id_str = call.data.split(':')
    device_id = int(device_id_str)
    
    conn = sqlite3.connect(DB_FILE)
    if action == 'teacher_approve':
        conn.execute("UPDATE teachers SET status='approved' WHERE chat_id=?", (device_id,))
        bot.edit_message_text(f"✅ Заявка преподавателя ({device_id}) одобрена.", chat_id, call.message.message_id)
    elif action == 'teacher_reject':
        conn.execute("DELETE FROM teachers WHERE chat_id=?", (device_id,))
        bot.edit_message_text(f"❌ Заявка преподавателя ({device_id}) отклонена.", chat_id, call.message.message_id)
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id)

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
