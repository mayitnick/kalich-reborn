import pytest
import sqlite3
import os
import tempfile
from unittest.mock import MagicMock, patch

@pytest.fixture(autouse=True)
def mock_telebot(monkeypatch):
    mock_bot = MagicMock()
    monkeypatch.setattr('kalich.bot', mock_bot)
    return mock_bot

@pytest.fixture
def memory_db(monkeypatch):
    import kalich
    temp_db = tempfile.NamedTemporaryFile(delete=False)
    temp_db.close()
    
    # Patch kalich.DB_FILE for this test
    monkeypatch.setattr('kalich.DB_FILE', temp_db.name)
    kalich.init_db()
    
    conn = sqlite3.connect(temp_db.name)
    yield conn
    conn.close()
    
    try:
        os.unlink(temp_db.name)
    except:
        pass
