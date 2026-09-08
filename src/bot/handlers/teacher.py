import re
from datetime import datetime
from src.config import DB_FILE, CALLS
from src.database import (
    get_db_connection,
    is_teacher,
    get_teacher_info,
    get_teacher_schedule,
    get_all_schedules_for_day,
    get_schedule_history_for_date,
    apply_teacher_overrides,
    save_teacher_override,
    extract_room
)
from src.services.parser import GROUP_ID_TO_NAME, find_group_info
from src.services.notifier import get_status
from src.bot.instance import bot, reply_safe, wrap_code


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
                        res_lines.append(f"   {', '.join(sorted(groups_clean))}")
    if not has_lessons:
        res_lines.append("Нет пар в ваших кабинетах.")
    return "\n".join(res_lines)


def cmd_teacher_r(message, day=None, label=None):
    """Выводит расписание учителя на указанный день."""
    if day is None:
        day = datetime.now().isoweekday()
    original_data = get_all_schedules_for_day(day)
    overridden_data = apply_teacher_overrides(original_data, day)

    dept, rooms = get_teacher_info(message.chat.id)
    if not rooms or dept is None:
        return reply_safe(message, "❌ Нет данных. Зарегистрируйтесь: /start")

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

    for idx in range(max_slots):
        if not schedule[idx]:
            has_lunch = False
            for (dep, gid), lessons in overridden_data.items():
                if dep == dept:
                    if idx < len(lessons) and "обед" in str(lessons[idx]).lower():
                        has_lunch = True
                        break
            if has_lunch:
                schedule[idx].append(("", "ОБЕД", ""))

    rooms_str = ', '.join(rooms)
    if label is None:
        day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
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
            target_date = datetime.strptime(args, "%d.%m.%Y").strftime("%Y-%m-%d")
            all_data = get_schedule_history_for_date(target_date)
            target_weekday = datetime.strptime(args, "%d.%m.%Y").isoweekday()
            if all_data:
                all_data = apply_teacher_overrides(all_data, target_weekday)
            if not all_data:
                return reply_safe(message, wrap_code(f"🗄 Нет данных в архиве за {args}"))
            target_weekday = datetime.strptime(args, "%d.%m.%Y").isoweekday()
            dept, rooms, schedule = get_teacher_schedule(message.chat.id, target_weekday, all_data)
            body = format_teacher_schedule(rooms, schedule, target_weekday)
            return reply_safe(message, wrap_code(f"🗄 Архив ({args}) | каб. {rooms_str}\n\n{body}"))
        except ValueError:
            return reply_safe(message, wrap_code("Неверный формат даты. Используйте ДД.ММ.ГГГГ"))

    # День недели /db пн
    if args in day_map:
        target_day = day_map[args]
        all_data = get_all_schedules_for_day(target_day)
        all_data = apply_teacher_overrides(all_data, target_day)
        dept, rooms, schedule = get_teacher_schedule(message.chat.id, target_day, all_data)
        body = format_teacher_schedule(rooms, schedule, target_day)
        return reply_safe(message, wrap_code(f"🗓 {day_labels[target_day]} | каб. {rooms_str}\n\n{body}"))

    # Классический /db (завтра)
    curr_day = datetime.now().isoweekday()
    next_day = 1 if curr_day >= 5 else curr_day + 1
    all_data = get_all_schedules_for_day(next_day)
    all_data = apply_teacher_overrides(all_data, next_day)
    dept, rooms, schedule = get_teacher_schedule(message.chat.id, next_day, all_data)
    body = format_teacher_schedule(rooms, schedule, next_day)
    reply_safe(message, wrap_code(f"📦 {day_labels[next_day]} | каб. {rooms_str}\n\n{body}"))


