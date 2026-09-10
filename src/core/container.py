"""
Dependency Injection & Service Container for Kalich Bot.
Provides strongly-typed services and AppContext for IDE autocompletion.
"""
from typing import Any, Dict, Optional, List, Callable, Tuple
import telebot
from telebot import TeleBot
from telebot.types import Message, InlineKeyboardMarkup, ReplyKeyboardMarkup

import src.config as _config
import src.database as _database
import src.services.parser as _parser
import src.services.analytics as _analytics
import src.services.notifier as _notifier
from src.bot.instance import reply_safe as _reply_safe, wrap_code as _wrap_code


class ConfigService:
    """Типизированный доступ к конфигурации проекта и системным параметрам."""

    def __init__(self, mod=_config):
        self._mod = mod

    @property
    def DB_FILE(self) -> str:
        return getattr(self._mod, 'DB_FILE', 'data/schedules.db')

    @property
    def CALLS(self) -> List[Tuple[str, str]]:
        return getattr(self._mod, 'CALLS', [])

    @property
    def MODERATOR_IDS(self) -> List[int]:
        return getattr(self._mod, 'MODERATOR_IDS', [])

    @property
    def SPECIAL_CHATS(self) -> Dict[int, int]:
        return getattr(self._mod, 'SPECIAL_CHATS', {})

    @property
    def APPROVED_TEACHER_IDS(self) -> List[int]:
        return getattr(self._mod, 'APPROVED_TEACHER_IDS', [])

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mod, name)


class DatabaseService:
    """Типизированный слой работы с базой данных SQLite и менеджерами."""

    def __init__(self, mod=_database):
        self._mod = mod

    def get_connection(self):
        """Возвращает соединение SQLite с включенным режимом WAL и timeout."""
        return self._mod.get_db_connection()

    def init_db(self) -> None:
        """Инициализирует таблицы базы данных."""
        self._mod.init_db()

    def save_schedule_to_db(self, department: int, group_id: int, day: int,
                            content_hash: str, lessons_json: str, date_str: str = "") -> None:
        """Сохраняет расписание в кэш и историю."""
        self._mod.save_schedule_to_db(department, group_id, day, content_hash, lessons_json, date_str)

    def get_all_schedules_for_day(self, day: int) -> Dict[Tuple[int, int], list]:
        """Возвращает расписание всех групп на указанный день недели."""
        return self._mod.get_all_schedules_for_day(day)

    def get_schedule_history_for_date(self, date_str: str) -> Dict[Tuple[int, int], list]:
        """Возвращает историческое расписание за дату (ГГГГ-ММ-ДД)."""
        return self._mod.get_schedule_history_for_date(date_str)

    def is_teacher(self, chat_id: int) -> bool:
        """Проверяет, зарегистрирован и одобрен ли учитель."""
        return self._mod.is_teacher(chat_id)

    def get_teacher_info(self, chat_id: int) -> Tuple[Optional[int], List[str]]:
        """Возвращает (отделение, список кабинетов) учителя."""
        return self._mod.get_teacher_info(chat_id)

    def save_teacher_override(self, chat_id: int, department: int, day: int,
                              slot_idx: int, group_id: int, new_room: Optional[str] = None,
                              new_subject: Optional[str] = None) -> None:
        """Сохраняет замену кабинета или предмета от преподавателя."""
        self._mod.save_teacher_override(chat_id, department, day, slot_idx, group_id, new_room, new_subject)

    def apply_teacher_overrides(self, all_data: dict, day: int) -> dict:
        """Применяет действующие замены преподавателей к расписанию."""
        return self._mod.apply_teacher_overrides(all_data, day)

    def get_teacher_schedule(self, chat_id: int, day: int, all_data: dict, date_str: str = ""):
        """Формирует расписание конкретного учителя по его кабинетам."""
        return self._mod.get_teacher_schedule(chat_id, day, all_data, date_str)

    def get_user_settings(self, chat_id: int) -> dict:
        """Возвращает настройки пользователя (fluffy_mode, time_display_mode и т.д.)."""
        return self._mod.get_user_settings(chat_id)

    def set_user_setting(self, chat_id: int, key: str, value: Any) -> None:
        """Устанавливает значение настройки пользователя."""
        self._mod.set_user_setting(chat_id, key, value)

    def extract_room(self, lesson_text: str) -> Optional[str]:
        """Извлекает номер кабинета из текста пары."""
        return self._mod.extract_room(lesson_text)

    @property
    def monitor_manager(self):
        """Менеджер подписок пользователей на группы."""
        return self._mod.monitor_manager

    @property
    def custom_names_manager(self):
        """Менеджер пользовательских переименований предметов."""
        return self._mod.custom_names_manager

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mod, name)


