import unittest
from unittest.mock import patch, MagicMock

class MockTeleBot(MagicMock):
    def message_handler(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def callback_query_handler(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def send_chat_action(self, *args, **kwargs):
        pass

patch('telebot.TeleBot', MockTeleBot).start()

import kalich


class TestKalichCommands(unittest.TestCase):
    def setUp(self):
        # Создаем мок-объект сообщения
        self.message = MagicMock()
        self.message.chat.id = 123456789
        self.message.message_thread_id = None
        self.message.from_user.id = 123456789
        self.message.text = ""

    @patch('kalich.reply_safe')
    @patch('kalich.get_user_settings')
    def test_cmd_ping_normal(self, mock_settings, mock_reply):
        # Тестируем команду /ping в обычном режиме
        mock_settings.return_value = {'fluffy_mode': False}
        kalich.cmd_ping(self.message)
        
        # Проверяем, что была вызвана функция reply_safe с правильным текстом
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertEqual(args[0], self.message)
        self.assertEqual(args[1], "Система функционирует в штатном режиме.")

    @patch('kalich.reply_safe')
    @patch('kalich.get_user_settings')
    def test_cmd_ping_fluffy(self, mock_settings, mock_reply):
        # Тестируем команду /ping в пушистом режиме
        mock_settings.return_value = {'fluffy_mode': True}
        kalich.cmd_ping(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertEqual(args[0], self.message)
        self.assertEqual(args[1], "Понг! 🦊 Я здесь и работаю без перебоев.")

    @patch('kalich.reply_safe')
    def test_cmd_cancel(self, mock_reply):
        # Тестируем команду /cancel когда нечего отменять
        kalich.cmd_cancel(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertEqual(args[0], self.message)
        self.assertEqual(args[1], "Нечего отменять.")

    @patch('kalich.reply_safe')
    @patch('kalich.get_user_settings')
    def test_cmd_about(self, mock_settings, mock_reply):
        # Тестируем команду /about
        mock_settings.return_value = {'fluffy_mode': False}
        kalich.cmd_about(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertIn("Информационная система расписания.", args[1])
        self.assertIn("Сегодняㅤ/r", args[1])

    @patch('kalich.reply_safe')
    def test_cmd_help(self, mock_reply):
        # Тестируем команду /help
        kalich.cmd_help(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertIn("Справка по командам бота", args[1])
        self.assertIn("/start — Инициализация и приветствие.", args[1])

if __name__ == '__main__':
    unittest.main()
