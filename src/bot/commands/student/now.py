import re
from datetime import datetime
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext
from src.bot.handlers.teacher import cmd_teacher_now


class NowCommand(BaseCommand):
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
