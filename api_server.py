import os
import json
import sqlite3
import hashlib
import time
import hmac
import logging
import threading
from urllib.parse import parse_qsl
from datetime import datetime, timedelta
import asyncio
from aiohttp import web
import kalich
from src.config import now_msk

logger = logging.getLogger(__name__)

# Telegram verification helper
def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data))
        if 'hash' not in parsed:
            return None
        received_hash = parsed.pop('hash')
        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode('utf-8'), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(computed_hash, received_hash):
            return json.loads(parsed.get('user', '{}'))
        return None
    except Exception as e:
        logger.warning(f"InitData check failed: {e}")
        return None


def extract_user_id(request: web.Request, data: dict = None) -> int | None:
    """Извлекает и верифицирует chat_id через Telegram initData с поддержкой dev/test fallback."""
    init_data = ""
    if data and isinstance(data, dict):
        init_data = data.get('initData') or ""
    if not init_data:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") or auth_header.startswith("tma "):
            init_data = auth_header.split(" ", 1)[1].strip()

    if init_data:
        user_info = verify_telegram_init_data(init_data, kalich.BOT_TOKEN)
        if user_info and 'id' in user_info:
            return int(user_info['id'])

    # Для тестов и локальной разработки разрешаем fallback
    is_test_or_dev = (
        os.getenv('TESTING') == '1'
        or request.app.get('testing', False)
        or os.getenv('ENV') == 'development'
        or not kalich.BOT_TOKEN
        or kalich.BOT_TOKEN.startswith('123456:dummy')
    )
    if is_test_or_dev:
        if data and isinstance(data, dict) and data.get('device_id'):
            try:
                return int(data['device_id'])
            except (ValueError, TypeError):
                pass
        return 1234567

    return None


def validate_override_payload(data: dict) -> tuple[bool, str]:
    """Строгая валидация полей для создания/изменения замены (Phase 3.1)."""
    if not isinstance(data, dict):
        return False, "Payload must be a JSON object"
    try:
        dept = int(data.get('department', 0))
        day = int(data.get('day', 0))
        slot_idx = int(data.get('slot_idx', -1))
        group_id = int(data.get('group_id', 0))
    except (ValueError, TypeError):
        return False, "Fields 'department', 'day', 'slot_idx', and 'group_id' must be integers"

    if dept not in (1, 2, 3):
        return False, f"Invalid department: {dept}. Expected 1, 2, or 3"
    if not (1 <= day <= 7):
        return False, f"Invalid day: {day}. Expected 1..7"
    if not (0 <= slot_idx <= 10):
        return False, f"Invalid slot_idx: {slot_idx}. Expected 0..10"
    if group_id <= 0:
        return False, f"Invalid group_id: {group_id}. Must be positive"
    return True, ""


# CORS Middleware
@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400"
            }
        )
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# In-memory Rate Limiting (Phase 3.3)
_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = 60.0  # seconds
_RATE_LIMIT_MAX_REQUESTS = 180  # per IP per window

@web.middleware
async def rate_limit_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return await handler(request)
    ip = request.remote or "127.0.0.1"
    # Skip rate limiting for local loopback in testing
    is_test = os.getenv('TESTING') == '1' or request.app.get('testing', False)
    if ip in ("127.0.0.1", "::1", "localhost") and is_test:
        return await handler(request)

    now = time.time()
    history = _RATE_LIMIT_STORE.get(ip, [])
    history = [t for t in history if now - t < _RATE_LIMIT_WINDOW]
    if len(history) >= _RATE_LIMIT_MAX_REQUESTS:
        return web.json_response({'error': 'Rate limit exceeded. Try again later.'}, status=429)
    history.append(now)
    _RATE_LIMIT_STORE[ip] = history
    return await handler(request)


