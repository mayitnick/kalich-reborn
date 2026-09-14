import kalich

def test_extract_room():
    assert kalich.extract_room("Математика (101)") == "101"
    assert kalich.extract_room("Физика (101а)") == "101а"
    assert kalich.extract_room("Программирование") is None
    assert kalich.extract_room("Физра (Спортзал) (1)") == "Спортзал) (1" # Based on the logic of finding first ( and last )

def test_parse_date_range():
    # Test valid date range
    start, end = kalich.parse_date_range("01.09.2023 - 05.09.2023")
    assert start == "2023-09-01"
    assert end == "2023-09-05"

    # Test single date
    start, end = kalich.parse_date_range("01.09.2023")
    assert start == "2023-09-01"
    assert end == "2023-09-01"

    # Test invalid text
    start, end = kalich.parse_date_range("invalid text")
    assert start is None
    assert end is None

def test_dynamic_group_parser(monkeypatch):
    def mock_get(url, *args, **kwargs):
        class MockResponse:
            status_code = 200
            text = """
            <html>
                <body>
                    <a href="?group_id=101">БУХ-11-26</a>
                    <a href="?group_id=102">ПК-11-26</a>
                    <a href="?group_id=999">ПОНЕДЕЛЬНИК</a>
                </body>
            </html>
            """
        return MockResponse()

    monkeypatch.setattr('kalich.requests_get_no_proxy', mock_get)
    
    kalich.GROUP_NAME_TO_ID = {}
    kalich.update_groups_cache()
    
    assert "БУХ-11-26" in kalich.GROUP_NAME_TO_ID
    assert "ПК-11-26" in kalich.GROUP_NAME_TO_ID
    assert "ПОНЕДЕЛЬНИК" not in kalich.GROUP_NAME_TO_ID
    assert 101 in kalich.GROUP_ID_TO_NAME[3]

def test_find_group_info():
    kalich.GROUP_NAME_TO_ID = {
        "ИС-21-25": [3, 201],
        "ПКД 11-26": [1, 105]
    }
    
    # Exact match
    name, info = kalich.find_group_info("ИС-21-25")
    assert name == "ИС-21-25"
    assert info == [3, 201]
    
    # Normalized match (spaces instead of dashes, lowercase)
    name, info = kalich.find_group_info("ис 21 25")
    assert name == "ИС-21-25"
    assert info == [3, 201]

    # Compact match (no spaces or hyphens)
    name, info = kalich.find_group_info("ис2125")
    assert name == "ИС-21-25"
    assert info == [3, 201]

    # Partial word match
    name, info = kalich.find_group_info("ПКД")
    assert name == "ПКД 11-26"
    assert info == [1, 105]

def test_get_department_groups():
    kalich.GROUP_NAME_TO_ID = {
        "БУХ-11-26": [1, 101],
        "ПК-11-26": [1, 102],
        "ИС-21-25": [3, 201]
    }
    dept1 = kalich.get_department_groups(1)
    assert dept1 == ["БУХ-11-26", "ПК-11-26"]
    dept3 = kalich.get_department_groups(3)
    assert dept3 == ["ИС-21-25"]


def test_fetch_lessons_html_fixtures(monkeypatch):
    """Тестирование парсинга различных вариантов верстки Gloris с тегами <p> (Phase 5.1)."""
    sample_html = """
    <html>
        <body>
            <div class="lessons">
                <p>1. Математика (302)</p>
                <p>2. Физика (104) / Химия (205)</p>
                <p>3. Информатика (201)</p>
                <p>Разработано $cript</p>
            </div>
        </body>
    </html>
    """
    class MockResp:
        status_code = 200
        text = sample_html

    monkeypatch.setattr('kalich.requests_get_no_proxy', lambda *args, **kwargs: MockResp())
    lessons = kalich.fetch_lessons(1, 201, 3)
    assert len(lessons) == 3
    assert "Математика (302)" in lessons[0]
    assert "Физика (104)" in lessons[1]
    assert "Информатика (201)" in lessons[2]
    # Filtered out system string
    assert not any("Разработано" in l for l in lessons)


def test_teacher_schedule_generation(memory_db):
    """Тестирование генератора расписания преподавателей (Phase 5.1)."""
    # Сохраняем информацию о преподавателе с кабинетом 302
    kalich.init_db()
    conn = kalich.get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO teachers (chat_id, department, rooms, name, status) VALUES (?, ?, ?, ?, 'approved')",
        (99999, 3, '["302"]', 'Иванов И.И.')
    )
    conn.commit()
    conn.close()

    all_data = {
        (3, 101): ["Математика (302)", "Физика (101)"],
        (3, 102): ["Информатика (201)", "История (302)"]
    }
    kalich.GROUP_ID_TO_NAME = {3: {101: "Гр-101", 102: "Гр-102"}}

    dept, rooms, schedule = kalich.get_teacher_schedule(99999, 1, all_data)
    assert dept == 3
    assert "302" in rooms
    assert len(schedule) > 1
    # Первая пара в кабинете 302 у Гр-101
    assert any("Гр-101" in item[0] for item in schedule[0])
    # Вторая пара в кабинете 302 у Гр-102
    assert any("Гр-102" in item[0] for item in schedule[1])


