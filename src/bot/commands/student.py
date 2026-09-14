"""
Студенческие команды просмотра расписания, подписок и поиска.
"""
import re
from datetime import datetime
from telebot.types import Message
from src.config import now_msk
from src.core.command import BaseCommand
from src.core.container import AppContext
from src.bot.handlers.teacher import (
    cmd_teacher_now,
    cmd_teacher_next,
    cmd_teacher_r,
    cmd_teacher_db,
)


def format_lessons_count(count: int) -> str:
    if count == 1:
        return "пол пары"
    elif count == 2:
        return "1 пара"
    elif count == 3:
        return "1.5 пары"
    elif count == 4:
        return "2 пары"
    return f"{count / 2} пары"


def clean_subject_for_grouping(t: str) -> str:
    return re.sub(r'\(.*?\)', '', str(t)).strip().lower()


def build_lesson_blocks(lessons: list, calls: list, cid: int, department: int,
                        gid: int, day: int, all_data: dict, ctx: AppContext) -> list:
    total = min(len(lessons), len(calls))
    if total == 0:
        return []

    blocks = []
    i = 0
    while i < total:
        first_idx = i
        target = clean_subject_for_grouping(lessons[i])
        last_idx = i
        while last_idx + 1 < total and clean_subject_for_grouping(lessons[last_idx + 1]) == target:
            last_idx += 1

        start_time = calls[first_idx][0]
        end_time = calls[last_idx][1]
        count = last_idx - first_idx + 1

        lines = ctx.notifier.format_with_overlap(
            cid,
            department,
            gid,
            day,
            first_idx,
            str(lessons[first_idx]),
            all_data
        )
        clean_name = lines[0] if lines else str(lessons[first_idx])
        overlap_extra = f"\n   {lines[1]}" if len(lines) > 1 else ""

        if first_idx == last_idx:
            num_str = f"{first_idx + 1}"
        else:
            num_str = f"{first_idx + 1}-{last_idx + 1}"

        display_name = f"{num_str}. {clean_name}{overlap_extra}"

        blocks.append({
            "first_idx": first_idx,
            "last_idx": last_idx,
            "start_time": start_time,
            "end_time": end_time,
            "count": count,
            "name": clean_name,
            "display_name": display_name,
            "raw_name": lessons[first_idx]
        })
        i = last_idx + 1

    return blocks


def get_next_block_info(ctx: AppContext, cid: int, department: int, gid: int,
                        day: int, data: dict, current_idx: int | None = None):
    try:
        lessons = data.get((department, gid), [])
        if not lessons:
            return None
        calls = ctx.config.CALLS
        blocks = build_lesson_blocks(lessons, calls, cid, department, gid, day, data, ctx)
        if not blocks:
            return None

        now_dt = now_msk()
        curr_time = now_dt.strftime("%H:%M")
        curr_dt = datetime.strptime(curr_time, "%H:%M")

        next_b = None
        if current_idx is not None:
            for b_idx, b in enumerate(blocks):
                if b['first_idx'] <= current_idx <= b['last_idx']:
                    if b_idx + 1 < len(blocks):
                        next_b = blocks[b_idx + 1]
                    break
        else:
            first_start = datetime.strptime(blocks[0]['start_time'], "%H:%M")
            if curr_dt < first_start:
                next_b = blocks[0]
            else:
                for b_idx, b in enumerate(blocks):
                    end_dt = datetime.strptime(b['end_time'], "%H:%M")
                    if curr_dt < end_dt:
                        if b_idx + 1 < len(blocks):
                            next_b = blocks[b_idx + 1]
                        break

        if next_b is None:
            return None

        start_time = next_b['start_time']
        td = datetime.strptime(start_time, "%H:%M") - curr_dt
        h, m = td.seconds // 3600, (td.seconds // 60) % 60
        rem_str = f"{f'{h}ч ' if h > 0 else ''}{m}м"

        return {
            "name": next_b['display_name'],
            "count": next_b['count'],
            "time_to": rem_str,
            "raw_name": next_b['raw_name'],
            "start_time": next_b['start_time'],
            "end_time": next_b['end_time']
        }
    except Exception:
        return None


