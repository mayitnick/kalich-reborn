import telebot


def get_start_roles_markup(webapp_url: str = None):
    """Клавиатура выбора роли/отделения при /start."""
    markup = telebot.types.InlineKeyboardMarkup()
    if webapp_url:
        markup.add(
            telebot.types.InlineKeyboardButton("📱 Открыть мини-приложение", web_app=telebot.types.WebAppInfo(url=webapp_url))
        )
    markup.add(
        telebot.types.InlineKeyboardButton("1️⃣ Первое отделение", callback_data="start_role_1"),
        telebot.types.InlineKeyboardButton("2️⃣ Второе отделение", callback_data="start_role_2")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("3️⃣ Третье отделение", callback_data="start_role_3"),
        telebot.types.InlineKeyboardButton("🧑‍🏫 Я учитель", callback_data="start_role_4")
    )
    return markup


def get_settings_markup(settings):
    """Клавиатура переключения настроек пользователя."""
    markup = telebot.types.InlineKeyboardMarkup()
    notif_btn = "✅ Уведомления" if settings['notifications'] else "❌ Уведомления"
    voice_btn = "✅ Голосовые ответы" if settings['voice_alerts'] else "❌ Голосовые ответы"
    fluffy_btn = "🦊 Fluffy mode" if settings['fluffy_mode'] else "🤖 Строгий бот"
    effect_btn = f"🎧 Эффект: {settings.get('voice_effect', 'echo')}"

    markup.add(telebot.types.InlineKeyboardButton(notif_btn, callback_data="toggle_notifications"))
    markup.add(telebot.types.InlineKeyboardButton(voice_btn, callback_data="toggle_voice_alerts"))
    markup.add(telebot.types.InlineKeyboardButton(effect_btn, callback_data="cycle_voice_effect"))
    markup.add(telebot.types.InlineKeyboardButton(fluffy_btn, callback_data="toggle_fluffy_mode"))
    return markup


def get_teacher_approval_markup(chat_id):
    """Клавиатура для модератора для подтверждения учителя."""
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_teacher_{chat_id}"),
        telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"deny_teacher_{chat_id}")
    )
    return markup
