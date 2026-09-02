import json
import time
import hashlib
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext


class FillCommand(BaseCommand):
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