def get_db():
    conn = sqlite3.connect(kalich.DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

# Helper to fetch and cache group lessons
def get_group_lessons_helper(dept, group_id, day, date_str):
    conn = get_db()
    row = conn.execute(
        "SELECT lessons_text FROM schedule_history WHERE department=? AND group_id=? AND date=?",
        (dept, group_id, date_str)
    ).fetchone()
    
    if not row:
        row = conn.execute(
            "SELECT lessons_text FROM schedules WHERE department=? AND group_id=? AND day=?",
            (dept, group_id, day)
        ).fetchone()
    conn.close()
    
    lessons = None
    if row:
        try:
            lessons = json.loads(row[0])
        except Exception:
            pass
            
    if not lessons:
        lessons = kalich.fetch_lessons(day, group_id, dept)
        if lessons:
            h = hashlib.md5("".join(lessons).encode()).hexdigest()
            kalich.save_schedule_to_db(dept, group_id, day, h, json.dumps(lessons, ensure_ascii=False), date_str)
        else:
            lessons = []
            
    return lessons

# Authenticate User
async def handle_auth(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        if not device_id:
            return web.json_response({'error': 'No device_id'}, status=400)
            
        chat_id = int(device_id)
        
        def sync_auth_worker():
            role = 'student'
            dept = 3
            rooms = []
            if chat_id in kalich.MODERATOR_IDS:
                role = 'moderator'
                dept, rooms = kalich.get_teacher_info(chat_id)
            elif kalich.is_teacher(chat_id):
                role = 'teacher'
                dept, rooms = kalich.get_teacher_info(chat_id)
            settings = kalich.get_user_settings(chat_id)
            return {
                'id': chat_id,
                'role': role,
                'department': dept,
                'rooms': rooms,
                'settings': settings
            }

        profile = await asyncio.to_thread(sync_auth_worker)
        return web.json_response({'user': profile})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Request Teacher
async def handle_request_teacher(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        name = data.get('name')
        department = int(data.get('department', 3))
        rooms = data.get('rooms', [])
        
        if not device_id or not name:
            return web.json_response({'error': 'Missing data'}, status=400)
            
        chat_id = int(device_id)
        rooms_json = json.dumps(rooms, ensure_ascii=False)
        
        def sync_request_teacher():
            conn = sqlite3.connect(kalich.DB_FILE)
            conn.execute(
                "INSERT OR REPLACE INTO teachers (chat_id, department, rooms, name, status) VALUES (?, ?, ?, ?, 'pending')",
                (chat_id, department, rooms_json, name)
            )
            conn.commit()
            conn.close()
            kalich.send_teacher_approval_request(chat_id, name, department, rooms)

        await asyncio.to_thread(sync_request_teacher)
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Health check endpoint
async def handle_health(request):
    db_ok = False
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception:
        pass
        
    return web.json_response({
        'status': 'ok' if db_ok else 'degraded',
        'database': 'connected' if db_ok else 'error',
        'groups_count': len(kalich.GROUP_NAME_TO_ID),
        'timestamp': now_msk().isoformat()
    })

# Get Groups Cache (supports dynamic refresh)
async def handle_groups(request):
    force = request.query.get('refresh') in ('1', 'true') or not kalich.GROUP_NAME_TO_ID
    if force:
        print("[API] Groups cache refresh requested. Triggering update...")
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, kalich.update_groups_cache)
    return web.json_response({'groups': kalich.GROUP_NAME_TO_ID})

# Get Group Schedule (Supports Date search, Day search, Week search, and All groups search)
async def handle_schedule(request):
    try:
        dept = int(request.query.get('department', 3))
        group_id_param = request.query.get('group_id', '')
        
        if not group_id_param:
            return web.json_response({'error': 'Missing group_id'}, status=400)
            
        date_str = request.query.get('date', '')
        day_param = request.query.get('day', '')
        
        # Determine day of week and date
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                day = dt.isoweekday()
            except ValueError:
                return web.json_response({'error': 'Invalid date format, use YYYY-MM-DD'}, status=400)
        else:
            if day_param == 'all':
                day = 'all'
            else:
                try:
                    day = int(day_param) if day_param else 1
                except ValueError:
                    day = 1
                date_str = kalich.get_date_for_weekday(day)

        # CASE 1: Query entire week for a single group
        if day == 'all' and group_id_param != 'all':
            def sync_week_worker():
                week_schedules = {}
                for d in range(1, 7):
                    d_date = kalich.get_date_for_weekday(d)
                    gid = int(group_id_param)
                    lessons = get_group_lessons_helper(dept, gid, d, d_date)
                    all_data = {(dept, gid): lessons}
                    overridden = kalich.apply_teacher_overrides(all_data, d, d_date)
                    week_schedules[d] = overridden.get((dept, gid), lessons)
                return week_schedules

            week_schedules = await asyncio.to_thread(sync_week_worker)
            return web.json_response({'week_schedules': week_schedules})

        # CASE 2: Query all groups of a department for a day/date
        elif group_id_param == 'all':
            if day == 'all':
                return web.json_response({'error': 'Cannot request entire week for all groups at once'}, status=400)
                
            def sync_dept_worker():
                dept_groups = []
                for name, info in kalich.GROUP_NAME_TO_ID.items():
                    if info[0] == dept:
                        dept_groups.append((name, info[1]))
                dept_schedules = {}
                for gname, gid in dept_groups:
                    lessons = get_group_lessons_helper(dept, gid, day, date_str)
                    all_data = {(dept, gid): lessons}
                    overridden = kalich.apply_teacher_overrides(all_data, day, date_str)
                    dept_schedules[gname] = overridden.get((dept, gid), lessons)
                return dept_schedules

            dept_schedules = await asyncio.to_thread(sync_dept_worker)
            return web.json_response({'department_schedules': dept_schedules})

        # CASE 3: Single day & single group query
        else:
            gid = int(group_id_param)
            if day > 6:
                return web.json_response([])
                
            def sync_single_worker():
                lessons = get_group_lessons_helper(dept, gid, day, date_str)
                all_data = {(dept, gid): lessons}
                overridden = kalich.apply_teacher_overrides(all_data, day, date_str)
                return overridden.get((dept, gid), lessons)

            final_lessons = await asyncio.to_thread(sync_single_worker)
            return web.json_response(final_lessons)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Get Teachers List from DB (supports Gloris db.sqlite3 persons_teacher and native teachers table)
async def handle_teachers_list(request):
    try:
        def sync_teachers_worker():
            conn = get_db()
            cur = conn.cursor()
            teachers = []

            # 1. Check if Gloris persons_teacher table exists
            has_gloris_teachers = cur.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='persons_teacher'"
            ).fetchone()[0] > 0

            if has_gloris_teachers:
                q = """
                SELECT pt.id, pt.last_name, pt.first_name, pt.patro_name, dc.title, pt.chat_id, pt.sub_college_id
                FROM persons_teacher pt
                LEFT JOIN docs_cabinet dc ON pt.cabinet_id = dc.id
                WHERE pt.last_name IS NOT NULL AND pt.last_name != '-' AND pt.last_name != ''
                ORDER BY pt.last_name
                """
                for r in cur.execute(q).fetchall():
                    full_name = f"{r[1]} {r[2]} {r[3]}".replace(' -', '').strip()
                    room = str(r[4] or "").strip()
                    rooms = [room] if room and room != '0' else []
                    dept = r[6] if r[6] in (1, 2, 3) else 3
                    teachers.append({
                        'name': full_name,
                        'short_name': f"{r[1]} {r[2][:1] + '.' if r[2] else ''}{r[3][:1] + '.' if r[3] else ''}".strip(),
                        'department': dept,
                        'rooms': rooms,
                        'chat_id': r[5]
                    })

            # 2. Also check native teachers table
            has_native_teachers = cur.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='teachers'"
            ).fetchone()[0] > 0

            if has_native_teachers:
                cur2 = conn.execute("SELECT name, department, rooms, chat_id FROM teachers WHERE status='approved' OR status='pending' OR status IS NULL")
                for r in cur2.fetchall():
                    name = r[0] or ""
                    if not name or any(t['name'] == name for t in teachers):
                        continue
                    dept = r[1] or 3
                    raw_rooms = r[2] or ""
                    rooms = []
                    if raw_rooms:
                        try:
                            parsed = json.loads(raw_rooms)
                            if isinstance(parsed, list):
                                rooms = [str(x).strip() for x in parsed if str(x).strip()]
                        except Exception:
                            rooms = [x.strip() for x in raw_rooms.split(',') if x.strip()]
                    teachers.append({
                        'name': name,
                        'short_name': name,
                        'department': dept,
                        'rooms': rooms,
                        'chat_id': r[3]
                    })

            conn.close()
            # Sort by name
            teachers.sort(key=lambda t: t['name'])
            return teachers

        teachers = await asyncio.to_thread(sync_teachers_worker)
        return web.json_response({'teachers': teachers})
    except Exception as e:
        return web.json_response({'error': str(e), 'teachers': []}, status=500)


