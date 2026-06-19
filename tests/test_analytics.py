import kalich
import json
import io

def test_generate_group_subject_chart_empty(memory_db):
    # Should return None if no data
    res = kalich.generate_group_subject_chart(999, 1, "Test Group")
    assert res is None

def test_generate_group_subject_chart_with_data(memory_db):
    lessons = ["Math (101)", "Physics (102)", "Math (101)"]
    kalich.save_schedule_to_db(1, 999, 1, "hash", json.dumps(lessons), "2023-09-01")
    
    # Needs GROUP_ID_TO_NAME context if we use it, but the function takes group_name directly
    res = kalich.generate_group_subject_chart(999, 1, "Test Group")
    assert isinstance(res, io.BytesIO)

def test_get_time_distribution_stats_empty(memory_db):
    stats = kalich.get_time_distribution_stats()
    assert stats == [0] * 10
