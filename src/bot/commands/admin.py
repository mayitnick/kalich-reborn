"""
Административные команды, статистика и управление рассылками.
"""
import re
import json
import time
import hashlib
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext





class FillCommand(BaseCommand):
    """Принудительное наполнение локального кэша базы данных (только модераторы)."""
    name = "fill"
    aliases = ["заполнить_бд"]
    description = "Принудительное наполнение локального кэша базы данных (только модераторы)"
    requires = ["db", "parser", "config"]
    role = "moderator"

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if message.from_user.id not in ctx.config.MODERATOR_IDS:
            return

        ctx.reply(message, "⏳ Заполнение базы (ПН-ПТ) для всех отделений...")
        try:
            c = 0
            for d in [1, 2, 3, 4, 5]:
                date_str = ctx.db.get_date_for_weekday(d)
                for name, info in ctx.parser.GROUP_NAME_TO_ID.items():
                    dep, gid = info[0], info[1]
                    raw = ctx.parser.fetch_lessons(d, gid, dep)
                    if raw:
                        h = hashlib.md5("".join(raw).encode()).hexdigest()
                        ctx.db.save_schedule_to_db(
                            dep, gid, d, h, json.dumps(raw, ensure_ascii=False), date_str
                        )
                        c += 1
                    time.sleep(0.05)
            ctx.reply(message, f"✅ База заполнена! Записей: {c}")
        except Exception as e:
            ctx.reply(message, f"❌ Ошибка: {e}")


class FlushCommand(BaseCommand):
    """Очистка локального кэша расписания (только модераторы)."""
    name = "flush"
    aliases = ["очистить_бд"]
    description = "Очистка локального кэша расписания (только модераторы)"
    requires = ["db", "config"]
    role = "moderator"

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if message.from_user.id in ctx.config.MODERATOR_IDS:
            conn = ctx.db.get_connection()
            conn.execute("DELETE FROM schedules")
            conn.commit()
            conn.close()
            ctx.reply(message, "♻️ База очищена.")


class SendAllCommand(BaseCommand):
    """Рассылка объявлений во все активные чаты (только модераторы)."""
    name = "sendall"
    aliases = ["рассылка"]
    description = "Рассылка объявлений во все активные чаты (только для модераторов)"
    requires = ["db", "config", "bot"]
    role = "moderator"

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if message.from_user.id not in ctx.config.MODERATOR_IDS:
            return

        source_text = ""
        if message.reply_to_message:
            source_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        else:
            source_text = message.text.replace('/sendall', '', 1).strip()

        if not source_text:
            return ctx.reply(message, "⚠️ Нет текста для рассылки.")

        header = "Новости:ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ"
        full_block_text = f"```{header}\n{source_text}```"
        found_commands = re.findall(r'(/[a-zA-Z0-9_]+)', source_text)
        commands_message = " ".join(dict.fromkeys(found_commands))

        sent_targets = set()
        monitors = ctx.db.monitor_manager.active_monitors.values()

        for m in monitors:
            cid = m['chat_id']
            thread = m.get('message_thread_id') or ctx.config.SPECIAL_CHATS.get(cid)
            target_key = (cid, thread)
            if target_key in sent_targets:
                continue
            sent_targets.add(target_key)
            try:
                ctx.bot.send_message(
                    cid,
                    full_block_text,
                    parse_mode='Markdown',
                    message_thread_id=thread
                )
                if commands_message:
                    ctx.bot.send_message(cid, commands_message, message_thread_id=thread)
                time.sleep(0.1)
            except Exception:
                continue

        ctx.reply(message, "✅ Рассылка выполнена.")


class MemCommand(BaseCommand):
    """Кастомное переименование предмета/замена наименования для чата."""
    name = "mem"
    aliases = ["замена_предмета", "алиас"]
    description = "Кастомное переименование предметов для чата"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        raw_text = message.text.replace('/mem', '', 1).strip()
        sep = next((s for s in ['-', '—', ':'] if s in raw_text), None)
        if not sep:
            return ctx.reply(
                message, ctx.wrap_code("Ошибка.\nФормат: /mem Предмет - Замена")
            )
        try:
            old, new = [p.strip() for p in raw_text.split(sep, 1)]
            ctx.db.custom_names_manager.set_name(message.chat.id, old, new)
            ctx.reply(message, ctx.wrap_code(f"Успех.\n{old} -> {new}"))
        except Exception:
            ctx.reply(message, ctx.wrap_code("Ошибка."))


