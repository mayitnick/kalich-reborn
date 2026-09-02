"""
Пример расширения функционала бота:
1. Обработка изображений (content_types=['photo'])
2. Текстовые триггеры с регулярными выражениями (text_patterns)
3. Прямое внедрение зависимостей в параметры метода (db, parser, notifier)
"""
from telebot.types import Message
from src.core.command import BaseCommand, command
from src.core.container import AppContext, DatabaseService, ParserService, NotifierService


class PhotoEchoHandler(BaseCommand):
    """Пример обработчика входящих фотографий."""
    name = "photo_echo"
    content_types = ["photo"]
    description = "Демонстрация перехвата изображений"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        if not message.photo:
            return
        best_photo = message.photo[-1]
        caption = message.caption or "без подписи"
        ctx.reply(
            message,
            f"🖼 Получено изображение!\n"
            f"• File ID: `{best_photo.file_id}`\n"
            f"• Размер: {best_photo.width}x{best_photo.height}\n"
            f"• Подпись: {caption}",
            parse_mode="Markdown"
        )


class CallStatusPatternHandler(BaseCommand):
    """
    Пример обработчика текстовой фразы через регулярное выражение.
    Срабатывает на 'когда звонок', 'когда пара?' и т.д.
    Использует прямое внедрение параметров вместо ctx.
    """
    name = "call_status_trigger"
    text_patterns = [r"^когда\s+(пара|звонок)\??$", r"^сколько\s+до\s+конца\??$"]
    description = "Текстовый триггер проверки времени звонка"
    requires = ["notifier"]

    def execute(self, message: Message, notifier: NotifierService, **kwargs):
        status, rem_time, idx = notifier.get_status()
        if status == "rest" or rem_time is None:
            message_text = "Сейчас нет пар или колледж уже закрыт."
        else:
            message_text = f"Текущая пара №{idx+1}. До конца пары осталось: {rem_time}."
        from src.bot.instance import reply_safe
        reply_safe(message, message_text)
