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
