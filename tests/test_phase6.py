import json
import kalich
from src.services.notifier import compute_schedule_diff, get_first_lesson_start

def test_compute_schedule_diff():
    old_lessons = ["Математика (302)", "Физика (104)", "Информатика (201)"]
    new_lessons = ["Математика (302)", "Химия (312)", ""]
    diff = compute_schedule_diff(old_lessons, new_lessons)
    assert "- 2 пара: [Было] Физика (104) ➔ [Стало] Химия (312)" in diff
    assert "- 3 пара: [Отменена] Информатика (201)" in diff

def test_smart_alarm_start():
    # Lessons start from pair 2 (CALLS[1] is 09:05)
    lessons = ["", "Информатика (201)", "Физика (104)"]
    idx, time_str = get_first_lesson_start(lessons)
    assert idx == 2
    assert time_str == "09:05"

    # Lessons start from pair 1 (CALLS[0] is 08:20)
    lessons_early = ["Математика (302)", "Информатика (201)"]
    idx_early, time_str_early = get_first_lesson_start(lessons_early)
    assert idx_early == 1
    assert time_str_early == "08:20"

def test_homework_notes(memory_db):
    note_id = kalich.add_homework_note(999, 101, 3, "Математика", "Стр 45 упр 3", "2026-09-20")
    assert note_id > 0

    notes = kalich.get_homework_notes(999)
    assert len(notes) == 1
    assert notes[0]["subject"] == "Математика"
    assert notes[0]["note"] == "Стр 45 упр 3"

    deleted = kalich.delete_homework_note(note_id, 999)
    assert deleted is True
    assert len(kalich.get_homework_notes(999)) == 0