class ParserService:
    """Типизированный сервис парсинга страниц колледжа и кэширования групп."""

    def __init__(self, mod=_parser):
        self._mod = mod

    @property
    def GROUP_NAME_TO_ID(self) -> Dict[str, List[int]]:
        return self._mod.GROUP_NAME_TO_ID

    @property
    def GROUP_ID_TO_NAME(self) -> Dict[int, Dict[int, str]]:
        return self._mod.GROUP_ID_TO_NAME

    def find_group_info(self, group_name: str) -> Tuple[Optional[str], Optional[List[int]]]:
        """Нестрогий поиск группы по названию. Возвращает (каноническое_имя, [отделение, id])."""
        return self._mod.find_group_info(group_name)

    def fetch_lessons(self, day: int, group_id: int, department: int) -> List[str]:
        """Загружает список уроков на день для указанной группы."""
        return self._mod.fetch_lessons(day, group_id, department)

    def get_department_groups(self, department: int) -> List[str]:
        """Возвращает отсортированный список всех групп выбранного отделения."""
        return self._mod.get_department_groups(department)

    def extract_room(self, lesson_text: str) -> Optional[str]:
        """Извлекает номер кабинета из текста пары."""
        return getattr(self._mod, 'extract_room', _database.extract_room)(lesson_text)

    def load_groups_cache(self) -> None:
        """Загружает кэш групп из файла."""
        self._mod.load_groups_cache()

    def update_groups_cache(self) -> None:
        """Обновляет кэш групп с сайтов всех 3 отделений."""
        self._mod.update_groups_cache()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mod, name)


class AnalyticsService:
    """Типизированный сервис генерации аналитических диаграмм и инфографики."""

    def __init__(self, mod=_analytics):
        self._mod = mod

    def generate_group_subject_chart(self, group_id: int, department: int,
                                     group_name: str, start_date: str = None,
                                     end_date: str = None):
        """Генерирует круговую диаграмму распределения предметов группы в BytesIO."""
        return self._mod.generate_group_subject_chart(group_id, department, group_name, start_date, end_date)

    def generate_group_daily_chart(self, group_id: int, department: int,
                                   group_name: str, start_date: str = None,
                                   end_date: str = None):
        """Генерирует столбчатую диаграмму нагрузки группы по дням недели."""
        return self._mod.generate_group_daily_chart(group_id, department, group_name, start_date, end_date)

    def generate_teacher_daily_chart(self, rooms: list, department: int,
                                     start_date: str = None, end_date: str = None):
        """Генерирует диаграмму нагрузки преподавателя по дням недели."""
        return self._mod.generate_teacher_daily_chart(rooms, department, start_date, end_date)

    def generate_teacher_groups_chart(self, rooms: list, department: int,
                                      start_date: str = None, end_date: str = None):
        """Генерирует диаграмму групп, занимающихся в кабинетах преподавателя."""
        return self._mod.generate_teacher_groups_chart(rooms, department, start_date, end_date)

    def generate_time_distribution_chart(self, group_id: int, department: int,
                                         group_name: str, start_date: str = None,
                                         end_date: str = None):
        """Генерирует тепловую диаграмму распределения пар по времени."""
        return self._mod.generate_time_distribution_chart(group_id, department, group_name, start_date, end_date)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mod, name)


