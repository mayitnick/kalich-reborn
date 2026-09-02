from telebot.types import Message
import messages
from src.core.command import BaseCommand
from src.core.container import AppContext


class HelpCommand(BaseCommand):
    name = "help"
    aliases = ["помощь", "справка"]
    description = "Подробное руководство по использованию бота"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        help_text = messages.HELP_TEXT_MAIN

        if ctx.db.is_teacher(message.chat.id):
            help_text += messages.HELP_TEXT_TEACHER

        help_text += messages.HELP_TEXT_EXTRA
        ctx.reply(message, help_text)
