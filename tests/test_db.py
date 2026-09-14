import kalich
import json

def test_save_schedule_to_db(memory_db):
    # Test saving and retrieving
    lessons = ["Math", "Physics"]
    kalich.save_schedule_to_db(1, 101, 1, "hash123", json.dumps(lessons), "2023-09-01")
    
    # Verify in fast cache (schedules table)
    res = memory_db.execute("SELECT lessons_text FROM schedules WHERE department=1 AND group_id=101 AND day=1").fetchone()
    assert res is not None
    assert json.loads(res[0]) == lessons

    # Verify in history cache
    res = memory_db.execute("SELECT lessons_text FROM schedule_history WHERE department=1 AND group_id=101 AND date='2023-09-01'").fetchone()
    assert res is not None
    assert json.loads(res[0]) == lessons

def test_get_all_schedules_for_day(memory_db):
    lessons = ["Math", "Physics"]
    kalich.save_schedule_to_db(1, 101, 1, "hash123", json.dumps(lessons), "2023-09-01")
    
    schedules = kalich.get_all_schedules_for_day(1)
    assert (1, 101) in schedules
    assert schedules[(1, 101)] == lessons


def test_db_transaction(memory_db):
    import kalich
    with kalich.db_transaction() as conn:
        conn.execute("INSERT OR REPLACE INTO groups_cache (group_name, department, group_id) VALUES (?, ?, ?)", ("ТЕСТ-11", 1, 999))
    
    res = memory_db.execute("SELECT department, group_id FROM groups_cache WHERE group_name='ТЕСТ-11'").fetchone()
    assert res == (1, 999)


def test_monitor_manager_sqlite(memory_db):
    import kalich
    mm = kalich.MonitorManager()
    mm.active_monitors["12345"] = {"chat_id": 12345, "group_id": 42, "department": 2}
    mm.save()

    # Check that SQLite table has the monitor
    row = memory_db.execute("SELECT chat_id, group_id, department FROM active_monitors WHERE id='12345'").fetchone()
    assert row == (12345, 42, 2)

    # Reload into a fresh manager
    mm2 = kalich.MonitorManager()
    assert "12345" in mm2.active_monitors
    assert mm2.active_monitors["12345"]["group_id"] == 42


def test_custom_names_sqlite(memory_db):
    import kalich
    cnm = kalich.CustomNamesManager()
    cnm.set_name(777, "Математика", "Матеша")

    row = memory_db.execute("SELECT custom_name FROM custom_names WHERE chat_id=777").fetchone()
    assert row is not None
    assert row[0] == "Матеша"
    assert cnm.apply(777, "Математика (302)") == "Матеша (302)"