class StatsCommand(BaseCommand):
    """Аналитические отчеты и инфографика по загруженности групп, преподавателей и кабинетов."""
    name = "stats"
    aliases = ["статистика", "график"]
    description = "Аналитические отчеты и инфографика по загруженности групп, преподавателей и кабинетов"
    requires = ["db", "analytics", "parser", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        text_args = message.text.replace('/stats', '', 1).strip()

        # Парсинг диапазона дат
        start_date, end_date = ctx.db.parse_date_range(text_args)
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
                    return ctx.reply(message, ctx.wrap_code("❌ Укажите имя преподавателя.\nПример: /stats учитель Hhh"))

                conn = ctx.db.get_connection()
                res = conn.execute(
                    "SELECT chat_id, name, department, rooms FROM teachers WHERE name LIKE ? AND status='approved'",
                    (f"%{name_query}%",)
                ).fetchall()
                conn.close()
                if not res:
                    return ctx.reply(message, ctx.wrap_code(f"❌ Преподаватель '{name_query}' не найден или не одобрен."))
                elif len(res) > 1:
                    match_list = "\n".join([f"- {r[1]} (отд.{r[2]})" for r in res])
                    return ctx.reply(message, ctx.wrap_code(f"🔍 Найдено несколько преподавателей:\n{match_list}\nУточните запрос."))

                teacher_chat_id, target_name, dept, rooms_json = res[0]
                target_id = json.loads(rooms_json)
                target_type = 'teacher'
            elif first in ['каб', 'room', 'кабинет']:
                room_query = " ".join(tokens[1:]).strip()
                if not room_query:
                    return ctx.reply(message, ctx.wrap_code("❌ Укажите номер кабинета.\nПример: /stats каб 44"))
                target_id = [room_query]
                target_name = f"Кабинет {room_query}"
                target_type = 'room'
                mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
                dept = mons[0]['department'] if mons else 1
            else:
                group_query = clean_args.upper()
                clean_query = group_query.replace('-', ' ').replace('_', ' ')
                group_info = None

                for k, v in ctx.parser.GROUP_NAME_TO_ID.items():
                    if clean_query == k.upper().replace('-', ' ') or group_query == k.upper():
                        group_info = v
                        target_name = k
                        break
                if not group_info:
                    for k, v in ctx.parser.GROUP_NAME_TO_ID.items():
                        if clean_query in k.upper().replace('-', ' ').split():
                            group_info = v
                            target_name = k
                            break

                if group_info:
                    dept, target_id = group_info[0], group_info[1]
                    target_type = 'group'
                else:
                    return ctx.reply(message, ctx.wrap_code(f"❌ Группа или команда '{clean_args}' не распознана."))
        else:
            if ctx.db.is_teacher(message.chat.id):
                dept, rooms = ctx.db.get_teacher_info(message.chat.id)
                target_id = rooms
                conn = ctx.db.get_connection()
                row = conn.execute("SELECT name FROM teachers WHERE chat_id=?", (message.chat.id,)).fetchone()
                conn.close()
                target_name = row[0] if row else "Моя нагрузка"
                target_type = 'teacher'
            else:
                mons = ctx.db.monitor_manager.get_user_monitors(message.chat.id)
                if mons:
                    dept, target_id = mons[0]['department'], mons[0]['group_id']
                    target_name = mons[0]['group_name']
                    target_type = 'group'
                else:
                    import kalich
                    return kalich.show_general_stats_menu(message)

        # Сохраняем сессию
        ctx.config.stats_context[message.chat.id] = {
            'target_type': target_type,
            'target_id': target_id,
            'target_name': target_name,
            'dept': dept,
            'start_date': start_date,
            'end_date': end_date
        }

        import kalich
        kalich.show_target_stats_menu_by_chat_id(message.chat.id, getattr(message, 'message_thread_id', None))


__all__ = [
    "FillCommand",
    "FlushCommand",
    "SendAllCommand",
    "MemCommand",
    "StatsCommand",
]

