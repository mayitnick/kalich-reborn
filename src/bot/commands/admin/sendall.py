import re
import time
from telebot.types import Message
from src.core.command import BaseCommand
from src.core.container import AppContext


class SendAllCommand(BaseCommand):
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
