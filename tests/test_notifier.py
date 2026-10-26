import json
import time
import hashlib
from unittest.mock import MagicMock, patch
import kalich
import src.services.notifier as notifier
from src.database import get_db_connection


def test_db_connection_no_dir(monkeypatch, tmp_path):
    # Test that get_db_connection does not crash with empty dirname
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr('src.config.DB_FILE', db_path)
    monkeypatch.setattr('kalich.DB_FILE', db_path)
    conn = get_db_connection()
    assert conn is not None
    conn.close()


def test_send_updates_for_day_initial_and_diff(memory_db, monkeypatch):
    chat_id = 987654
    dep = 3
    gid = 42
    day = 1

    # Setup active monitor
    kalich.monitor_manager.active_monitors = {
        f"{chat_id}_{dep}_{gid}": {
            "chat_id": chat_id,
            "department": dep,
            "group_id": gid,
            "group_name": "ТЕСТ-11",
            "message_thread_id": None
        }
    }

    mock_send = MagicMock()
    mock_sent_msg = MagicMock()
    mock_sent_msg.message_id = 111
    mock_send.return_value = mock_sent_msg
    monkeypatch.setattr(notifier.bot, 'send_message', mock_send)

    initial_lessons = ["Математика (101)", "Физика (102)"]
    data = {(dep, gid): initial_lessons}

    # 1. First run: initial notification sent and stored
    notifier.send_updates_for_day(day, data)
    assert mock_send.call_count == 1
    call_args = mock_send.call_args[0]
    assert "Математика" in call_args[1]

    # Verify user_notifications record has last_lessons_text
    row = memory_db.execute(
        "SELECT last_msg_hash, last_message_id, last_lessons_text FROM user_notifications WHERE chat_id=? AND group_id=?",
        (chat_id, gid)
    ).fetchone()
    assert row is not None
    assert row[1] == 111
    assert json.loads(row[2]) == initial_lessons

    # 2. Second run without changes: no duplicate send
    mock_send.reset_mock()
    notifier.send_updates_for_day(day, data)
    assert mock_send.call_count == 0

    # 3. Third run with updated lessons (substitution)
    mock_send.reset_mock()
    updated_lessons = ["Математика (101)", "Химия (305)"]
    updated_data = {(dep, gid): updated_lessons}

    notifier.send_updates_for_day(day, updated_data)
    assert mock_send.call_count == 1
    update_text = mock_send.call_args[0][1]
    # Check that diff is calculated and sent
    assert "Изменения" in update_text
    assert "Физика" in update_text and "Химия" in update_text

    # Verify updated record
    row2 = memory_db.execute(
        "SELECT last_msg_hash, last_lessons_text FROM user_notifications WHERE chat_id=? AND group_id=?",
        (chat_id, gid)
    ).fetchone()
    assert json.loads(row2[1]) == updated_lessons


def test_trigger_schedule_update_day_and_night(memory_db, monkeypatch):
    from datetime import datetime

    # 1. Day time: calls send_updates_for_day immediately
    mock_now_day = MagicMock(return_value=datetime(2026, 10, 23, 14, 0))
    monkeypatch.setattr('src.services.notifier.now_msk', mock_now_day)
    mock_send = MagicMock()
    monkeypatch.setattr('src.services.notifier.send_updates_for_day', mock_send)

    notifier.trigger_schedule_update(5, "2026-10-30")
    assert mock_send.call_count == 1
    assert mock_send.call_args[0][0] == 5

    # 2. Night time: stores in _DEBOUNCE_BUFFER for morning
    mock_now_night = MagicMock(return_value=datetime(2026, 10, 23, 23, 30))
    monkeypatch.setattr('src.services.notifier.now_msk', mock_now_night)

    notifier.trigger_schedule_update(5, "2026-10-30")
    assert 5 in notifier._DEBOUNCE_BUFFER
    assert notifier._DEBOUNCE_BUFFER[5]['date_str'] == "2026-10-30"
    assert time.time() - notifier._DEBOUNCE_BUFFER[5]['last_change'] < 5


def test_refresh_gloris_schedule_triggers_update(memory_db, monkeypatch):
    from src.bot.commands.student import refresh_gloris_schedule
    from src.core.container import AppContext, ServiceContainer

    container = ServiceContainer(bot=MagicMock())
    ctx = container.create_context()

    dep, gid, day = 3, 50, 2
    mons = [{"department": dep, "group_id": gid}]

    # Mock fetch_lessons
    monkeypatch.setattr(ctx.parser, 'fetch_lessons', lambda d, g, dp: ["История (202)"])
    mock_trigger = MagicMock()
    monkeypatch.setattr(ctx.notifier, 'trigger_schedule_update', mock_trigger)

    refresh_gloris_schedule(ctx, mons, day)

    # Must save schedule to DB and call trigger_schedule_update
    assert mock_trigger.call_count == 1
    assert mock_trigger.call_args[0][0] == day

    # Calling again with identical content should NOT re-trigger
    mock_trigger.reset_mock()
    refresh_gloris_schedule(ctx, mons, day)
    assert mock_trigger.call_count == 0


def test_cmd_main_change_group(memory_db, monkeypatch):
    from src.bot.commands.student import MainCommand
    from src.core.container import ServiceContainer

    container = ServiceContainer(bot=MagicMock())
    ctx = container.create_context()
    cmd = MainCommand()

    chat_id = 777888
    # 1. /main without arguments, no monitor yet
    msg = MagicMock()
    msg.chat.id = chat_id
    msg.message_thread_id = None
    msg.text = "/main"

    replies = []
    monkeypatch.setattr(ctx, 'reply', lambda m, text, **kw: replies.append(text))
    cmd.execute(msg, ctx)
    assert len(replies) == 1
    assert "ещё не установлена" in replies[0]

    # 2. /main with invalid group
    replies.clear()
    msg.text = "/main НЕИЗВЕСТНАЯ_ГРУППА_999"
    cmd.execute(msg, ctx)
    assert len(replies) == 1
    assert "не найдена" in replies[0]

    # 3. /main with valid group (e.g. default group "ИС 21-25")
    replies.clear()
    msg.text = "/main ИС 21-25"
    cmd.execute(msg, ctx)
    assert len(replies) == 1
    assert "успешно изменена" in replies[0]
    assert "ИС 21-25" in replies[0]

    # Verify monitor was saved
    mons = ctx.db.monitor_manager.get_user_monitors(chat_id)
    assert len(mons) == 1
    assert mons[0]["group_name"] == "ИС 21-25"
    assert mons[0]["group_id"] == 46

    # 4. /main to change group in a specific topic
    replies.clear()
    msg_topic = MagicMock()
    msg_topic.chat.id = chat_id
    msg_topic.message_thread_id = 12345
    msg_topic.text = "/main П 21-25"
    cmd.execute(msg_topic, ctx)
    assert len(replies) == 1
    assert "топике #12345" in replies[0]

    # Verify topic monitor
    topic_mons = [m for m in ctx.db.monitor_manager.active_monitors.values() if m.get("message_thread_id") == 12345]
    assert len(topic_mons) == 1
    assert topic_mons[0]["group_name"] == "П 21-25"
    assert topic_mons[0]["chat_id"] == chat_id

    # 5. /main without arguments shows current group
    replies.clear()
    msg.text = "/main"
    cmd.execute(msg, ctx)
    assert len(replies) == 1
    assert "Текущая группа" in replies[0]
    assert "ИС 21-25" in replies[0]
