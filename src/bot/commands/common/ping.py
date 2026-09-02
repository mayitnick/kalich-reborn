from telebot.types import Message
import messages
from src.core.command import BaseCommand
from src.core.container import AppContext


class PingCommand(BaseCommand):
    name = "ping"
    aliases = ["пинг", "живой?"]
    description = "Проверка отклика и работоспособности бота"
    requires = ["db", "config"]

    def execute(self, message: Message, ctx: AppContext):
        settings = ctx.db.get_user_settings(message.chat.id)
        if settings.get('fluffy_mode'):
            ctx.reply(message, messages.PING_FLUFFY)
        else:
            ctx.reply(message, messages.PING_NORMAL)
