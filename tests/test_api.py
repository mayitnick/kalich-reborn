import pytest
import time
import requests
import threading
import sqlite3
import json
import asyncio
from aiohttp import web
import kalich
import api_server

def run_server_in_thread(app):
    loop = asyncio.new_event_loop()
    runner = web.AppRunner(app)
    
    port_event = threading.Event()
    allocated_port = []
    
    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, '127.0.0.1', 0)  # Port 0 means auto-allocate
        loop.run_until_complete(site.start())
        port = site._server.sockets[0].getsockname()[1]
        allocated_port.append(port)
        port_event.set()
        loop.run_forever()
        
    t = threading.Thread(target=run, daemon=True)
    t.start()
    
    if not port_event.wait(timeout=5):
        raise RuntimeError("Web server failed to start in thread")
        
    return allocated_port[0], loop, runner

@pytest.fixture
def api_url(memory_db):
    # Setup test cache
    kalich.GROUP_NAME_TO_ID = {
        "Гр-301": [3, 301],
        "Гр-302": [3, 302]
    }
    kalich.build_reverse_group_dict()
    api_server.ensure_dev_teacher()
    
    app = web.Application()
    app.router.add_get('/api/health', api_server.handle_health)
    app.router.add_post('/api/auth', api_server.handle_auth)
    app.router.add_get('/api/groups', api_server.handle_groups)
    app.router.add_get('/api/schedule', api_server.handle_schedule)
    app.router.add_get('/api/teacher/schedule', api_server.handle_teacher_schedule)
    app.router.add_post('/api/override', api_server.handle_override)
    app.router.add_post('/api/sync', api_server.handle_sync)
    app.router.add_post('/api/settings', api_server.handle_settings)
    app.router.add_get('/api/analytics', api_server.handle_analytics)
    app.router.add_get('/api/calendar/{department}/{group_id}.ics', api_server.handle_calendar_feed)
    app.router.add_post('/api/admin/fill', api_server.handle_admin_fill)
    app.router.add_post('/api/admin/flush', api_server.handle_admin_flush)
    app.router.add_get('/', api_server.serve_index)
    app.router.add_get('/index.html', api_server.serve_index)
    app.router.add_get('/styles.css', api_server.serve_styles)
    app.router.add_get('/app.js', api_server.serve_app_js)
    app.router.add_get('/manifest.json', api_server.serve_manifest)
    
    port, loop, runner = run_server_in_thread(app)
    
    yield f"http://127.0.0.1:{port}"
    
    # Cleanup server
    loop.call_soon_threadsafe(loop.stop)
    time.sleep(0.1)
    loop.close()