class NotifierService:
    """Типизированный сервис уведомлений, расписания звонков и фоновых проверок."""

    def __init__(self, mod=_notifier):
        self._mod = mod

    def get_status(self) -> Tuple[str, Optional[str], Optional[int]]:
        """Определяет статус текущего занятия (work/rest), время до конца и индекс пары."""
        return self._mod.get_status()

    def format_with_overlap(self, chat_id: int, department: int, gid: int,
                            day: int, idx: int, raw_text: str, all_day_data: dict) -> List[str]:
        """Форматирует строку пары с учетом совмещений кабинетов с другими группами."""
        return self._mod.format_with_overlap(chat_id, department, gid, day, idx, raw_text, all_day_data)

    def send_updates_for_day(self, day: int, all_data: dict) -> None:
        """Рассылает уведомления об изменении расписания подписанным пользователям."""
        self._mod.send_updates_for_day(day, all_data)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mod, name)


class AppContext:
    """
    Контекст выполнения команды с полной поддержкой автодополнения (IDE type hints).
    Предоставляет централизованный доступ ко всем сервисам и утилитам взаимодействия.
    """

    def __init__(self, bot: TeleBot, config: ConfigService, database: DatabaseService,
                 parser: ParserService, analytics: AnalyticsService, notifier: NotifierService,
                 services: Optional[Dict[str, Any]] = None):
        self.bot: TeleBot = bot
        self.config: ConfigService = config
        self.db: DatabaseService = database
        self.database: DatabaseService = database  # Удобный алиас
        self.parser: ParserService = parser
        self.analytics: AnalyticsService = analytics
        self.notifier: NotifierService = notifier
        self.services: Dict[str, Any] = services or {}

    def reply(self, message: Message, text: str, **kwargs) -> Optional[Message]:
        """Безопасно отправляет ответ пользователю в правильный тред чата."""
        import sys
        kalich_mod = sys.modules.get('kalich')
        reply_fn = getattr(kalich_mod, 'reply_safe', _reply_safe) if kalich_mod else _reply_safe
        return reply_fn(message, text, **kwargs)


    def wrap_code(self, text: str) -> str:
        """Оборачивает текст в блок моноширинного кода Markdown."""
        return _wrap_code(text)

    def get_service(self, name: str) -> Any:
        """Возвращает зарегистрированный сервис по имени."""
        if name in ('db', 'database'):
            return self.db
        if name == 'parser':
            return self.parser
        if name == 'analytics':
            return self.analytics
        if name == 'notifier':
            return self.notifier
        if name == 'config':
            return self.config
        if name == 'bot':
            return self.bot
        return self.services.get(name)


class ServiceContainer:
    """
    Реестр и контейнер зависимостей (Dependency Injection Container).
    Инициализирует сервисы один раз в основном файле и передает их командам.
    """

    def __init__(self, bot: Optional[TeleBot] = None):
        from src.bot.instance import bot as default_bot
        self.bot: TeleBot = bot or default_bot
        self.config = ConfigService()
        self.db = DatabaseService()
        self.parser = ParserService()
        self.analytics = AnalyticsService()
        self.notifier = NotifierService()
        self._custom_services: Dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """Регистрирует дополнительный пользовательский сервис."""
        self._custom_services[name] = service

    def get(self, name: str) -> Any:
        """Возвращает зарегистрированный сервис по имени."""
        if name in ('db', 'database'):
            return self.db
        if name == 'parser':
            return self.parser
        if name == 'analytics':
            return self.analytics
        if name == 'notifier':
            return self.notifier
        if name == 'config':
            return self.config
        if name == 'bot':
            return self.bot
        return self._custom_services.get(name)

    def has(self, name: str) -> bool:
        """Проверяет наличие сервиса в контейнере."""
        standard = ('db', 'database', 'parser', 'analytics', 'notifier', 'config', 'bot')
        return name in standard or name in self._custom_services

    def create_context(self) -> AppContext:
        """Создает экземпляр типизированного AppContext."""
        return AppContext(
            bot=self.bot,
            config=self.config,
            database=self.db,
            parser=self.parser,
            analytics=self.analytics,
            notifier=self.notifier,
            services=self._custom_services
        )
