import re
from datetime import datetime
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext
from src.bot.handlers.teacher import cmd_teacher_r, cmd_teacher_db


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


class ScheduleTodayCommand(BaseCommand):
    name = "r"
    aliases = ["сегодня", "расписание"]
    description = "Расписание занятий на сегодня"
    requires = ["db", "notifier"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if ctx.db.is_teacher(message.chat.id):
            return cmd_teacher_r(message)

        day = datetime.now().isoweekday()
        if day > 5:
            return ctx.reply(message, ctx.wrap_code("Отдыхай (выходной)"))

        mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
        if not mons:
            return ctx.reply(message, "❌ Нет подписок.")

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
    name = "db"
    aliases = ["архив", "неделя"]
    description = "Расписание по дням недели или конкретной дате"
    requires = ["db", "notifier"]

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
                all_data = ctx.db.apply_teacher_overrides(all_data, target_weekday)
                for m in mons:
                    header = f"🗄 Архив ({args}): {m['group_name']}"
                    render_schedule_msg(ctx, message, m, all_data, target_weekday, header)
                return
            except ValueError:
                return ctx.reply(message, "❌ Неверный формат даты.")

        target_day = day_map.get(args)
        if target_day is not None:
            all_data = ctx.db.get_all_schedules_for_day(target_day)
            all_data = ctx.db.apply_teacher_overrides(all_data, target_day)
            for m in mons:
                header = f"📅 {day_labels[target_day]}: {m['group_name']}"
                render_schedule_msg(ctx, message, m, all_data, target_day, header)
            return

        # Если без аргументов — выводим всю неделю
        for m in mons:
            for d in range(1, 7):
                all_data = ctx.db.get_all_schedules_for_day(d)
                all_data = ctx.db.apply_teacher_overrides(all_data, d)
                header = f"📅 {day_labels[d]}: {m['group_name']}"
                render_schedule_msg(ctx, message, m, all_data, d, header)
