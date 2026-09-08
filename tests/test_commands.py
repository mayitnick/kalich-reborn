import unittest
import tempfile
import os
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
import src.config as config
import src.database as database


class TestKalichCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp_db = tempfile.NamedTemporaryFile(delete=False)
        cls._temp_db.close()
        cls._orig_db = config.DB_FILE
        config.DB_FILE = cls._temp_db.name
        kalich.DB_FILE = cls._temp_db.name
        kalich.init_db()

    @classmethod
    def tearDownClass(cls):
        config.DB_FILE = cls._orig_db
        kalich.DB_FILE = cls._orig_db
        try:
            os.unlink(cls._temp_db.name)
        except Exception:
            pass

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
        self.assertEqual(args[1], kalich.messages.PING_NORMAL)

    @patch('kalich.reply_safe')
    @patch('kalich.get_user_settings')
    def test_cmd_ping_fluffy(self, mock_settings, mock_reply):
        # Тестируем команду /ping в пушистом режиме
        mock_settings.return_value = {'fluffy_mode': True}
        kalich.cmd_ping(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertEqual(args[0], self.message)
        self.assertEqual(args[1], kalich.messages.PING_FLUFFY)

    @patch('kalich.reply_safe')
    def test_cmd_cancel(self, mock_reply):
        # Тестируем команду /cancel когда нечего отменять
        kalich.cmd_cancel(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertEqual(args[0], self.message)
        self.assertEqual(args[1], kalich.messages.CANCEL_NOTHING)

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
    @patch('src.database.is_teacher')
    @patch('kalich.is_teacher')
    def test_cmd_help(self, mock_is_teacher_k, mock_is_teacher_db, mock_reply):
        # Тестируем команду /help
        mock_is_teacher_k.return_value = False
        mock_is_teacher_db.return_value = False
        kalich.cmd_help(self.message)
        
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        self.assertIn("Справка по командам бота", args[1])
        self.assertIn("/start — Инициализация и приветствие.", args[1])

    @patch('kalich.reply_safe')
    @patch('kalich.is_teacher', return_value=False)
    @patch('src.database.is_teacher', return_value=False)
    def test_cmd_now_and_next(self, mock_is_teacher_db, mock_is_teacher_k, mock_reply):
        import datetime
        from src.core.container import ServiceContainer

        # Register monitor and schedule
        kalich.monitor_manager.active_monitors[self.message.chat.id] = {
            'chat_id': self.message.chat.id,
            'department': 1,
            'group_id': 101,
            'group_name': 'ПК-11-26'
        }
        test_lessons = ["Информатика (204)", "Математика (301)", "Физика (201)"]
        import json
        kalich.save_schedule_to_db(1, 101, 1, "test_h", json.dumps(test_lessons), "2026-09-08")

        # 1. Test /now during lesson 1 (e.g. 08:35 on Monday)
        dt_during_lesson = datetime.datetime(2026, 9, 7, 8, 35) # Monday
        with patch('src.bot.commands.student.now_msk', return_value=dt_during_lesson):
            mock_reply.reset_mock()
            kalich.cmd_now(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Сейчас: 1. Информатика (204)", reply_text)
            self.assertIn("Время: 08:20 - 09:05", reply_text)
            self.assertIn("До конца пары: 30м", reply_text)
            self.assertIn("Следующий: 2. Математика (301) (09:05 - 09:50)", reply_text)

        # 2. Test /now during break (e.g. 09:55 on Monday)
        dt_during_break = datetime.datetime(2026, 9, 7, 9, 55)
        with patch('src.bot.commands.student.now_msk', return_value=dt_during_break):
            mock_reply.reset_mock()
            kalich.cmd_now(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Сейчас: Перемена", reply_text)
            self.assertIn("До конца перемены: 5м", reply_text)
            self.assertIn("Следующий: 3. Физика (201) (10:00 - 10:45)", reply_text)

        # 3. Test /now before lessons (e.g. 08:00 on Monday)
        dt_before = datetime.datetime(2026, 9, 7, 8, 0)
        with patch('src.bot.commands.student.now_msk', return_value=dt_before):
            mock_reply.reset_mock()
            kalich.cmd_now(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Занятия еще не начались", reply_text)
            self.assertIn("До начала: 20м", reply_text)
            self.assertIn("Следующий: 1. Информатика (204) (08:20 - 09:05)", reply_text)

        # 4. Test /now after lessons (e.g. 12:00 on Monday)
        dt_after = datetime.datetime(2026, 9, 7, 12, 0)
        with patch('src.bot.commands.student.now_msk', return_value=dt_after):
            mock_reply.reset_mock()
            kalich.cmd_now(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Пар больше нет", reply_text)

        # 5. Test /next during lesson 1 (08:35)
        with patch('src.bot.commands.student.now_msk', return_value=dt_during_lesson):
            mock_reply.reset_mock()
            kalich.cmd_next(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Далее: 2. Математика (301)", reply_text)
            self.assertIn("Время: 09:05 - 09:50", reply_text)
            self.assertIn("Через: 30м", reply_text)

        # 6. Test /next during break (09:55)
        with patch('src.bot.commands.student.now_msk', return_value=dt_during_break):
            mock_reply.reset_mock()
            kalich.cmd_next(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Далее: 3. Физика (201)", reply_text)
            self.assertIn("Время: 10:00 - 10:45", reply_text)
            self.assertIn("Через: 5м", reply_text)

        # 7. Test /next after lessons (12:00)
        with patch('src.bot.commands.student.now_msk', return_value=dt_after):
            mock_reply.reset_mock()
            kalich.cmd_next(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Пар больше нет", reply_text)

        # 8. Test merged block of consecutive identical lessons
        merged_lessons = ["Информатика (204)", "Информатика (204)", "Физика (201)"]
        kalich.save_schedule_to_db(1, 101, 1, "test_h2", json.dumps(merged_lessons), "2026-09-08")
        with patch('src.bot.commands.student.now_msk', return_value=dt_during_lesson):
            mock_reply.reset_mock()
            kalich.cmd_now(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Сейчас: 1-2. Информатика (204)", reply_text)
            self.assertIn("Время: 08:20 - 09:50", reply_text)
            self.assertIn("До конца блока: 1ч 15м", reply_text)
            self.assertIn("Следующий: 3. Физика (201) (10:00 - 10:45)", reply_text)

            # Test /next during merged block
            mock_reply.reset_mock()
            kalich.cmd_next(self.message)
            mock_reply.assert_called_once()
            args, _ = mock_reply.call_args
            reply_text = args[1].replace('\u3164', ' ')
            self.assertIn("Далее: 3. Физика (201)", reply_text)
            self.assertIn("Время: 10:00 - 10:45", reply_text)
            self.assertIn("Через: 1ч 25м", reply_text)

if __name__ == '__main__':
    unittest.main()
