"""
Интерактивные пасхалки, лор и диалоговые реакции бота (Phase 8.3 & 8.4).
"""
import time
from telebot.types import Message
from src.config import now_msk
from src.core.command import BaseCommand
from src.core.container import AppContext

_USER_CALL_HISTORY: dict[int, list[float]] = {}
_SPAM_WINDOW = 10.0  # 10 секунд
_SPAM_THRESHOLD = 5   # 5 запросов


class LoreChatHandler(BaseCommand):
    """Отклик на имя «Калич» / «Калик», диалоговые пасхалки и реакции на аудио."""
    name = "lore_chat"
    aliases = ["калич", "калик", "kalich"]
    text_patterns = [
        r"(?i)\b(калич|калик)\b",
        r"(?i)\b(спасибо|пасиб|благодарю)\b",
        r"(?i)\b(спокойной ночи|сладких снов)\b",
        r"(?i)\b(я устал|устала|сил нет)\b",
        r"(?i)\b(привет|хай|хеллоу|доброе утро)\b"
    ]
    content_types = ["text", "audio", "voice"]
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        chat_id = message.chat.id
        now = time.time()

        # 1. Детектор спама вызовами (5 частых запросов подряд)
        history = _USER_CALL_HISTORY.get(chat_id, [])
        history = [t for t in history if now - t < _SPAM_WINDOW]
        history.append(now)
        _USER_CALL_HISTORY[chat_id] = history

        if len(history) == _SPAM_THRESHOLD:
            return ctx.reply(
                message,
                "Да слышу я, слышу, наушники не настолько громко играют! [^ v ^] 🎧"
            )

        # 2. Реакция на аудиосообщения и голосовые файлы
        if message.content_type in ("audio", "voice"):
            return ctx.reply(
                message,
                "О, трек в коллекцию? Жаль, мои наушники играют только радио колледжа... 🎧 [｡･ω･｡]"
            )

        text = (message.text or "").strip().lower()

        # 3. Субботние герои первой пары
        current_dt = now_msk()
        if current_dt.isoweekday() == 6 and current_dt.hour in (8, 9):
            if any(w in text for w in ("калич", "калик", "утро", "пары")):
                return ctx.reply(
                    message,
                    "Доброе утречко тем героям, кто встал на первую пару в субботу... держитесь, я с вами [- _ -] ☕"
                )

        # 4. Диалоговые пасхалки без сторонних API (8.4)
        if any(w in text for w in ("спасибо", "пасиб", "благодарю")):
            return ctx.reply(message, "Всегда пожалуйста! Обращайся в любое время [> ‿ <] ✨")

        if "спокойной ночи" in text or "сладких снов" in text:
            return ctx.reply(message, "Доброй ночи! Отдохни как следует перед парами [- _ -] 🌙")

        if any(w in text for w in ("я устал", "устала", "сил нет")):
            return ctx.reply(message, "Держись, студент! Завари чайку, переведи дух... Ты справишься [^ v ^] 🍵")

        # 5. Отклик на имя в чатах (8.3)
        if "калич" in text or "калик" in text:
            return ctx.reply(message, "Да-да, я тут! [^ v ^] Всегда на связи и слушаю колледж!")
