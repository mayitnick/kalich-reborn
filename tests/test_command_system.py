import pytest
from unittest.mock import MagicMock
from telebot.types import Message, PhotoSize

from src.core.container import ServiceContainer, AppContext, DatabaseService, NotifierService
from src.core.command import BaseCommand, command
from src.core.scanner import CommandScanner, DependencyError


def test_service_container_initialization():
    container = ServiceContainer()
    assert container.has("db")
    assert container.has("database")
    assert container.has("parser")
    assert container.has("analytics")
    assert container.has("notifier")
    assert container.has("config")
    assert container.has("bot")
    assert not container.has("unknown_module")

    # Test custom service registration
    custom_obj = {"key": "value"}
    container.register("custom_service", custom_obj)
    assert container.has("custom_service")
    assert container.get("custom_service") == custom_obj

    # Test context creation
    ctx = container.create_context()
    assert isinstance(ctx, AppContext)
    assert ctx.db is container.db
    assert ctx.database is container.db
    assert ctx.parser is container.parser
    assert ctx.analytics is container.analytics
    assert ctx.notifier is container.notifier
    assert ctx.get_service("custom_service") == custom_obj


def test_command_discovery():
    container = ServiceContainer()
    scanner = CommandScanner(container)
    cmds = scanner.discover("src/bot/commands")
    cmd_names = [c.name for c in cmds]

    assert "ping" in cmd_names
    assert "about" in cmd_names
    assert "photo_echo" in cmd_names
    assert "call_status_trigger" in cmd_names


def test_dependency_validation_success():
    container = ServiceContainer()
    scanner = CommandScanner(container)

    class ValidCmd(BaseCommand):
        name = "valid"
        requires = ["db", "parser"]

    scanner.validate_dependencies(ValidCmd())


def test_dependency_validation_failure():
    container = ServiceContainer()
    scanner = CommandScanner(container)

    class InvalidCmd(BaseCommand):
        name = "invalid"
        requires = ["db", "nonexistent_super_service"]

    with pytest.raises(DependencyError) as exc_info:
        scanner.validate_dependencies(InvalidCmd())

    assert "nonexistent_super_service" in str(exc_info.value)


def test_dispatcher_parameter_injection():
    mock_bot = MagicMock()
    container = ServiceContainer(bot=mock_bot)
    scanner = CommandScanner(container)

    called_args = {}

    class InjectedCmd(BaseCommand):
        name = "injected"
        requires = ["notifier"]

        def execute(self, message, notifier: NotifierService):
            called_args['message'] = message
            called_args['notifier'] = notifier

    dispatcher = scanner._create_dispatcher(InjectedCmd())

    mock_msg = MagicMock()
    mock_msg.chat.id = 123
    mock_msg.from_user.id = 456

    dispatcher(mock_msg)
    assert called_args['message'] == mock_msg
    assert called_args['notifier'] is container.notifier


def test_functional_command_decorator():
    called = []

    @command(name="deco_cmd", aliases=["деко"], requires=["config"])
    def my_handler(message, ctx: AppContext):
        called.append(ctx)

    assert isinstance(my_handler, BaseCommand)
    assert my_handler.name == "deco_cmd"
    assert my_handler.aliases == ["деко"]
    assert my_handler.requires == ["config"]

    container = ServiceContainer()
    scanner = CommandScanner(container)
    scanner.validate_dependencies(my_handler)

    dispatcher = scanner._create_dispatcher(my_handler)
    mock_msg = MagicMock()
    mock_msg.chat.id = 123
    mock_msg.from_user.id = 456
    dispatcher(mock_msg)

    assert len(called) == 1
    assert isinstance(called[0], AppContext)
