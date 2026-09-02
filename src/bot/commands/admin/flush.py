from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext


class FlushCommand(BaseCommand):
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