def render_schedule_msg(ctx: AppContext, message: Message, monitor: dict,
                        all_data: dict, day: int, header_text: str, send_stickers: bool = False):
    key = (monitor['department'], monitor['group_id'])
    lessons = all_data.get(key)
    if not lessons:
        return ctx.reply(message, ctx.wrap_code(f"{header_text}\n\nНет пар или данных."))

    res = f"{header_text}\n\n"
    cnt = 1
    for i, l in enumerate(lessons):
        lines = ctx.notifier.format_with_overlap(
            message.chat.id,
            monitor['department'],
            monitor['group_id'],
            day,
            i,
            str(l),
            all_data
        )
        if not lines:
            continue
        if day == 1 and cnt == 1 and lines:
            lines[0] = lines[0] + " +К/Ч"
        res += f"{cnt}. {lines[0]}\n"
        if len(lines) > 1:
            res += f"   {lines[1]}\n"
        cnt += 1
    ctx.reply(message, ctx.wrap_code(res.strip()))


def refresh_gloris_schedule(ctx: AppContext, mons: list, day: int):
    """Опрашивает Глорис для парсера по дню недели и обновляет базы данных при наличии изменений."""
    import json
    import hashlib
    for m in mons:
        dep = m['department']
        gid = m['group_id']
        try:
            raw = ctx.parser.fetch_lessons(day, gid, dep)
            if raw:
                h = hashlib.md5("".join(raw).encode()).hexdigest()
                date_str = ctx.db.get_date_for_weekday(day)
                ctx.db.save_schedule_to_db(dep, gid, day, h, json.dumps(raw, ensure_ascii=False), date_str)
        except Exception:
            pass


class NowCommand(BaseCommand):
    """Текущая пара, оставшееся время и следующий урок."""
    name = "now"
    aliases = ["сейчас", "пара"]
    description = "Текущая пара, оставшееся время и следующий урок"
    requires = ["db", "notifier", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_now(message)

        now_dt = now_msk()
        day = now_dt.isoweekday()
        if day > 5:
            return ctx.reply(message, ctx.wrap_code("Отдыхай (выходной)\n(Используй /db)") + "\n\n/db")

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(message, "❌ Нет подписок. Сначала отправь номер группы.")

        all_data = ctx.db.get_all_schedules_for_day(day)
        all_data = ctx.db.apply_teacher_overrides(all_data, day)
        m = mons[0]
        key = (m['department'], m['group_id'])
        lessons = all_data.get(key, [])
        calls = ctx.config.CALLS

        blocks = build_lesson_blocks(lessons, calls, message.chat.id, m['department'], m['group_id'], day, all_data, ctx)
        if not blocks:
            return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

        curr_time = now_dt.strftime("%H:%M")
        curr_dt = datetime.strptime(curr_time, "%H:%M")

        # 1. До начала занятий
        first_start = datetime.strptime(blocks[0]['start_time'], "%H:%M")
        if curr_dt < first_start:
            td = first_start - curr_dt
            h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
            rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
            next_b = blocks[0]
            res = (
                f"Занятия еще не начались\n"
                f"До начала: {rem}\n\n"
                f"Следующий: {next_b['display_name']} ({next_b['start_time']} - {next_b['end_time']})"
            )
            return ctx.reply(message, ctx.wrap_code(res))

        # 2. После всех занятий
        last_end = datetime.strptime(blocks[-1]['end_time'], "%H:%M")
        if curr_dt >= last_end:
            return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

        # 3. Во время блока
        for b_idx, b in enumerate(blocks):
            start_dt = datetime.strptime(b['start_time'], "%H:%M")
            end_dt = datetime.strptime(b['end_time'], "%H:%M")
            if start_dt <= curr_dt <= end_dt:
                total_sec = (end_dt - start_dt).seconds
                elapsed_sec = max(0, (curr_dt - start_dt).seconds)
                percent = min(100, max(0, int((elapsed_sec / total_sec) * 100))) if total_sec else 0
                bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))

                td = end_dt - curr_dt
                h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
                rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
                lbl = "До конца блока:" if b['count'] > 1 else "До конца пары:"

                if b_idx + 1 < len(blocks):
                    next_b = blocks[b_idx + 1]
                    next_str = f"{next_b['display_name']} ({next_b['start_time']} - {next_b['end_time']})"
                else:
                    next_str = "пар больше нет"

                res = (
                    f"Сейчас: {b['display_name']}\n"
                    f"Время: {b['start_time']} - {b['end_time']}\n"
                    f"{bar} {percent}%\n"
                    f"{lbl} {rem}\n\n"
                    f"Следующий: {next_str}"
                )
                return ctx.reply(message, ctx.wrap_code(res))

        # 4. Во время перемены между блоками
        for b_idx in range(len(blocks) - 1):
            break_start = datetime.strptime(blocks[b_idx]['end_time'], "%H:%M")
            break_end = datetime.strptime(blocks[b_idx + 1]['start_time'], "%H:%M")
            if break_start < curr_dt < break_end:
                td = break_end - curr_dt
                h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
                rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
                next_b = blocks[b_idx + 1]
                res = (
                    f"Сейчас: Перемена\n"
                    f"До конца перемены: {rem}\n\n"
                    f"Следующий: {next_b['display_name']} ({next_b['start_time']} - {next_b['end_time']})"
                )
                return ctx.reply(message, ctx.wrap_code(res))

        return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")


