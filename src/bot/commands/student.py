"""
Студенческие команды просмотра расписания, подписок и поиска.
"""
import re
from datetime import datetime
from telebot.types import Message
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


def get_next_block_info(ctx: AppContext, cid: int, department: int, gid: int,
                        day: int, data: dict, current_idx: int | None = None):
    try:
        lessons = data.get((department, gid), [])
        if not lessons:
            return None
        now_dt = datetime.now()
        curr_time = now_dt.strftime("%H:%M")
        next_idx = None
        calls = ctx.config.CALLS

        if current_idx is not None:
            def clean_n(t):
                return re.sub(r'\(?\d{2,4}[А-Яа-я]?\)?', '', str(t)).strip().lower()
            target_n = clean_n(lessons[current_idx])
            check_idx = current_idx
            while check_idx < len(lessons) - 1 and clean_n(lessons[check_idx + 1]) == target_n:
                check_idx += 1
            if check_idx + 1 < len(lessons):
                next_idx = check_idx + 1
        else:
            for i, call in enumerate(calls):
                if call[0] > curr_time and i < len(lessons):
                    next_idx = i
                    break

        if next_idx is None or next_idx >= len(lessons):
            return None

        def clean_n(t):
            return re.sub(r'\(?\d{2,4}[А-Яа-я]?\)?', '', str(t)).strip().lower()

        next_name_raw = clean_n(lessons[next_idx])
        block_count = 1
        temp_idx = next_idx
        while temp_idx < len(lessons) - 1 and clean_n(lessons[temp_idx + 1]) == next_name_raw:
            temp_idx += 1
            block_count += 1

        start_time = calls[next_idx][0]
        td = datetime.strptime(start_time, "%H:%M") - datetime.strptime(curr_time, "%H:%M")
        h, m = td.seconds // 3600, (td.seconds // 60) % 60
        rem_str = f"{f'{h}ч ' if h > 0 else ''}{m}м"

        lines = ctx.notifier.format_with_overlap(
            cid,
            department,
            gid,
            day,
            next_idx,
            lessons[next_idx],
            data
        )
        clean_name = lines[0] if lines else str(lessons[next_idx])
        return {
            "name": clean_name,
            "count": block_count,
            "time_to": rem_str,
            "raw_name": lessons[next_idx]
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
    """Текущая пара и прогресс-бар до её завершения."""
    name = "now"
    aliases = ["сейчас", "пара"]
    description = "Текущая пара и прогресс-бар до её завершения"
    requires = ["db", "notifier", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_now(message)

        status, _, idx = ctx.notifier.get_status()
        if status == "rest" or idx is None:
            return ctx.reply(message, ctx.wrap_code("Отдыхай\n(Используй /db)") + "\n\n/db")

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return

        day = datetime.now().isoweekday()
        all_data = ctx.db.get_all_schedules_for_day(day)
        all_data = ctx.db.apply_teacher_overrides(all_data, day)
        m = mons[0]
        key = (m['department'], m['group_id'])
        lessons = all_data.get(key)

        if lessons and len(lessons) > idx:
            curr_l_raw = lessons[idx]

            def clean_n(t):
                return re.sub(r'\(?\d{2,4}[А-Яа-я]?\)?', '', str(t)).strip().lower()

            target_n = clean_n(curr_l_raw)
            first_idx = idx
            while first_idx > 0 and clean_n(lessons[first_idx - 1]) == target_n:
                first_idx -= 1
            last_idx = idx
            while last_idx < len(lessons) - 1 and clean_n(lessons[last_idx + 1]) == target_n:
                last_idx += 1

            now_dt = datetime.now()
            fmt = "%H:%M"
            calls = ctx.config.CALLS
            start_dt = datetime.strptime(calls[first_idx][0], fmt)
            end_dt = datetime.strptime(calls[last_idx][1], fmt)
            curr_dt = datetime.strptime(now_dt.strftime(fmt), fmt)

            total_sec = (end_dt - start_dt).seconds
            elapsed_sec = (curr_dt - start_dt).seconds
            percent = min(100, max(0, (elapsed_sec / total_sec) * 100))
            bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))

            lines = ctx.notifier.format_with_overlap(
                message.chat.id,
                m['department'],
                m['group_id'],
                day,
                idx,
                str(curr_l_raw),
                all_data
            )
            res_line = lines[0] if lines else str(curr_l_raw)
            td = end_dt - curr_dt
            h, m_rem = td.seconds // 3600, (td.seconds // 60) % 60
            rem = f"{f'{h}ч ' if h > 0 else ''}{m_rem}м"
            lbl = "До конца блока:" if last_idx > first_idx else "До конца пары:"
            ctx.reply(message, ctx.wrap_code(f"{res_line}\n{bar} {int(percent)}%\n{lbl} {rem}"))


class NextCommand(BaseCommand):
    """Информация о следующей предстоящей паре."""
    name = "next"
    aliases = ["далее", "следующая"]
    description = "Информация о следующей предстоящей паре"
    requires = ["db", "notifier", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_next(message)

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(message, "❌ Нет подписок. Сначала отправь номер группы.")

        day = datetime.now().isoweekday()
        data = ctx.db.get_all_schedules_for_day(day)
        m = mons[0]
        status, _, idx = ctx.notifier.get_status()
        info = get_next_block_info(ctx, message.chat.id, m['department'], m['group_id'], day, data, idx)

        if info:
            res = (
                f"Далее: {info['name']}\n"
                f"Длительность: {format_lessons_count(int(info['count']))}\n"
                f"Через: {info['time_to']}"
            )
            ctx.reply(message, ctx.wrap_code(res))
        else:
            ctx.reply(message, ctx.wrap_code("Пар больше нет") + "\n\n/db")


class ScheduleTodayCommand(BaseCommand):
    """Расписание занятий на сегодня."""
    name = "r"
    aliases = ["сегодня", "расписание"]
    description = "Расписание занятий на сегодня"
    requires = ["db", "notifier", "parser"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_r(message)

        day = datetime.now().isoweekday()
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
        curr_day = datetime.now().isoweekday()
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
        day = datetime.now().isoweekday()
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
                room = ctx.parser.extract_room(l_str)
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

        day = datetime.now().isoweekday()
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
