import re
import time
import json
import hashlib
import logging
from datetime import datetime
from src.config import SPECIAL_CHATS, now_msk
from src.database import (
    get_db_connection,
    extract_room,
    get_all_schedules_for_day,
    get_date_for_weekday,
    save_schedule_to_db,
    monitor_manager,
    custom_names_manager
)
from src.services.parser import (
    GROUP_NAME_TO_ID,
    GROUP_ID_TO_NAME,
    fetch_lessons
)
from src.bot.instance import bot, wrap_code

logger = logging.getLogger(__name__)


def format_with_overlap(cid, department, gid, day, idx, raw_text, all_day_data):
    """Форматирует строку пары с учетом кастомных названий и совмещений кабинетов."""
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


def send_updates_for_day(day, data):
    """Отправляет уведомления об изменениях расписания (включая совмещения)."""
    conn = get_db_connection()
    for m in monitor_manager.active_monitors.values():
        dep = m['department']
        gid = m['group_id']
        key = (dep, gid)
        lessons = data.get(key)
        if not lessons:
            continue

        day_of_week = {
            1: "понедельник", 2: "вторник", 3: "среда",
            4: "четверг", 5: "пятница", 6: "суббота"
        }.get(day, "неизвестно")
        msg = f"📢 Обновление\n{m['group_name']} на {day_of_week}\n\n"
        cnt = 1
        for i, l in enumerate(lessons):
            lines = format_with_overlap(m['chat_id'], dep, gid, day, i, str(l), data)
            if not lines:
                continue
            if day == 1 and cnt == 1 and lines:
                lines[0] = lines[0] + " +К/Ч"
            msg += f"{cnt}. {lines[0]}\n"
            if len(lines) > 1:
                msg += f"   {lines[1]}\n"
            cnt += 1
        msg = msg.strip()
        msg_hash = hashlib.md5(msg.encode()).hexdigest()

        cur = conn.execute(
            "SELECT last_msg_hash FROM user_notifications WHERE chat_id=? AND department=? AND group_id=? AND day=?",
            (m['chat_id'], dep, gid, day)
        )
        row = cur.fetchone()
        thread_id = m.get('message_thread_id') or SPECIAL_CHATS.get(m['chat_id'])
        if row is None:
            try:
                bot.send_message(m['chat_id'], wrap_code(msg), parse_mode='Markdown', message_thread_id=thread_id)
                conn.execute(
                    "INSERT INTO user_notifications (chat_id, department, group_id, day, last_msg_hash) VALUES (?, ?, ?, ?, ?)",
                    (m['chat_id'], dep, gid, day, msg_hash)
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Error sending update: {e}")
        elif row[0] != msg_hash:
            try:
                bot.send_message(m['chat_id'], wrap_code(msg), parse_mode='Markdown', message_thread_id=thread_id)
                conn.execute(
                    "UPDATE user_notifications SET last_msg_hash=? WHERE chat_id=? AND department=? AND group_id=? AND day=?",
                    (msg_hash, m['chat_id'], dep, gid, day)
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Error sending update: {e}")
    conn.close()


def send_teacher_override_notifications_for_day(day):
    """Отправляет ученикам батч-уведомление об изменениях учителя (один раз на чат)."""
    now = time.time()
    conn = get_db_connection()
    pending = conn.execute(
        "SELECT id, department, slot_idx, group_id, new_room, new_subject FROM teacher_room_overrides "
        "WHERE notified=0 AND notify_after <= ? AND day=?",
        (now, day)
    ).fetchall()
    if not pending:
        conn.close()
        return

    affected = {}
    notified_ids = []
    all_data = get_all_schedules_for_day(day)
    for row_id, dep, slot_idx, group_id, new_room, new_subject in pending:
        notified_ids.append(row_id)
        if group_id == -1:
            for (d, gid) in all_data:
                if d == dep:
                    affected.setdefault((dep, gid), []).append((slot_idx, new_room, new_subject))
        else:
            affected.setdefault((dep, group_id), []).append((slot_idx, new_room, new_subject))

    day_of_week = {1: "понедельник", 2: "вторник", 3: "среда", 4: "четверг", 5: "пятница", 6: "суббота"}.get(day, "?")
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
            lines.append(f"{slot_idx + 1}. {' | '.join(parts) if parts else orig_subj}")
        msg = "\n".join(lines)
        try:
            thread_id = m.get('message_thread_id') or SPECIAL_CHATS.get(m['chat_id'])
            bot.send_message(m['chat_id'], wrap_code(msg), parse_mode='Markdown', message_thread_id=thread_id)
        except Exception as e:
            logger.error(f"Override notify error: {e}")

    for row_id in notified_ids:
        conn.execute("UPDATE teacher_room_overrides SET notified=1 WHERE id=?", (row_id,))
    conn.commit()
    conn.close()


def teacher_notification_loop():
    """Фоновый поток: каждую минуту ищет готовые к отправке уведомления об изменениях учителя."""
    while True:
        try:
            now = time.time()
            conn = get_db_connection()
            pending_days = conn.execute(
                "SELECT DISTINCT day FROM teacher_room_overrides WHERE notified=0 AND notify_after <= ?",
                (now,)
            ).fetchall()
            conn.close()
            for (d,) in pending_days:
                send_teacher_override_notifications_for_day(d)
        except Exception as e:
            logger.error(f"Teacher notify loop error: {e}")
        time.sleep(60)


def morning_broadcast():
    sent_today = False
    while True:
        try:
            now = now_msk()
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
                                lines = format_with_overlap(cid, m['department'], m['group_id'], day, i, str(l), data)
                                if not lines:
                                    continue
                                if day == 1 and cnt == 1 and lines:
                                    lines[0] = lines[0] + " +К/Ч"
                                res += f"{cnt}. {lines[0]}\n"
                                if len(lines) > 1:
                                    res += f"   {lines[1]}\n"
                                cnt += 1
                            try:
                                thread_id = m.get('message_thread_id') or SPECIAL_CHATS.get(cid)
                                bot.send_message(
                                    cid,
                                    wrap_code(res.strip()),
                                    parse_mode='Markdown',
                                    message_thread_id=thread_id
                                )
                            except Exception:
                                pass
                sent_today = True
            if now.hour == 8:
                sent_today = False
        except Exception:
            pass
        time.sleep(30)


def check_loop():
    while True:
        try:
            now = now_msk()
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

                    conn = get_db_connection()
                    old = conn.execute(
                        "SELECT content_hash FROM schedules WHERE group_id=? AND day=? AND department=?",
                        (gid, d, dep)
                    ).fetchone()
                    conn.close()

                    if not old or old[0] != h:
                        save_schedule_to_db(dep, gid, d, h, json.dumps(raw, ensure_ascii=False), date_str)
                        if is_silent:
                            continue
                        data = get_all_schedules_for_day(d)
                send_updates_for_day(d, data)
        except Exception as e:
            logger.error(f"Check loop error: {e}")
        time.sleep(600)


def get_status():
    """Определяет статус текущего занятия (work/rest), оставшееся время и индекс текущей пары."""
    from src.config import CALLS
    now = now_msk()
    curr = now.strftime("%H:%M")
    wd = now.isoweekday()
    if wd > 5:
        return "rest", None, None
    max_l = 10 if wd == 1 else 8
    last_call = CALLS[max_l - 1][1]
    if curr >= last_call:
        return "rest", None, None
    td = datetime.strptime(last_call, "%H:%M") - datetime.strptime(curr, "%H:%M")
    h, m = td.seconds // 3600, (td.seconds // 60) % 60
    t_str = f"{f'{h}ч ' if h > 0 else ''}{m}м"
    active_idx = next((i for i, c in enumerate(CALLS[:max_l]) if c[0] <= curr <= c[1]), None)
    return "work", t_str, active_idx