class NextCommand(BaseCommand):
    """Информация о следующем предстоящем блоке пар."""
    name = "next"
    aliases = ["далее", "следующая"]
    description = "Информация о следующем предстоящем блоке пар"
    requires = ["db", "notifier", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_next(message)

        now_dt = now_msk()
        day = now_dt.isoweekday()
        if day > 5:
            return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(message, "❌ Нет подписок. Сначала отправь номер группы.")

        all_data = ctx.db.get_all_schedules_for_day(day)
        all_data = ctx.db.apply_teacher_overrides(all_data, day)
        m = mons[0]
        key = (m['department'], m['group_id'])
        lessons = all_data.get(key, [])
        calls = ctx.config.CALLS

        blocks = build_lesson_blocks(lessons, calls, message.chat.id, m['department'], m['group_id'], day, all_data, ctx)
        if not blocks:
            return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

        curr_time = now_dt.strftime("%H:%M")
        curr_dt = datetime.strptime(curr_time, "%H:%M")

        # 1. До начала занятий
        first_start = datetime.strptime(blocks[0]['start_time'], "%H:%M")
        if curr_dt < first_start:
            td = first_start - curr_dt
            h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
            rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
            next_b = blocks[0]
            res = (
                f"Далее: {next_b['display_name']}\n"
                f"Время: {next_b['start_time']} - {next_b['end_time']}\n"
                f"Длительность: {format_lessons_count(next_b['count'])}\n"
                f"Через: {rem}"
            )
            return ctx.reply(message, ctx.wrap_code(res))

        # 2. После всех уроков
        last_end = datetime.strptime(blocks[-1]['end_time'], "%H:%M")
        if curr_dt >= last_end:
            return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

        # 3. Во время блока -> следующий блок!
        for b_idx, b in enumerate(blocks):
            start_dt = datetime.strptime(b['start_time'], "%H:%M")
            end_dt = datetime.strptime(b['end_time'], "%H:%M")
            if start_dt <= curr_dt <= end_dt:
                if b_idx + 1 < len(blocks):
                    next_b = blocks[b_idx + 1]
                    next_start = datetime.strptime(next_b['start_time'], "%H:%M")
                    td = next_start - curr_dt
                    h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
                    rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
                    res = (
                        f"Далее: {next_b['display_name']}\n"
                        f"Время: {next_b['start_time']} - {next_b['end_time']}\n"
                        f"Длительность: {format_lessons_count(next_b['count'])}\n"
                        f"Через: {rem}"
                    )
                    return ctx.reply(message, ctx.wrap_code(res))
                else:
                    return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")

        # 4. Во время перемены между блоками
        for b_idx in range(len(blocks) - 1):
            break_start = datetime.strptime(blocks[b_idx]['end_time'], "%H:%M")
            break_end = datetime.strptime(blocks[b_idx + 1]['start_time'], "%H:%M")
            if break_start < curr_dt < break_end:
                td = break_end - curr_dt
                h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
                rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
                next_b = blocks[b_idx + 1]
                res = (
                    f"Далее: {next_b['display_name']}\n"
                    f"Время: {next_b['start_time']} - {next_b['end_time']}\n"
                    f"Длительность: {format_lessons_count(next_b['count'])}\n"
                    f"Через: {rem}"
                )
                return ctx.reply(message, ctx.wrap_code(res))

        return ctx.reply(message, ctx.wrap_code("Пар больше нет\n(Используй /db)") + "\n\n/db")


class ScheduleTodayCommand(BaseCommand):
    """Расписание занятий на сегодня."""
    name = "r"
    aliases = ["сегодня", "расписание"]
    description = "Расписание занятий на сегодня"
    requires = ["db", "notifier", "parser"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_r(message)

        day = now_msk().isoweekday()
        if day > 5:
            return ctx.reply(message, ctx.wrap_code("Отдыхай (выходной)"))

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(message, "❌ Нет подписок.")

        refresh_gloris_schedule(ctx, mons, day)
        all_day_data = ctx.db.get_all_schedules_for_day(day)
        all_day_data = ctx.db.apply_teacher_overrides(all_day_data, day)
        for m in mons:
            render_schedule_msg(
                ctx,
                message,
                m,
                all_day_data,
                day,
                f"📅 Сегодня: {m['group_name']}",
                send_stickers=True
            )


class ScheduleArchiveCommand(BaseCommand):
    """Расписание на завтра, по дням недели или конкретной дате."""
    name = "db"
    aliases = ["архив", "завтра"]
    description = "Расписание на завтра, по дням недели или конкретной дате"
    requires = ["db", "notifier", "parser"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_db(message)

        args = message.text.replace('/db', '').strip().lower()
        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(message, "❌ Нет подписок.")

        day_map = {'пн': 1, 'вт': 2, 'ср': 3, 'чт': 4, 'пт': 5, 'сб': 6}
        day_labels = {1: "ПН", 2: "ВТ", 3: "СР", 4: "ЧТ", 5: "ПТ", 6: "СБ"}

        # Обработка конкретной даты /db 16.06.2026
        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', args):
            try:
                target_date = datetime.strptime(args, "%d.%m.%Y").strftime("%Y-%m-%d")
                all_data = ctx.db.get_schedule_history_for_date(target_date)
                if not all_data:
                    return ctx.reply(message, ctx.wrap_code(f"🗄 Нет данных в архиве за {args}"))

                target_weekday = datetime.strptime(args, "%d.%m.%Y").isoweekday()
                refresh_gloris_schedule(ctx, mons, target_weekday)
                all_data = ctx.db.get_schedule_history_for_date(target_date) or all_data
                all_data = ctx.db.apply_teacher_overrides(all_data, target_weekday)
                for m in mons:
                    header = f"🗄 Архив ({args}): {m['group_name']}"
                    render_schedule_msg(ctx, message, m, all_data, target_weekday, header)
                return
            except ValueError:
                return ctx.reply(message, "❌ Неверный формат даты.")

        target_day = day_map.get(args)
        if target_day is not None:
            refresh_gloris_schedule(ctx, mons, target_day)
            all_data = ctx.db.get_all_schedules_for_day(target_day)
            all_data = ctx.db.apply_teacher_overrides(all_data, target_day)
            for m in mons:
                header = f"📅 {day_labels[target_day]}: {m['group_name']}"
                render_schedule_msg(ctx, message, m, all_data, target_day, header)
            return

        # Если без аргументов — выводим расписание НА ЗАВТРА
        curr_day = now_msk().isoweekday()
        next_day = 1 if curr_day >= 5 else curr_day + 1
        refresh_gloris_schedule(ctx, mons, next_day)
        all_data = ctx.db.get_all_schedules_for_day(next_day)
        all_data = ctx.db.apply_teacher_overrides(all_data, next_day)
        for m in mons:
            header = f"📅 Завтра ({day_labels[next_day]}): {m['group_name']}"
            render_schedule_msg(ctx, message, m, all_data, next_day, header)


class ListCommand(BaseCommand):
    """Просмотр списка активных подписок или профиля преподавателя."""
    name = "list"
    aliases = ["подписки", "список"]
    description = "Просмотр активных подписок пользователя"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            dept, rooms = ctx.db.get_teacher_info(message.chat.id)
            return ctx.reply(
                message, f"🧑‍🏫 *Учитель*\nОтделение: {dept}\nКабинеты: {', '.join(rooms)}"
            )
        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        ctx.reply(
            message,
            "📋 *Подписки:*\n" + "\n".join([f"- {m['group_name']}" for m in mons])
        )


class UnsubCommand(BaseCommand):
    """Отписка от рассылки и удаление подписок/профиля."""
    name = "unsub"
    aliases = ["отписаться", "отписка"]
    description = "Удаление всех подписок пользователя или профиля учителя"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            conn = ctx.db.get_connection()
            conn.execute("DELETE FROM teachers WHERE chat_id=?", (message.chat.id,))
            conn.commit()
            conn.close()
            return ctx.reply(
                message, "🗑 Учительский профиль удалён. /start — зарегистрироваться снова."
            )
        to_del = [
            k for k, v in ctx.db.monitor_manager.active_monitors.items()
            if str(v['chat_id']) == str(message.chat.id)
        ]
        for k in to_del:
            del ctx.db.monitor_manager.active_monitors[k]
        ctx.db.monitor_manager.save()
        ctx.reply(message, "🗑 Подписки удалены.")


class FindByRoomCommand(BaseCommand):
    """Поиск расписания по номеру кабинета."""
    name = "f"
    aliases = ["кабинет", "комната"]
    description = "Поиск расписания пар по номеру кабинета"
    requires = ["db", "parser"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        room_target = message.text.replace('/f', '', 1).strip()
        if not room_target:
            return ctx.reply(
                message, ctx.wrap_code("Ошибка: введите номер кабинета.\nПример: /f 44")
            )

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(
                message, "❌ Нет активных подписок. Сначала подпишитесь на группу, чтобы определить отделение."
            )

        user_department = mons[0]['department']
        day = now_msk().isoweekday()
        if day > 5:
            return ctx.reply(message, ctx.wrap_code("Сегодня выходной, занятий нет."))

        all_data = ctx.db.get_all_schedules_for_day(day)
        max_lessons = 10
        schedule = [{} for _ in range(max_lessons)]

        for (dep, gid), lessons in all_data.items():
            if dep != user_department:
                continue
            group_name = ctx.parser.GROUP_ID_TO_NAME.get(dep, {}).get(gid, "?")
            for idx in range(min(len(lessons), max_lessons)):
                l_str = str(lessons[idx])
                room = ctx.db.extract_room(l_str)
                if room and room_target in room:
                    applied = ctx.db.custom_names_manager.apply(
                        message.chat.id, l_str
                    ) or ""
                    subj = re.sub(r'\s*\([^)]*\)$', '', applied).strip()
                    if subj:
                        if subj not in schedule[idx]:
                            schedule[idx][subj] = []
                        schedule[idx][subj].append(group_name)

        res_lines = [f"Кабинет {room_target} (отделение {user_department}):"]
        for i, hour in enumerate(schedule):
            if hour:
                row = " / ".join([f"{s} ({', '.join(g)})" for s, g in hour.items()])
                res_lines.append(f"{i+1}. {row}")
            else:
                res_lines.append(f"{i+1}. ---")

        ctx.reply(message, ctx.wrap_code("\n".join(res_lines)))


class FindByGroupCommand(BaseCommand):
    """Быстрый просмотр расписания для любой группы."""
    name = "w"
    aliases = ["группа", "поиск_группы"]
    description = "Просмотр расписания произвольной группы"
    requires = ["db", "parser", "notifier"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        target_group = message.text.replace('/w', '', 1).strip().upper()
        if not target_group:
            return ctx.reply(
                message, ctx.wrap_code("Ошибка: введите группу.\nПример: /w ИС-41-22")
            )

        matched_name, group_info = ctx.parser.find_group_info(target_group)
        if not group_info:
            return ctx.reply(
                message, ctx.wrap_code(f"Группа {target_group} не найдена.")
            )
        target_group = matched_name
        department, gid = group_info[0], group_info[1]

        day = now_msk().isoweekday()
        if day > 5:
            return ctx.reply(
                message, ctx.wrap_code(f"{target_group}: отдых (выходной)")
            )

        all_day_data = ctx.db.get_all_schedules_for_day(day)
        lessons = all_day_data.get((department, gid)) or ctx.parser.fetch_lessons(day, gid, department)

        if lessons:
            res = f"Группа {target_group}:\n\n"
            cnt = 1
            for i, l in enumerate(lessons):
                lines = ctx.notifier.format_with_overlap(
                    message.chat.id, department, gid, day, i, l, all_day_data
                )
                if not lines:
                    continue
                if day == 1 and cnt == 1 and lines:
                    lines[0] = lines[0] + " +К/Ч"
                res += f"{cnt}. {lines[0]}\n"
                if len(lines) > 1:
                    res += f"   {lines[1]}\n"
                cnt += 1
            ctx.reply(message, ctx.wrap_code(res.strip()))
        else:
            ctx.reply(
                message, ctx.wrap_code(f"Нет данных для {target_group} на сегодня.")
            )


class HomeworkCommand(BaseCommand):
    """Карманный планер: дедлайны, домашка и заметки к парам (Phase 6.4)."""
    name = "hw"
    aliases = ["note", "домашка", "заметки", "дз"]
    description = "Карманный планер: просмотр и добавление домашки/заметок (/hw предмет заметка)"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        text = message.text or ""
        parts = text.split(maxsplit=2)
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        # 1. Если аргументы переданы -> Добавление заметки
        if len(args) >= 2:
            subject = args[0].strip()
            note = args[1].strip()
            mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
            gid = mons[0]['group_id'] if mons else 0
            dep = mons[0]['department'] if mons else 3
            ctx.db.add_homework_note(message.chat.id, gid, dep, subject, note)
            return ctx.reply(
                message,
                f"📝 Заметка добавлена:\n📌 *{subject}*: {note}\n\nПосмотреть все: `/hw`",
                parse_mode='Markdown'
            )
        elif len(args) == 1 and args[0].strip() in ("clear", "очистить", "удалить"):
            # Очистка всех заметок
            notes = ctx.db.get_homework_notes(message.chat.id)
            for n in notes:
                ctx.db.delete_homework_note(n['id'], message.chat.id)
            return ctx.reply(message, "🗑 Все заметки удалены.")

        # 2. Если без аргументов -> Вывод активных заметок
        notes = ctx.db.get_homework_notes(message.chat.id)
        if not notes:
            return ctx.reply(
                message,
                "📭 У вас пока нет заметок и домашнего задания.\n\n"
                "Чтобы добавить: `/hw [Предмет] [Текст заметки]`\n"
                "Например: `/hw Математика сдать типовой расчёт`",
                parse_mode='Markdown'
            )

        res = "📋 *Ваш карманный планер:*\n\n"
        for i, n in enumerate(notes[:15], 1):
            res += f"{i}. 📌 *{n['subject']}*: {n['note']}\n"
        res += "\n_Очистить всё: `/hw clear`_"
        ctx.reply(message, res, parse_mode='Markdown')


class FreeRoomsCommand(BaseCommand):
    """Навигатор по колледжу: свободные аудитории прямо сейчас (Phase 6.5)."""
    name = "free"
    aliases = ["свободные", "гдеприсесть", "аудитории", "окна"]
    description = "Поиск свободных аудиторий в отделении прямо сейчас"
    requires = ["db", "parser"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        user_department = mons[0]['department'] if mons else 3

        day = now_msk().isoweekday()
        if day > 6:
            return ctx.reply(message, ctx.wrap_code("Сегодня выходной, колледж закрыт."))

        now_time = now_msk().strftime("%H:%M")
        from src.config import CALLS
        max_lessons = 10 if day == 1 else 8

        # Находим текущую или следующую пару
        current_idx = None
        for i, call in enumerate(CALLS[:max_lessons]):
            if call[0] <= now_time <= call[1]:
                current_idx = i
                break
        if current_idx is None:
            # Если между парами или перед парами, берем ближайшую следующую
            for i, call in enumerate(CALLS[:max_lessons]):
                if now_time < call[0]:
                    current_idx = i
                    break
        if current_idx is None:
            return ctx.reply(message, ctx.wrap_code("Учебный день завершён, все кабинеты свободны."))

        call_time = f"{CALLS[current_idx][0]} - {CALLS[current_idx][1]}"
        all_data = ctx.db.get_all_schedules_for_day(day)

        # Собираем все занятые и известные кабинеты отделения
        occupied_rooms = set()
        all_known_rooms = set()

        for (dep, gid), lessons in all_data.items():
            if dep != user_department:
                continue
            for idx, lesson in enumerate(lessons):
                room = ctx.db.extract_room(str(lesson))
                if room and room.isdigit():
                    all_known_rooms.add(room)
                    if idx == current_idx:
                        occupied_rooms.add(room)

        free_rooms = sorted(all_known_rooms - occupied_rooms, key=lambda x: int(x) if x.isdigit() else x)
        if not free_rooms:
            return ctx.reply(
                message,
                ctx.wrap_code(f"Отделение {user_department} | {current_idx+1} пара ({call_time})\nСвободных кабинетов не обнаружено.")
            )

        res = f"🏫 Свободные аудитории (Отд. {user_department})\n⏰ {current_idx+1} пара ({call_time}):\n\n"
        res += ", ".join(free_rooms[:30])
        ctx.reply(message, ctx.wrap_code(res))


class RollcallCommand(BaseCommand):
    """Инструменты старосты: интерактивная перекличка в групповом чате (Phase 7.2)."""
    name = "rollcall"
    aliases = ["перекличка", "посещаемость", "ктотут"]
    description = "Запуск интерактивной переклички студентов в чате группы"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✋ Я на парах!", callback_data="rollcall_present"),
            InlineKeyboardButton("🤒 Болею", callback_data="rollcall_ill")
        )
        ctx.reply(
            message,
            "📋 *Утренняя перекличка группы!*\n\n"
            "Отметьтесь кнопкой ниже, чтобы староста видел посещаемость:\n"
            "• ✋ Присутствуют: 0\n"
            "• 🤒 Отсутствуют: 0\n\n"
            "_(Нажмите кнопку ниже для отметки)_",
            reply_markup=markup,
            parse_mode='Markdown'
        )


class TermProgressCommand(BaseCommand):
    """Студенческий трекер семестра, каникул и сессии (Phase 7.3)."""
    name = "term"
    aliases = ["семестр", "сессия", "каникулы", "progress"]
    description = "Счетчик учебных недель и дней до конца семестра и сессии"
    requires = ["config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        now = now_msk()
        year = now.year
        # Осенний семестр: 1 сентября - 31 декабря, Весенний: 12 января - 30 июня
        if now.month >= 9:
            term_name = f"Осенний семестр {year}"
            term_start = datetime(year, 9, 1)
            term_end = datetime(year, 12, 31)
            session_start = datetime(year, 12, 20)
        else:
            term_name = f"Весенний семестр {year}"
            term_start = datetime(year, 1, 12)
            term_end = datetime(year, 6, 30)
            session_start = datetime(year, 6, 10)

        total_days = (term_end - term_start).days
        passed_days = max(0, (now.date() - term_start.date()).days)
        remaining_days = max(0, (term_end.date() - now.date()).days)
        current_week = (passed_days // 7) + 1
        days_to_session = max(0, (session_start.date() - now.date()).days)

        percent = min(100, int((passed_days / total_days) * 100)) if total_days > 0 else 0
        filled_bars = percent // 10
        progress_bar = "▓" * filled_bars + "░" * (10 - filled_bars)

        res = (
            f"🎓 *Трекер семестра: {term_name}*\n\n"
            f"Прогресс: `[{progress_bar}]` {percent}%\n\n"
            f"• 📅 Текущая учебная неделя: *{current_week}*\n"
            f"• ⏳ До начала сессии: *{days_to_session} дн.*\n"
            f"• 🏖 До каникул: *{remaining_days} дн.*\n\n"
            f"Держитесь, Калич верит в вас! [^ v ^]"
        )
        ctx.reply(message, res, parse_mode='Markdown')
