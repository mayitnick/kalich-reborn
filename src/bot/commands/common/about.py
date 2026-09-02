from telebot.types import Message
import messages
from src.core.command import BaseCommand
from src.core.container import AppContext


class AboutCommand(BaseCommand):
    name = "about"
    aliases = ["о_боте", "инфо"]
    description = "Информация о боте и авторах"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext):
        settings = ctx.db.get_user_settings(message.chat.id)
        if settings.get('fluffy_mode'):
            about_text = messages.ABOUT_FLUFFY
        else:
            about_text = messages.ABOUT_NORMAL
        cmds = [ctx.wrap_code(c) for c in messages.ABOUT_COMMANDS]
        ctx.reply(message, about_text + "\n\n" + "\n\n".join(cmds))