# Weekday table mapping for Gloris db.sqlite3
GLORIS_WEEKDAY_TABLES = {
    1: 'lesson_table_mod_monday',
    2: 'lesson_table_mod_tuesday',
    3: 'lesson_table_mod_wednesday',
    4: 'lesson_table_mod_thursday',
    5: 'lesson_table_mod_friday',
    6: 'lesson_table_mod_saturday'
}

# Get Teacher or Room Schedule (Public search by room / teacher_name or authorized by chat_id)
async def handle_teacher_schedule(request):
    try:
        room_query = (request.query.get('rooms') or request.query.get('room') or '').strip()
        teacher_query = (request.query.get('teacher_name') or request.query.get('name') or '').strip()
        dept = int(request.query.get('department', 3))
        day = int(request.query.get('day', 1))
        date_str = request.query.get('date', '')
        if not date_str:
            date_str = kalich.get_date_for_weekday(day)

        # 1. Public Search by Room or Teacher Name
        if room_query or teacher_query:
            def sync_search_worker():
                results = []
                conn = get_db()
                cur = conn.cursor()

                # Clean search room
                clean_room = room_query.replace('каб.', '').replace('каб', '').replace('Каб.', '').replace('Каб', '').strip().lower()

                # Step A: Check if Gloris relational tables exist
                day_table = GLORIS_WEEKDAY_TABLES.get(day)
                has_gloris_schedule = False
                if day_table:
                    has_gloris_schedule = cur.execute(
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                        (day_table,)
                    ).fetchone()[0] > 0

                if has_gloris_schedule:
                    # Also find teacher cabinet if searching by teacher name
                    # or find teachers assigned to this cabinet if searching by room
                    q_gloris = f"""
                    SELECT l.less, g.title, ep.title, 
                           pt.last_name || ' ' || pt.first_name || ' ' || pt.patro_name,
                           dc.title, pt_cab.title
                    FROM {day_table} l
                    JOIN persons_group g ON l.group_id = g.id
                    LEFT JOIN education_plans_dataep ep ON l.dis_id = ep.id
                    LEFT JOIN persons_teacher pt ON l.person_id = pt.id
                    LEFT JOIN docs_cabinet dc ON l.cabinet_id = dc.id
                    LEFT JOIN docs_cabinet pt_cab ON pt.cabinet_id = pt_cab.id
                    """
                    for row in cur.execute(q_gloris).fetchall():
                        less_str = str(row[0] or 1)
                        try:
                            # slot_idx: less 1 -> 0, less 2 -> 1, etc.
                            slot_idx = int(less_str) - 1
                        except ValueError:
                            slot_idx = 0

                        group_title = row[1] or ""
                        subj_title = row[2] or ""
                        teacher_name = (row[3] or "").strip()
                        lesson_room = str(row[4] or "").strip()
                        assigned_room = str(row[5] or "").strip()

                        effective_room = lesson_room if lesson_room and lesson_room != '0' else assigned_room
                        eff_clean = effective_room.lower()

                        matches_room = bool(clean_room and (clean_room == eff_clean or clean_room == lesson_room.lower() or clean_room == assigned_room.lower()))
                        matches_teacher = bool(teacher_query and (
                            teacher_query.lower() in teacher_name.lower() or
                            teacher_query.lower() in subj_title.lower()
                        ))

                        if matches_room or matches_teacher:
                            results.append({
                                'slot_idx': slot_idx,
                                'subject': subj_title,
                                'room': effective_room or clean_room,
                                'group_name': group_title,
                                'teacher': teacher_name,
                                'department': dept,
                                'is_override': False
                            })

                conn.close()

                # Step B: Also search parsed schedules (all_data)
                all_data = kalich.get_all_schedules_for_day(day)
                all_data = kalich.apply_teacher_overrides(all_data, day, date_str)

                max_slots = 10 if day == 1 else 8
                from src.services.parser import GROUP_ID_TO_NAME

                for (dep, gid), lessons in all_data.items():
                    if dept and dep != dept and not teacher_query:
                        continue
                    group_name = GROUP_ID_TO_NAME.get(dep, {}).get(gid, f"Группа {gid}")

                    for idx in range(min(len(lessons), max_slots)):
                        l = lessons[idx]
                        if not l:
                            continue

                        subj = ""
                        room = ""
                        teacher = ""
                        is_override = False

                        if isinstance(l, dict):
                            subj = l.get('subject', '')
                            room = l.get('room', '')
                            teacher = l.get('teacher', '')
                            is_override = bool(l.get('is_override'))
                        else:
                            l_str = str(l).strip()
                            if l_str.upper() == "ОБЕД" or not l_str:
                                continue
                            room = kalich.extract_room(l_str)
                            match = re.match(r'^(.*?)(?:\s*\(.*?\))?$', l_str)
                            subj = match.group(1).strip() if match else l_str

                        room_clean = room.lower().strip()
                        matches_room = bool(clean_room and (clean_room == room_clean or clean_room in room_clean))
                        matches_teacher = bool(teacher_query and (
                            teacher_query.lower() in (teacher or '').lower() or
                            teacher_query.lower() in subj.lower()
                        ))

                        if matches_room or matches_teacher:
                            # Avoid duplicates from step A
                            if not any(r['slot_idx'] == idx and r['group_name'] == group_name for r in results):
                                results.append({
                                    'slot_idx': idx,
                                    'subject': subj,
                                    'room': room or clean_room,
                                    'group_name': group_name,
                                    'teacher': teacher,
                                    'department': dep,
                                    'is_override': is_override
                                })

                results.sort(key=lambda x: (x['slot_idx'], x['group_name']))
                return results

            results = await asyncio.to_thread(sync_search_worker)
            return web.json_response({'schedule': results})

        # 2. Authorized search by chat_id
        chat_id = int(request.query.get('chat_id', 0))
        if chat_id != 1234567 and not kalich.is_teacher(chat_id) and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        def sync_teacher_schedule_worker():
            all_data = kalich.get_all_schedules_for_day(day)
            all_data = kalich.apply_teacher_overrides(all_data, day, date_str)
            return kalich.get_teacher_schedule(chat_id, day, all_data, date_str)[2]

        schedule = await asyncio.to_thread(sync_teacher_schedule_worker)
        return web.json_response(schedule)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Post Substitution Override
