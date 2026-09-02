import urllib.request
import telebot
import logging
from typing import cast, Any
from src.config import BOT_TOKEN

logger = telebot.logger
telebot.logger.setLevel(logging.CRITICAL)

system_proxies = urllib.request.getproxies()
if system_proxies:
    from telebot import apihelper
    cast(Any, apihelper).proxy = system_proxies

# Если токен не задан или не содержит двоеточия (например, при тестах без .env),
# используем fallback токен для возможности безопасной инициализации telebot.
token = BOT_TOKEN if (BOT_TOKEN and ':' in BOT_TOKEN) else '123456:dummy_token_for_init'
bot = telebot.TeleBot(token)


def wrap_code(text):
    """Оборачивает текст в блок кода, заменяя пробелы на ㅤ только в первой строке."""
    if not text:
        return "```...```"
    lines = str(text).split('\n')
    lines[0] = lines[0].replace(" ", "ㅤ")
    joined = '\n'.join(lines)
    return f"```{joined}```"


def reply_safe(message, text, parse_mode='Markdown'):
    """Безопасная отправка сообщения пользователю с сохранением топика."""
    try:
        thread_id = getattr(message, 'message_thread_id', None)
        return bot.send_message(
            message.chat.id,
            text,
            parse_mode=parse_mode,
            message_thread_id=thread_id
        )
    except Exception:
        return None
