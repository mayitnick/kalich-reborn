"""
Общие команды бота для всех пользователей.
"""
from datetime import datetime
import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import messages
import src.config
from src.config import now_msk
from src.core.command import BaseCommand
from src.core.container import AppContext, NotifierService
from src.bot.instance import reply_safe, logger




[]
class PingCommand(BaseCommand):
    """Проверка отклика и работоспособности бота."""
    name = "ping"
    aliases = ["пинг", "живой?"]
    description = "Проверка отклика и работоспособности бота"
    requires = ["db", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        settings = ctx.db.get_user_settings(message.chat.id)
        if settings.get('fluffy_mode'):
            ctx.reply(message, messages.PING_FLUFFY)
        else:
            ctx.reply(message, messages.PING_NORMAL)


class AboutCommand(BaseCommand):
    """Информация о боте и авторах."""
    name = "about"
    aliases = ["о_боте", "инфо"]
    description = "Информация о боте и авторах"
    requires = ["db"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        settings = ctx.db.get_user_settings(message.chat.id)
        if settings.get('fluffy_mode'):
            about_text = messages.ABOUT_FLUFFY
        else:
            about_text = messages.ABOUT_NORMAL
        cmds = [ctx.wrap_code(c) for c in messages.ABOUT_COMMANDS]
        ctx.reply(message, about_text + "\n\n" + "\n\n".join(cmds))


class CancelCommand(BaseCommand):
    """Сброс всех активных режимов ввода и диалогов."""
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


class HelpCommand(BaseCommand):
    """Справка по командам бота."""
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


class TimeCommand(BaseCommand):
    """Расписание звонков и оставшееся время до конца занятий."""
    name = "time"
    aliases = ["звонки", "время"]
    description = "Расписание звонков и таймер до конца учебного дня"
    requires = ["notifier", "config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        status, left, _ = ctx.notifier.get_status()
        now = now_msk()
        wd = now.isoweekday()
        curr_time = now.strftime("%H:%M")
        calls = ctx.config.CALLS

        if wd == 1:
            monday_calls = list(calls[:8])
            monday_calls.append(("14:50", "15:35"))
            calls_to_show = monday_calls
            end_time = datetime.strptime("15:35", "%H:%M")
        else:
            max_l = 8 if 2 <= wd <= 5 else 0
            calls_to_show = calls[:max_l]
            if max_l > 0:
                end_time = datetime.strptime(calls[max_l - 1][1], "%H:%M")
            else:
                end_time = None

        if status == 'work' and end_time:
            curr_dt = datetime.strptime(curr_time, "%H:%M")
            if curr_dt < end_time:
                td = end_time - curr_dt
                h, m = td.seconds // 3600, (td.seconds // 60) % 60
                left = f"{f'{h}ч ' if h > 0 else ''}{m}м"
            else:
                left = "0м"
        header = f"До конца дня: {left}" if status != 'rest' else "Отдыхай"

        res = f"{header}\n" + "\n".join([f"{i+1}. {c[0]} - {c[1]}" for i, c in enumerate(calls_to_show)])
        ctx.reply(message, ctx.wrap_code(res))


class StartCommand(BaseCommand):
    """Инициализация, выбор отделения или роли преподавателя."""
    name = "start"
    aliases = ["старт"]
    description = "Инициализация и стартовый выбор роли"
    requires = ["db", "config", "bot"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        ctx.config.waiting_for_department[message.chat.id] = True
        if message.chat.id in ctx.config.user_department:
            del ctx.config.user_department[message.chat.id]
        settings = ctx.db.get_user_settings(message.chat.id)
        if settings.get('fluffy_mode'):
            welcome_text = (
                "👋 Привет! Я — Калич, ваш пушистый лисёнок‑помощник! 🦊\n"
                "С радостью помогу вам быстро узнать расписание и любые замены.\n\n"
                "Выберите свою роль:"
            )
        else:
            welcome_text = (
                "Добро пожаловать в систему расписания.\n"
                "Пожалуйста, выберите вашу роль:"
            )
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("1️⃣ Первое отделение", callback_data="start_role_1"),
            InlineKeyboardButton("2️⃣ Второе отделение", callback_data="start_role_2")
        )
        markup.add(
            InlineKeyboardButton("3️⃣ Третье отделение", callback_data="start_role_3"),
            InlineKeyboardButton("🧑‍🏫 Я учитель", callback_data="start_role_4")
        )
        try:
            ctx.bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Start command error: {e}")


class SettingsCommand(BaseCommand):
    """Меню персональных настроек пользователя."""
    name = "settings"
    aliases = ["настройки"]
    description = "Настройки бота (уведомления, fluffy mode, эффекты)"
    requires = ["db", "bot"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        settings = ctx.db.get_user_settings(message.chat.id)
        markup = InlineKeyboardMarkup()
        notif_btn = "✅ Уведомления" if settings['notifications'] else "❌ Уведомления"
        voice_btn = "✅ Голосовые ответы" if settings['voice_alerts'] else "❌ Голосовые ответы"
        fluffy_btn = "🦊 Fluffy mode" if settings['fluffy_mode'] else "🤖 Строгий бот"
        effect_btn = f"🎧 Эффект: {settings.get('voice_effect', 'echo')}"

        markup.add(InlineKeyboardButton(notif_btn, callback_data="toggle_notifications"))
        markup.add(InlineKeyboardButton(voice_btn, callback_data="toggle_voice_alerts"))
        markup.add(InlineKeyboardButton(effect_btn, callback_data="cycle_voice_effect"))
        markup.add(InlineKeyboardButton(fluffy_btn, callback_data="toggle_fluffy_mode"))

        msg_text = "⚙️ Ваши настройки:\n(Включите Fluffy mode, если хотите чтобы бот общался как милый лисёнок!)"
        ctx.bot.send_message(message.chat.id, msg_text, reply_markup=markup)


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


class WebappCommand(BaseCommand):
    """Открыть Telegram Mini App с расписанием."""
    name = "webapp"
    aliases = ["app", "мини_приложение", "расписание_апп"]
    description = "Открыть интерактивное мини-приложение расписания"
    requires = ["config"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        url = getattr(src.config, 'WEBAPP_URL', '') or "https://kalich.example.com"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📱 Открыть расписание", web_app=telebot.types.WebAppInfo(url=url))
        )
        ctx.reply(message, "Нажмите кнопку ниже, чтобы открыть мини-приложение:", reply_markup=markup)


class CallStatusPatternHandler(BaseCommand):
    """Текстовый триггер проверки времени звонка."""
    name = "call_status_trigger"
    text_patterns = [r"^когда\s+(пара|звонок)\??$", r"^сколько\s+до\s+конца\??$"]
    description = "Текстовый триггер проверки времени звонка"
    requires = ["notifier"]

    def execute(self, message: Message, ctx: AppContext, **kwargs):
        status, rem_time, idx = ctx.notifier.get_status()
        if status == "rest" or rem_time is None or idx is None:
            message_text = "Сейчас нет пар или колледж уже закрыт."
        else:
            message_text = f"Текущая пара №{idx + 1}. До конца пары осталось: {rem_time}."
        reply_safe(message, message_text)


__all__ = [
    "PingCommand",
    "AboutCommand",
    "CancelCommand",
    "HelpCommand",
    "TimeCommand",
    "StartCommand",
    "SettingsCommand",
    "PhotoEchoHandler",
    "CallStatusPatternHandler",
    "WebappCommand",
]

