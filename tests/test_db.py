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