def cmd_teacher_now(message):
    """Показывает текущий урок учителя."""
    day = datetime.now().isoweekday()
    if day > 5:
        return reply_safe(message, wrap_code("Отдыхай (выходной)\n(Используй /db)") + "\n\n/db")

    all_data = get_all_schedules_for_day(day)
    all_data = apply_teacher_overrides(all_data, day)
    dept, rooms, schedule = get_teacher_schedule(message.chat.id, day, all_data)
    if not schedule:
        return reply_safe(message, wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

    now_dt = datetime.now()
    curr_time = now_dt.strftime("%H:%M")
    curr_dt = datetime.strptime(curr_time, "%H:%M")
    total_slots = min(len(schedule), len(CALLS))

    def format_slot(slot):
        if not slot:
            return "Окно"
        lines = []
        for gname, subj, room in slot:
            if subj == "ОБЕД":
                lines.append("ОБЕД")
            else:
                lines.append(f"{subj} (каб.{room})\n   {gname}")
        return "\n".join(lines)

    first_start = datetime.strptime(CALLS[0][0], "%H:%M")
    if curr_dt < first_start:
        td = first_start - curr_dt
        h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
        rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
        next_idx = next((i for i in range(total_slots) if schedule[i]), None)
        if next_idx is not None:
            next_str = f"{next_idx + 1}. {format_slot(schedule[next_idx])} ({CALLS[next_idx][0]} - {CALLS[next_idx][1]})"
        else:
            next_str = "пар больше нет"
        res = f"Занятия еще не начались\nДо начала 1-го урока: {rem}\n\nСледующий: {next_str}"
        return reply_safe(message, wrap_code(res))

    last_end = datetime.strptime(CALLS[total_slots - 1][1], "%H:%M")
    if curr_dt >= last_end:
        return reply_safe(message, wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

    for i in range(total_slots):
        start_dt = datetime.strptime(CALLS[i][0], "%H:%M")
        end_dt = datetime.strptime(CALLS[i][1], "%H:%M")
        if start_dt <= curr_dt <= end_dt:
            slot = schedule[i]
            next_idx = next((k for k in range(i + 1, total_slots) if schedule[k]), None)
            if next_idx is not None:
                next_str = f"{next_idx + 1}. {format_slot(schedule[next_idx])} ({CALLS[next_idx][0]} - {CALLS[next_idx][1]})"
            else:
                next_str = "пар больше нет"

            if not slot:
                res = f"Сейчас: {i + 1}. Окно (нет пар в ваших кабинетах)\nВремя: {CALLS[i][0]} - {CALLS[i][1]}\n\nСледующий: {next_str}"
                return reply_safe(message, wrap_code(res))

            total_sec = (end_dt - start_dt).seconds
            elapsed_sec = max(0, (curr_dt - start_dt).seconds)
            percent = min(100, max(0, int((elapsed_sec / total_sec) * 100))) if total_sec else 0
            bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            td = end_dt - curr_dt
            h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
            rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"

            res = (
                f"Сейчас: {i + 1}. {format_slot(slot)}\n"
                f"Время: {CALLS[i][0]} - {CALLS[i][1]}\n"
                f"{bar} {percent}%\n"
                f"До конца урока: {rem}\n\n"
                f"Следующий: {next_str}"
            )
            return reply_safe(message, wrap_code(res))

    for i in range(total_slots - 1):
        break_start = datetime.strptime(CALLS[i][1], "%H:%M")
        break_end = datetime.strptime(CALLS[i + 1][0], "%H:%M")
        if break_start < curr_dt < break_end:
            td = break_end - curr_dt
            h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
            rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
            next_idx = next((k for k in range(i + 1, total_slots) if schedule[k]), None)
            if next_idx is not None:
                next_str = f"{next_idx + 1}. {format_slot(schedule[next_idx])} ({CALLS[next_idx][0]} - {CALLS[next_idx][1]})"
            else:
                next_str = "пар больше нет"
            res = (
                f"Сейчас: Перемена\n"
                f"До конца перемены: {rem}\n\n"
                f"Следующий: {next_str}"
            )
            return reply_safe(message, wrap_code(res))

    return reply_safe(message, wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")


def cmd_teacher_next(message):
    """Показывает следующий урок учителя."""
    day = datetime.now().isoweekday()
    if day > 5:
        return reply_safe(message, wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

    all_data = get_all_schedules_for_day(day)
    all_data = apply_teacher_overrides(all_data, day)
    dept, rooms, schedule = get_teacher_schedule(message.chat.id, day, all_data)
    if not schedule:
        return reply_safe(message, wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

    now_dt = datetime.now()
    curr_time = now_dt.strftime("%H:%M")
    curr_dt = datetime.strptime(curr_time, "%H:%M")
    total_slots = min(len(schedule), len(CALLS))

    def format_slot(slot):
        lines = []
        for gname, subj, room in slot:
            if subj == "ОБЕД":
                lines.append("ОБЕД")
            else:
                lines.append(f"{subj} (каб.{room})\n   {gname}")
        return "\n".join(lines)

    first_start = datetime.strptime(CALLS[0][0], "%H:%M")
    if curr_dt < first_start:
        start_from = 0
    else:
        start_from = total_slots
        for i in range(total_slots):
            end_dt = datetime.strptime(CALLS[i][1], "%H:%M")
            if curr_dt < end_dt:
                start_from = i + 1
                break

    next_idx = next((k for k in range(start_from, total_slots) if schedule[k]), None)
    if next_idx is None:
        return reply_safe(message, wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

    start_t = CALLS[next_idx][0]
    end_t = CALLS[next_idx][1]
    td = datetime.strptime(start_t, "%H:%M") - curr_dt
    h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
    rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"

    res = (
        f"Далее: {next_idx + 1}. {format_slot(schedule[next_idx])}\n"
        f"Время: {start_t} - {end_t}\n"
        f"Через: {rem}"
    )
    return reply_safe(message, wrap_code(res))


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

    if tokens[0].lower() == 'clear':
        rest = tokens[1].lower() if len(tokens) > 1 else ''
        target_day = day_map.get(rest, today)
        conn = get_db_connection()
        conn.execute("DELETE FROM teacher_room_overrides WHERE teacher_chat_id=? AND day=?",
                     (message.chat.id, target_day))
        conn.commit()
        conn.close()
        return reply_safe(message, wrap_code(f"🗑 Замены на {day_names.get(target_day, '?')} сброшены."))

    target_day = today
    if tokens[0].lower() in day_map:
        target_day = day_map[tokens.pop(0).lower()]

    if not tokens:
        return reply_safe(message, "❌ Укажите номер пары.")

    try:
        slot_num = int(tokens.pop(0))
        slot_idx = slot_num - 1
    except ValueError:
        return reply_safe(message, "❌ Номер пары должен быть цифрой (1–10).")
    if slot_idx < 0 or slot_idx >= 10:
        return reply_safe(message, "❌ Номер пары от 1 до 10.")

    new_room = None
    new_subject = None
    group_id = -1
    remaining = []

    for t in tokens:
        tl = t.lower()
        if tl.startswith('п=') or tl.startswith('предм='):
            new_subject = t.split('=', 1)[1]
        elif re.match(r'^\d+[А-Яа-яA-Za-z]?$', t) and new_room is None:
            new_room = t
        else:
            remaining.append(t)

    if remaining:
        group_str = ' '.join(remaining)
        matched_name, group_info = find_group_info(group_str)
        if group_info:
            dept = group_info[0]
            group_id = group_info[1]
        else:
            return reply_safe(message, wrap_code(f"❌ Группа '{group_str}' не найдена."))

    if new_room is None and new_subject is None:
        return reply_safe(message, "❌ Укажите кабинет (число) и/или предмет (п=Название).")

    save_teacher_override(message.chat.id, dept, target_day, slot_idx, group_id, new_room, new_subject)

    all_data = get_all_schedules_for_day(target_day)
    sample_lesson = None
    if group_id == -1:
        _, teacher_rooms = get_teacher_info(message.chat.id)
        for (d, gid2), ls in all_data.items():
            if d == dept and slot_idx < len(ls):
                r = extract_room(str(ls[slot_idx]))
                if r and teacher_rooms and any(tr.strip() in r for tr in teacher_rooms):
                    sample_lesson = str(ls[slot_idx])
                    break
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
    orig_subj = re.sub(r'\s*\(.*$', '', sample_lesson).strip() if sample_lesson else "?"
    group_label = GROUP_ID_TO_NAME.get(dept, {}).get(group_id, "?") if group_id != -1 else "все группы"

    conf = [f"✅ Сохранено | {day_names.get(target_day, '?')}, пара {slot_num}"]
    if new_room:
        conf.append(f"Кабинет: {orig_room} → {new_room}")
    if new_subject:
        conf.append(f"Предмет: {orig_subj} → {new_subject}")
    conf.append(f"Группа: {group_label}")
    conf.append("⏳ Уведомление ученикам через ~5 мин")
    reply_safe(message, wrap_code("\n".join(conf)))
