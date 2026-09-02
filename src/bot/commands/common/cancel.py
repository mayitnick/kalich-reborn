from telebot.types import Message
import messages
import src.config
from src.core.command import BaseCommand
from src.core.container import AppContext


class CancelCommand(BaseCommand):
    name = "cancel"
    aliases = ["отмена", "отменить"]
    description = "Сброс всех активных режимов ввода и диалогов"
    requires = ["config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        cid = message.chat.id
        canceled = False
        state_dicts = (
            src.config.waiting_for_department,
            src.config.user_department,
            src.config.waiting_for_teacher_dept,
            src.config.waiting_for_teacher_rooms,
            src.config.waiting_for_stats_dates,
        )
        for d in state_dicts:
            if cid in d:
                del d[cid]
                canceled = True

        if canceled:
            ctx.reply(message, messages.CANCEL_SUCCESS)
        else:
            ctx.reply(message, messages.CANCEL_NOTHING)
