"""
Command abstractions, metadata, and registration decorators.
"""
from typing import List, Optional, Callable, Any, Dict
import inspect
from telebot.types import Message
from src.core.container import AppContext, ServiceContainer


class BaseCommand:
    """
    Базовый класс для создания команд бота с поддержкой Dependency Injection.
    Каждая команда декларирует свои триггеры и требуемые сервисы.
    """
    name: str = ""                         # Имя команды (без слэша), например "ping"
    aliases: List[str] = []                # Дополнительные команды или текстовые алиасы
    text_patterns: List[str] = []          # Регулярные выражения для текстовых триггеров
    content_types: List[str] = ["text"]    # Типы контента: text, photo, document, voice, sticker
    requires: List[str] = []               # Требуемые сервисы: 'db', 'parser', 'analytics', 'notifier'
    description: str = ""                  # Описание для справки
    role: str = "all"                      # Роль: 'all', 'teacher', 'moderator', 'student'

    def execute(self, message: Message, ctx: AppContext, **kwargs) -> Any:
        """
        Основной метод выполнения команды.
        Может принимать:
        - (message, ctx: AppContext)
        - или напрямую запрошенные модули: (message, db, parser)
        """
        raise NotImplementedError(f"Command '{self.name}' must implement execute().")


def command(name: str = "", aliases: Optional[List[str]] = None,
            content_types: Optional[List[str]] = None,
            text_patterns: Optional[List[str]] = None,
            requires: Optional[List[str]] = None,
            description: str = "",
            role: str = "all"):
    """
    Декоратор для создания функциональных команд бота.

    Пример:
    @command(name="ping", aliases=["пинг"], requires=["db"])
    def cmd_ping(message, ctx: AppContext):
        ctx.reply(message, "Понг!")
    """
    def decorator(fn: Callable) -> BaseCommand:
        cmd_name = name or fn.__name__.replace('cmd_', '').replace('handle_', '')
        cmd_cls = type(
            f"FuncCmd_{cmd_name}",
            (BaseCommand,),
            {
                "name": cmd_name,
                "aliases": aliases or [],
                "content_types": content_types or ["text"],
                "text_patterns": text_patterns or [],
                "requires": requires or [],
                "description": description or (fn.__doc__.strip() if fn.__doc__ else ""),
                "role": role,
                "execute": staticmethod(fn)
            }
        )
        return cmd_cls()
    return decorator
