"""
Automatic command scanner, dependency validator, and route dispatcher.
"""
import os
import re
import inspect
import logging
import importlib.util
from typing import List, Dict, Type, Any, Optional
from telebot import TeleBot
from telebot.types import Message

from src.core.container import ServiceContainer, AppContext
from src.core.command import BaseCommand

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Вызывается, если команда требует незарегистрированный модуль/сервис."""
    pass


class CommandScanner:
    """
    Сканирует директорию с командами, проверяет объявленные зависимости
    и регистрирует их в экземпляре TeleBot с автоматическим Dependency Injection.
    """

    def __init__(self, container: ServiceContainer):
        self.container = container
        self.commands: Dict[str, BaseCommand] = {}
        self.handlers_list: List[BaseCommand] = []

    def scan_and_register(self, directory_path: str) -> List[BaseCommand]:
        """
        Рекурсивно сканирует директорию, находит команды,
        валидирует их зависимости и регистрирует в боте.
        """
        discovered = self.discover(directory_path)
        for cmd in discovered:
            self.validate_dependencies(cmd)
            self.register_handler(cmd)
            if cmd.name:
                self.commands[cmd.name.lower()] = cmd
            self.handlers_list.append(cmd)
        logger.info(f"Loaded and registered {len(discovered)} commands from {directory_path}")
        return discovered

    def discover(self, directory_path: str) -> List[BaseCommand]:
        """Обнаруживает классы и экземпляры BaseCommand в указанной директории."""
        commands: List[BaseCommand] = []
        if not os.path.isdir(directory_path):
            logger.warning(f"Directory {directory_path} not found for command scanning.")
            return commands

        for root, _, files in sorted(os.walk(directory_path)):
            for file in sorted(files):
                if file.endswith('.py') and not file.startswith('__'):
                    full_path = os.path.join(root, file)
                    cmds = self._load_from_file(full_path)
                    commands.extend(cmds)
        return commands

    def _load_from_file(self, file_path: str) -> List[BaseCommand]:
        """Динамически загружает модуль и извлекает команды."""
        cmds: List[BaseCommand] = []
        mod_name = os.path.splitext(os.path.basename(file_path))[0]
        spec = importlib.util.spec_from_file_location(f"kalich_cmd_{mod_name}", file_path)
        if not spec or not spec.loader:
            return cmds

        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error loading command file {file_path}: {e}")
            raise

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, BaseCommand):
                if attr not in cmds:
                    cmds.append(attr)
            elif inspect.isclass(attr) and issubclass(attr, BaseCommand) and attr is not BaseCommand:
                inst = attr()
                if inst not in cmds:
                    cmds.append(inst)
        return cmds

    def validate_dependencies(self, cmd: BaseCommand) -> None:
        """Проверяет наличие всех затребованных командой сервисов в контейнере."""
        for req in cmd.requires:
            if not self.container.has(req):
                raise DependencyError(
                    f"Command '{cmd.name or cmd.__class__.__name__}' requires module '{req}', "
                    f"but it is not registered in ServiceContainer!"
                )

    def _create_dispatcher(self, cmd: BaseCommand):
        """Создает обертку вызова с разрешением зависимостей и проверкой ролей."""
        ctx = self.container.create_context()
        sig = inspect.signature(cmd.execute)
        param_names = [p.name for p in sig.parameters.values()]

        def handler(message: Message):
            # Проверка роли
            if cmd.role == "teacher" and not self.container.db.is_teacher(message.chat.id):
                return
            if cmd.role == "moderator" and message.from_user.id not in self.container.config.MODERATOR_IDS:
                return

            # Внедрение зависимостей
            kwargs: Dict[str, Any] = {}
            for name in param_names:
                if name in ('self', 'cls', 'message'):
                    continue
                if name == 'ctx':
                    kwargs['ctx'] = ctx
                elif self.container.has(name):
                    kwargs[name] = self.container.get(name)

            # Если execute ожидает (message, ctx)
            if 'ctx' in param_names:
                return cmd.execute(message, ctx=ctx, **{k: v for k, v in kwargs.items() if k != 'ctx'})
            elif kwargs:
                return cmd.execute(message, **kwargs)
            else:
                return cmd.execute(message, ctx)

        return handler

    def register_handler(self, cmd: BaseCommand) -> None:
        """Регистрирует команду в TeleBot."""
        bot = self.container.bot
        dispatcher = self._create_dispatcher(cmd)

        cmd_names: List[str] = []
        if cmd.name:
            cmd_names.append(cmd.name.lower())

        text_aliases: List[str] = []
        for a in cmd.aliases:
            clean_a = a.strip()
            if clean_a.startswith('/'):
                cmd_names.append(clean_a[1:].lower())
            elif clean_a.isascii() and ' ' not in clean_a and not cmd.text_patterns:
                # Английские алиасы также регистрируем как команды
                cmd_names.append(clean_a.lower())
            else:
                text_aliases.append(clean_a.lower())

        # 1. Регистрация слэш-команд
        if cmd_names:
            bot.message_handler(commands=cmd_names, content_types=cmd.content_types)(dispatcher)

        # 2. Регистрация текстовых алиасов и регулярных выражений
        if text_aliases or cmd.text_patterns:
            compiled_patterns = [re.compile(p, re.IGNORECASE) for p in cmd.text_patterns]

            def match_text(msg: Message) -> bool:
                if not msg.text:
                    return False
                clean_text = msg.text.strip().lower()
                if clean_text in text_aliases:
                    return True
                for cp in compiled_patterns:
                    if cp.search(msg.text):
                        return True
                return False

            bot.message_handler(func=match_text, content_types=["text"])(dispatcher)

        # 3. Регистрация специализированных типов контента (photo, document, voice и т.д.)
        non_text_types = [t for t in cmd.content_types if t != 'text']
        if non_text_types and not cmd_names:
            bot.message_handler(content_types=non_text_types)(dispatcher)
