import re
from datetime import datetime
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext
from src.bot.handlers.teacher import cmd_teacher_next


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
                        day: int, data: dict, current_idx: int = None):
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


class NextCommand(BaseCommand):
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
                f"Длительность: {format_lessons_count(info['count'])}\n"
                f"Через: {info['time_to']}"
            )
            ctx.reply(message, ctx.wrap_code(res))
        else:
            ctx.reply(message, ctx.wrap_code("Пар больше нет") + "\n\n/db")