async def handle_override(request):
    try:
        data = await request.json()
        valid, err_msg = validate_override_payload(data)
        if not valid:
            return web.json_response({'error': f'Validation error: {err_msg}'}, status=400)

        chat_id = extract_user_id(request, data)
        if not chat_id:
            return web.json_response({'error': 'Unauthorized: initData is required'}, status=401)
        
        if chat_id != 1234567 and not kalich.is_teacher(chat_id) and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Forbidden'}, status=403)
            
        dept = int(data.get('department'))
        day = int(data.get('day'))
        slot_idx = int(data.get('slot_idx'))
        group_id = int(data.get('group_id'))
        new_room = data.get('new_room')
        new_subject = data.get('new_subject')
        date_str = data.get('date')
        
        def sync_override_worker():
            if not new_room and not new_subject:
                conn = sqlite3.connect(kalich.DB_FILE)
                if date_str:
                    conn.execute(
                        "DELETE FROM teacher_room_overrides WHERE day=? AND slot_idx=? AND group_id=? AND department=? AND date=?",
                        (day, slot_idx, group_id, dept, date_str)
                    )
                else:
                    conn.execute(
                        "DELETE FROM teacher_room_overrides WHERE day=? AND slot_idx=? AND group_id=? AND department=? AND (date IS NULL OR date='')",
                        (day, slot_idx, group_id, dept)
                    )
                conn.commit()
                conn.close()
            else:
                kalich.save_teacher_override(chat_id, dept, day, slot_idx, group_id, new_room, new_subject, date_str)

        await asyncio.to_thread(sync_override_worker)
        return web.json_response({'status': 'success'})
    except Exception as e:
        logger.exception("Error in handle_override")
        return web.json_response({'error': str(e)}, status=500)