def test_api_auth(api_url):
    resp = requests.post(f"{api_url}/api/auth", json={'device_id': '1234567'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'user' in data
    assert data['user']['role'] == 'teacher'
    assert data['user']['id'] == 1234567

def test_api_groups(api_url):
    resp = requests.get(f"{api_url}/api/groups")
    assert resp.status_code == 200
    data = resp.json()
    assert "Гр-301" in data['groups']

def test_api_schedule(api_url):
    lessons = ["Math (302)", "Physics (303)"]
    kalich.save_schedule_to_db(3, 301, 1, "hash123", json.dumps(lessons), "2026-06-22")
    
    resp = requests.get(f"{api_url}/api/schedule?department=3&group_id=301&day=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data == lessons

def test_api_override_and_teacher_schedule(api_url):
    lessons = ["Math (302)", "Physics (303)"]
    kalich.save_schedule_to_db(3, 301, 1, "hash123", json.dumps(lessons), "2026-06-22")
    
    payload = {
        'initData': '',
        'department': 3,
        'day': 1,
        'slot_idx': 0,
        'group_id': 301,
        'new_room': '302',
        'new_subject': 'Chemistry'
    }
    resp = requests.post(f"{api_url}/api/override", json=payload)
    assert resp.status_code == 200
    
    # Schedule should change
    resp = requests.get(f"{api_url}/api/schedule?department=3&group_id=301&day=1")
    data = resp.json()
    assert data[0] == "Chemistry (302)"
    
    # Teacher schedule should reflect
    resp = requests.get(f"{api_url}/api/teacher/schedule?chat_id=1234567&day=1")
    teacher_schedule = resp.json()
    assert len(teacher_schedule) > 0
    assert teacher_schedule[0][0][1] == "Chemistry"

def test_api_sync(api_url):
    payload = {
        'initData': '',
        'overrides': [
            {
                'department': 3,
                'day': 2,
                'slot_idx': 1,
                'group_id': 302,
                'new_room': '305',
                'new_subject': 'Bio'
            }
        ]
    }
    resp = requests.post(f"{api_url}/api/sync", json=payload)
    assert resp.status_code == 200
    assert resp.json()['status'] == 'success'
    
    # Verify in DB
    conn = sqlite3.connect(kalich.DB_FILE)
    row = conn.execute("SELECT new_room FROM teacher_room_overrides WHERE group_id=302 AND day=2").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == '305'

def test_api_settings(api_url):
    payload = {
        'initData': '',
        'settings': {
            'notifications': 0,
            'voice_alerts': 1,
            'voice_effect': 'robot',
            'fluffy_mode': 1
        }
    }
    resp = requests.post(f"{api_url}/api/settings", json=payload)
    assert resp.status_code == 200
    
    settings = kalich.get_user_settings(1234567)
    assert settings['notifications'] == 0
    assert settings['voice_alerts'] == 1
    assert settings['voice_effect'] == 'robot'
    assert settings['fluffy_mode'] == 1

def test_api_analytics(api_url):
    lessons = ["Math (301)", "Physics (302)"]
    kalich.save_schedule_to_db(3, 301, 1, "hash123", json.dumps(lessons), "2026-06-22")
    
    resp = requests.get(f"{api_url}/api/analytics?type=group&target=3-301")
    assert resp.status_code == 200
    data = resp.json()
    assert 'subjects' in data
    assert 'daily' in data
    assert data['subjects']['Math'] == 1
    
    # Check cabinet analytics
    resp = requests.get(f"{api_url}/api/analytics?type=teacher&target=301")
    assert resp.status_code == 200
    data_room = resp.json()
    assert 'groups' in data_room
    # It should map "Гр-301 (Отд. 3)" since kalich.GROUP_NAME_TO_ID has "Гр-301": [3, 301]
    assert "Гр-301 (Отд. 3)" in data_room['groups']
    assert data['subjects']['Math'] == 1

def test_api_schedule_by_date(api_url):
    lessons = ["Chemistry (302)"]
    # 2026-06-22 is a Monday (weekday 1)
    kalich.save_schedule_to_db(3, 301, 1, "hash123", json.dumps(lessons), "2026-06-22")
    resp = requests.get(f"{api_url}/api/schedule?department=3&group_id=301&date=2026-06-22")
    assert resp.status_code == 200
    assert resp.json() == lessons

def test_api_override_by_date(api_url):
    lessons = ["Math (302)", "Physics (303)"]
    kalich.save_schedule_to_db(3, 301, 1, "hash123", json.dumps(lessons), "2026-06-22")
    
    # 1. Override for specific date 2026-06-22 (Monday)
    payload = {
        'initData': '',
        'department': 3,
        'day': 1,
        'slot_idx': 0,
        'group_id': 301,
        'new_room': '302',
        'new_subject': 'Chemistry',
        'date': '2026-06-22'
    }
    resp = requests.post(f"{api_url}/api/override", json=payload)
    assert resp.status_code == 200
    
    # 2. Get schedule for 2026-06-22 (should be overridden)
    resp = requests.get(f"{api_url}/api/schedule?department=3&group_id=301&date=2026-06-22")
    assert resp.json()[0] == "Chemistry (302)"
    
    # 3. Get schedule for another Monday (e.g. 2026-06-29) - should NOT be overridden
    kalich.save_schedule_to_db(3, 301, 1, "hash123", json.dumps(lessons), "2026-06-29")
    resp = requests.get(f"{api_url}/api/schedule?department=3&group_id=301&date=2026-06-29")
    assert resp.json()[0] == "Math (302)"

def test_api_admin_fill_and_flush_range(api_url):
    # Test range-based caching
    payload_fill = {
        'initData': '',
        'start_date': '2026-06-22',
        'end_date': '2026-06-23'
    }
    kalich.GROUP_NAME_TO_ID = {"Гр-301": [3, 301]}
    
    resp = requests.post(f"{api_url}/api/admin/fill", json=payload_fill)
    assert resp.status_code == 200
    
    time.sleep(0.5)
    
    payload_flush = {
        'initData': '',
        'start_date': '2026-06-22',
        'end_date': '2026-06-23'
    }
    resp = requests.post(f"{api_url}/api/admin/flush", json=payload_flush)
    assert resp.status_code == 200

def test_api_admin_fill_and_flush_by_department(api_url):
    # Test range-based caching with department parameter
    payload_fill = {
        'initData': '',
        'start_date': '2026-06-22',
        'end_date': '2026-06-22',
        'department': 3
    }
    kalich.GROUP_NAME_TO_ID = {
        "Group-Dept3": [3, 301],
        "Group-Dept1": [1, 101]
    }
    
    resp = requests.post(f"{api_url}/api/admin/fill", json=payload_fill)
    assert resp.status_code == 200
    
    time.sleep(0.5)
    
    payload_flush = {
        'initData': '',
        'start_date': '2026-06-22',
        'end_date': '2026-06-22',
        'department': 3
    }
    resp = requests.post(f"{api_url}/api/admin/flush", json=payload_flush)
    assert resp.status_code == 200

def test_api_health(api_url):
    resp = requests.get(f"{api_url}/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["groups_count"] >= 2


def test_api_validation_and_auth_checks(api_url):
    """Тестирование валидации входных данных и авторизации API (Phase 3.1 & 5.1)."""
    # 1. Неверный департамент
    invalid_dept_payload = {
        'department': 99,
        'day': 1,
        'slot_idx': 0,
        'group_id': 301,
        'new_room': '101'
    }
    resp = requests.post(f"{api_url}/api/override", json=invalid_dept_payload)
    assert resp.status_code == 400
    assert "Validation error" in resp.json()["error"]

    # 2. Неверный день
    invalid_day_payload = {
        'department': 3,
        'day': 15,
        'slot_idx': 0,
        'group_id': 301,
        'new_room': '101'
    }
    resp = requests.post(f"{api_url}/api/override", json=invalid_day_payload)
    assert resp.status_code == 400

    # 3. Неверный слот пары
    invalid_slot_payload = {
        'department': 3,
        'day': 1,
        'slot_idx': 99,
        'group_id': 301,
        'new_room': '101'
    }
    resp = requests.post(f"{api_url}/api/override", json=invalid_slot_payload)
    assert resp.status_code == 400


def test_api_calendar_ics(api_url):
    """Тестирование живого фида расписания iCal / .ics (Phase 6.3)."""
    lessons = ["Математика (302)", "Информатика (201)"]
    kalich.save_schedule_to_db(3, 301, 1, "hash_cal", json.dumps(lessons), "2026-06-22")

    resp = requests.get(f"{api_url}/api/calendar/3/301.ics")
    assert resp.status_code == 200
    assert "BEGIN:VCALENDAR" in resp.text
    assert "BEGIN:VEVENT" in resp.text
    assert "SUMMARY:Математика" in resp.text
    assert "LOCATION:Кабинет 302" in resp.text
    assert "END:VCALENDAR" in resp.text


def test_api_serves_webapp_tma(api_url):
    """Тестирование отдачи статических файлов Telegram Mini App."""
    resp_index = requests.get(f"{api_url}/")
    assert resp_index.status_code == 200
    assert "telegram-web-app.js" in resp_index.text

    resp_styles = requests.get(f"{api_url}/styles.css")
    assert resp_styles.status_code == 200
    assert "--tg-theme-bg-color" in resp_styles.text

    resp_app = requests.get(f"{api_url}/app.js")
    assert resp_app.status_code == 200
    assert "Telegram" in resp_app.text
    assert "PAIR_TIMES" in resp_app.text