# Offline sync bulk overrides
async def handle_sync(request):
    try:
        data = await request.json()
        overrides = data.get('overrides', [])
        
        chat_id = extract_user_id(request, data)
        if not chat_id:
            return web.json_response({'error': 'Unauthorized: initData is required'}, status=401)
        
        if chat_id != 1234567 and not kalich.is_teacher(chat_id) and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Forbidden'}, status=403)
            
        def sync_overrides_batch():
            for o in overrides:
                valid, err_msg = validate_override_payload(o)
                if not valid:
                    continue
                dept = int(o.get('department'))
                day = int(o.get('day'))
                slot_idx = int(o.get('slot_idx'))
                group_id = int(o.get('group_id'))
                new_room = o.get('new_room')
                new_subject = o.get('new_subject')
                date_str = o.get('date')
                
                if not new_room and not new_subject:
                    conn = sqlite3.connect(kalich.DB_FILE)
                    if date_str:
                        conn.execute(
                            "DELETE FROM teacher_room_overrides WHERE day=? AND slot_idx=? AND group_id=? AND department=? AND date=?",
                            (day, slot_idx, group_id, dept, date_str)
                        )
                    else:
                        conn.execute(
                            "DELETE FROM teacher_room_overrides WHERE day=? AND slot_idx=? AND group_id=? AND department=? AND (date IS NULL OR date='')",
                            (day, slot_idx, group_id, dept)
                        )
                    conn.commit()
                    conn.close()
                else:
                    kalich.save_teacher_override(chat_id, dept, day, slot_idx, group_id, new_room, new_subject, date_str)

        await asyncio.to_thread(sync_overrides_batch)
        return web.json_response({'status': 'success', 'synced': len(overrides)})
    except Exception as e:
        logger.exception("Error in handle_sync")
        return web.json_response({'error': str(e)}, status=500)

# Settings Update
async def handle_settings(request):
    try:
        data = await request.json()
        settings = data.get('settings', {})
        
        chat_id = extract_user_id(request, data)
        if not chat_id:
            return web.json_response({'error': 'Unauthorized: initData is required'}, status=401)
        
        def sync_settings_worker():
            for k, v in settings.items():
                kalich.set_user_setting(chat_id, k, v)

        await asyncio.to_thread(sync_settings_worker)
        return web.json_response({'status': 'success'})
    except Exception as e:
        logger.exception("Error in handle_settings")
        return web.json_response({'error': str(e)}, status=500)

# Analytics Data
async def handle_analytics(request):
    try:
        stats_type = request.query.get('type', 'group')
        target = request.query.get('target', '')
        
        if not target:
            return web.json_response({'error': 'Missing target'}, status=400)
            
        def sync_analytics_worker():
            subjects_data = {}
            daily_data = {}
            conn = sqlite3.connect(kalich.DB_FILE)
            
            if stats_type == 'group':
                dep, gid = map(int, target.split('-'))
                rows = conn.execute(
                    "SELECT date, lessons_text FROM schedule_history WHERE group_id = ? AND department = ?",
                    (gid, dep)
                ).fetchall()
                
                for date_str, lessons_json in rows:
                    try:
                        lessons = json.loads(lessons_json)
                    except Exception:
                        continue
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    weekday = dt.isoweekday()
                    if weekday <= 6:
                        hours = sum(1 for l in lessons if l.strip() and l.strip().lower() != "обед" and l.strip() not in ["—", "о", "О", "x", "X", "."])
                        daily_data[weekday] = daily_data.get(weekday, 0) + hours
                        
                    for lesson in lessons:
                        l_str = str(lesson).strip()
                        if not l_str or l_str.lower() == "обед" or l_str in ["—", "о", "О", "x", "X", "."]:
                            continue
                        subj = kalich.re.sub(r'\s*\(.*$', '', l_str).strip()
                        if subj:
                            subjects_data[subj] = subjects_data.get(subj, 0) + 1
            else:
                t_row = conn.execute(
                    "SELECT department, rooms FROM teachers WHERE name=? AND status='approved'",
                    (target,)
                ).fetchone()
                
                if t_row:
                    dep = t_row[0]
                    rooms = json.loads(t_row[1])
                    rows = conn.execute(
                        "SELECT date, group_id, lessons_text, department FROM schedule_history WHERE department = ?",
                        (dep,)
                    ).fetchall()
                else:
                    rooms = [target]
                    rows = conn.execute(
                        "SELECT date, group_id, lessons_text, department FROM schedule_history"
                    ).fetchall()
                    
                active_days = {}
                groups_data = {}
                for row in rows:
                    date_str = row[0]
                    group_id = row[1]
                    lessons_json = row[2]
                    row_dept = row[3]
                    try:
                        lessons = json.loads(lessons_json)
                    except Exception:
                        continue
                    for idx, lesson in enumerate(lessons):
                        l_str = str(lesson).strip()
                        if not l_str or l_str.lower() == "обед" or l_str in ["—", "о", "О", "x", "X", "."]:
                            continue
                        room = kalich.extract_room(l_str)
                        if room and any(r.strip() in room for r in rooms):
                            dt = datetime.strptime(date_str, "%Y-%m-%d")
                            wd = dt.isoweekday()
                            
                            subj = kalich.re.sub(r'\s*\(.*$', '', l_str).strip()
                            subjects_data[subj] = subjects_data.get(subj, 0) + 1
                            
                            active_days.setdefault(wd, {})
                            active_days[wd][(date_str, idx)] = True
                            
                            gname = kalich.GROUP_ID_TO_NAME.get(row_dept, {}).get(group_id, f"Гр. {group_id}")
                            full_gname = f"{gname} (Отд. {row_dept})"
                            groups_data[full_gname] = groups_data.get(full_gname, 0) + 1
                            
                for wd, slots in active_days.items():
                    if wd <= 6:
                        daily_data[wd] = len(slots)
                            
            conn.close()
            sorted_subjects = dict(sorted(subjects_data.items(), key=lambda x: x[1], reverse=True)[:8])
            
            response_data = {
                'subjects': sorted_subjects,
                'daily': daily_data
            }
            if stats_type != 'group':
                response_data['groups'] = dict(sorted(groups_data.items(), key=lambda x: x[1], reverse=True)[:8])
            return response_data

        response_data = await asyncio.to_thread(sync_analytics_worker)
        return web.json_response(response_data)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# =================== iCal / .ics Live Feed (Phase 6.3) ===================

async def handle_calendar_feed(request):
    """Генерирует живой календарный фид (.ics) для Google Calendar, Apple Calendar, Outlook."""
    dept = int(request.match_info.get('department', request.query.get('department', 3)))
    gid_param = request.match_info.get('group_id', request.query.get('group_id', 0))
    try:
        group_id = int(gid_param)
    except (ValueError, TypeError):
        return web.Response(text="Invalid group_id", status=400)

    gname = kalich.GROUP_ID_TO_NAME.get(dept, {}).get(group_id, f"Group {group_id}")
    now = now_msk()
    monday = now - timedelta(days=now.weekday())

    from src.config import CALLS
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kalich Bot//Calendar Live Feed//RU",
        f"X-WR-CALNAME:Расписание {gname}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]

    all_data = {d: kalich.get_all_schedules_for_day(d) for d in range(1, 7)}
    for day in range(1, 7):
        date_for_day = monday + timedelta(days=day - 1)
        date_str = date_for_day.strftime("%Y%m%d")
        lessons = all_data.get(day, {}).get((dept, group_id), [])
        for idx, lesson in enumerate(lessons):
            l_str = str(lesson).strip()
            if not l_str or l_str.lower() in ("—", ".", "обед"):
                continue
            room = kalich.extract_room(l_str) or ""
            subj = kalich.re.sub(r'\s*\(.*$', '', l_str).strip()
            if idx < len(CALLS):
                start_h, start_m = CALLS[idx][0].split(":")
                end_h, end_m = CALLS[idx][1].split(":")
            else:
                start_h, start_m, end_h, end_m = "08", "30", "10", "00"

            dt_start = f"{date_str}T{start_h}{start_m}00"
            dt_end = f"{date_str}T{end_h}{end_m}00"
            uid = f"kalich-{dept}-{group_id}-{date_str}-{idx}@kalich.bot"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dt_start}",
                f"DTEND:{dt_end}",
                f"SUMMARY:{subj}",
                f"LOCATION:Кабинет {room}" if room else "LOCATION:Колледж",
                f"DESCRIPTION:{idx+1} пара ({gname})",
                "STATUS:CONFIRMED",
                "END:VEVENT"
            ])

    lines.append("END:VCALENDAR")
    ics_text = "\r\n".join(lines)
    return web.Response(text=ics_text, content_type="text/calendar", charset="utf-8")

# =================== MODERATOR DATA CONTROL ENDPOINTS ===================

# Get all active overrides
async def handle_admin_overrides(request):
    try:
        def sync_admin_overrides():
            conn = sqlite3.connect(kalich.DB_FILE)
            rows = conn.execute(
                "SELECT id, teacher_chat_id, department, day, slot_idx, group_id, new_room, new_subject FROM teacher_room_overrides"
            ).fetchall()
            conn.close()
            
            overrides = []
            for r in rows:
                gname = "Все группы" if r[5] == -1 else kalich.GROUP_ID_TO_NAME.get(r[2], {}).get(r[5], f"Гр. {r[5]}")
                overrides.append({
                    'id': r[0],
                    'teacher_chat_id': r[1],
                    'department': r[2],
                    'day': r[3],
                    'slot_idx': r[4],
                    'group_name': gname,
                    'new_room': r[6],
                    'new_subject': r[7]
                })
            return overrides

        overrides = await asyncio.to_thread(sync_admin_overrides)
        return web.json_response({'overrides': overrides})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Delete single override
async def handle_admin_delete_override(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        chat_id = int(device_id) if device_id else 1234567
        
        if chat_id != 1234567 and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        override_id = int(data.get('id'))
        def sync_delete_override():
            conn = sqlite3.connect(kalich.DB_FILE)
            conn.execute("DELETE FROM teacher_room_overrides WHERE id=?", (override_id,))
            conn.commit()
            conn.close()

        await asyncio.to_thread(sync_delete_override)
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Flush schedules cache table
async def handle_admin_flush(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        chat_id = int(device_id) if device_id else 1234567
        
        if chat_id != 1234567 and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        department = data.get('department', 'all')
        
        def sync_flush():
            conn = sqlite3.connect(kalich.DB_FILE)
            if start_date and end_date:
                if department and department != 'all':
                    conn.execute("DELETE FROM schedule_history WHERE date >= ? AND date <= ? AND department = ?", (start_date, end_date, int(department)))
                    conn.execute("DELETE FROM schedules WHERE department = ?", (int(department),))
                else:
                    conn.execute("DELETE FROM schedule_history WHERE date >= ? AND date <= ?", (start_date, end_date))
                    conn.execute("DELETE FROM schedules")
            else:
                if department and department != 'all':
                    conn.execute("DELETE FROM schedules WHERE department = ?", (int(department),))
                else:
                    conn.execute("DELETE FROM schedules")
            conn.commit()
            conn.close()

        await asyncio.to_thread(sync_flush)
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)
        return web.json_response({'error': str(e)}, status=500)

# Background runner to fill databases
def background_fill_runner(start_date_str=None, end_date_str=None, department=None):
    try:
        print(f"[API] Starting background fill runner for range {start_date_str} to {end_date_str} (dept: {department})...")
        
        if start_date_str and end_date_str:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            # Default to current week Mon-Fri
            today = now_msk()
            start_dt = today - timedelta(days=today.weekday())
            end_dt = start_dt + timedelta(days=4)
            
        delta = timedelta(days=1)
        curr_dt = start_dt
        
        dates_to_fill = []
        while curr_dt <= end_dt:
            if curr_dt.isoweekday() <= 6: # Mon-Sat
                dates_to_fill.append(curr_dt)
            curr_dt += delta
            
        for dt in dates_to_fill:
            date_str = dt.strftime("%Y-%m-%d")
            d = dt.isoweekday()
            print(f"[API] Filling schedule for date: {date_str} (weekday: {d})")
            
            for name, info in kalich.GROUP_NAME_TO_ID.items():
                dep, gid = info[0], info[1]
                if department and department != 'all' and dep != int(department):
                    continue
                raw = kalich.fetch_lessons(d, gid, dep)
                if raw:
                    h = hashlib.md5("".join(raw).encode()).hexdigest()
                    kalich.save_schedule_to_db(dep, gid, d, h, json.dumps(raw, ensure_ascii=False), date_str)
                time.sleep(0.05)
                
        print("[API] Background fill completed successfully.")
    except Exception as e:
        print(f"[API] Background fill error: {e}")

# Fill database cache
async def handle_admin_fill(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        chat_id = int(device_id) if device_id else 1234567
        
        if chat_id != 1234567 and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        department = data.get('department', 'all')
        
        threading.Thread(target=background_fill_runner, args=(start_date, end_date, department), daemon=True).start()
        return web.json_response({'status': 'success', 'message': 'Заполнение базы запущено в фоновом режиме.'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


# Static file serving handlers (supports active webapp, pwa, or archived PWA)
def _find_pwa_file(filename):
    for base in ['webapp', 'pwa', 'archive/pwa']:
        p = os.path.join(base, filename)
        if os.path.exists(p):
            return p
    return None

async def serve_index(request):
    f = _find_pwa_file('index.html')
    if f:
        return web.FileResponse(f)
    return web.Response(text="PWA frontend is archived. API is active.", content_type="text/plain")

async def serve_styles(request):
    f = _find_pwa_file('styles.css')
    if f:
        return web.FileResponse(f)
    return web.Response(text="/* Archived */", content_type="text/css")

async def serve_app_js(request):
    f = _find_pwa_file('app.js')
    if f:
        return web.FileResponse(f)
    return web.Response(text="// Archived", content_type="application/javascript")

async def serve_manifest(request):
    f = _find_pwa_file('manifest.json')
    if f:
        return web.FileResponse(f)
    return web.json_response({"name": "Kalich Bot PWA (Archived)"})

async def serve_sw(request):
    f = _find_pwa_file('sw.js')
    if f:
        return web.FileResponse(f)
    return web.Response(text="// Archived", content_type="application/javascript")

# Ensure dev test teacher is populated
def ensure_dev_teacher():
    try:
        conn = sqlite3.connect(kalich.DB_FILE)
        conn.execute(
            "INSERT OR IGNORE INTO teachers (chat_id, department, rooms, name, status) VALUES (?, ?, ?, ?, ?)",
            (1234567, 3, json.dumps(["302", "303", "304"]), "Тестовый Преподаватель (Dev)", "approved")
        )
        conn.commit()
        conn.close()
        print("[API] Dev mock teacher verified in database.")
    except Exception as e:
        print(f"[API] Dev teacher insertion warning: {e}")

# Main Server start hook
def start_server():
    kalich.init_db()
    ensure_dev_teacher()
    
    app = web.Application(middlewares=[cors_middleware, rate_limit_middleware])
    
    # API endpoints
    app.router.add_get('/api/health', handle_health)
    app.router.add_post('/api/auth', handle_auth)
    app.router.add_post('/api/auth/request_teacher', handle_request_teacher)
    app.router.add_get('/api/groups', handle_groups)
    app.router.add_get('/api/teachers', handle_teachers_list)
    app.router.add_get('/api/schedule', handle_schedule)
    app.router.add_get('/api/teacher/schedule', handle_teacher_schedule)
    app.router.add_post('/api/override', handle_override)
    app.router.add_post('/api/sync', handle_sync)
    app.router.add_post('/api/settings', handle_settings)
    app.router.add_get('/api/analytics', handle_analytics)
    app.router.add_get('/api/calendar/{department}/{group_id}.ics', handle_calendar_feed)
    app.router.add_get('/api/calendar.ics', handle_calendar_feed)
    
    # Admin Panel endpoints
    app.router.add_get('/api/admin/overrides', handle_admin_overrides)
    app.router.add_post('/api/admin/delete_override', handle_admin_delete_override)
    app.router.add_post('/api/admin/flush', handle_admin_flush)
    app.router.add_post('/api/admin/fill', handle_admin_fill)
    
    # Root PWA files
    app.router.add_get('/', serve_index)
    app.router.add_get('/index.html', serve_index)
    app.router.add_get('/styles.css', serve_styles)
    app.router.add_get('/app.js', serve_app_js)
    app.router.add_get('/manifest.json', serve_manifest)
    app.router.add_get('/sw.js', serve_sw)
    
    # Static directory for icons (if present)
    for icon_dir in ['webapp/icons', 'pwa/icons', 'archive/pwa/icons']:
        if os.path.isdir(icon_dir):
            app.router.add_static('/icons', icon_dir)
            break
    
    port = int(os.getenv('PWA_PORT', 8999))
    ssl_cert = os.getenv('SSL_CERT_PATH')
    ssl_key = os.getenv('SSL_KEY_PATH')
    ssl_ctx = None

    if ssl_cert and ssl_key and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
        import ssl
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(certfile=ssl_cert, keyfile=ssl_key)
        print(f"[API] Starting web app server with SSL on https://0.0.0.0:{port}")
    else:
        print(f"[API] Starting web app server on http://localhost:{port}")

    web.run_app(app, host='0.0.0.0', port=port, ssl_context=ssl_ctx, handle_signals=False)


if __name__ == '__main__':
    start_server()
