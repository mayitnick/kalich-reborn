import os
import json
import sqlite3
import hashlib
import time
import hmac
import threading
from urllib.parse import parse_qsl
from datetime import datetime, timedelta
from aiohttp import web
import kalich

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
        print(f"[API] InitData check failed: {e}")
        return None

# Helper to fetch and cache group lessons
def get_group_lessons_helper(dept, group_id, day, date_str):
    conn = sqlite3.connect(kalich.DB_FILE)
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
        
        # Determine role from DB
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
        
        profile = {
            'id': chat_id,
            'role': role,
            'department': dept,
            'rooms': rooms,
            'settings': settings
        }
        
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
        
        conn = sqlite3.connect(kalich.DB_FILE)
        conn.execute(
            "INSERT OR REPLACE INTO teachers (chat_id, department, rooms, name, status) VALUES (?, ?, ?, ?, 'pending')",
            (chat_id, department, rooms_json, name)
        )
        conn.commit()
        conn.close()
        
        # Send to telegram moderators
        kalich.send_teacher_approval_request(chat_id, name, department, rooms)
        
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Get Groups Cache
async def handle_groups(request):
    if not kalich.GROUP_NAME_TO_ID:
        print("[API] Groups cache is empty. Triggering force update...")
        import asyncio
        loop = asyncio.get_event_loop()
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
            week_schedules = {}
            for d in range(1, 7):
                d_date = kalich.get_date_for_weekday(d)
                gid = int(group_id_param)
                lessons = get_group_lessons_helper(dept, gid, d, d_date)
                
                # Apply overrides
                all_data = {(dept, gid): lessons}
                overridden = kalich.apply_teacher_overrides(all_data, d, d_date)
                week_schedules[d] = overridden.get((dept, gid), lessons)
            return web.json_response({'week_schedules': week_schedules})

        # CASE 2: Query all groups of a department for a day/date
        elif group_id_param == 'all':
            if day == 'all':
                return web.json_response({'error': 'Cannot request entire week for all groups at once'}, status=400)
                
            # Find all groups belonging to the department
            dept_groups = []
            for name, info in kalich.GROUP_NAME_TO_ID.items():
                if info[0] == dept:
                    dept_groups.append((name, info[1]))
            
            dept_schedules = {}
            for gname, gid in dept_groups:
                lessons = get_group_lessons_helper(dept, gid, day, date_str)
                
                # Apply overrides
                all_data = {(dept, gid): lessons}
                overridden = kalich.apply_teacher_overrides(all_data, day, date_str)
                dept_schedules[gname] = overridden.get((dept, gid), lessons)
            return web.json_response({'department_schedules': dept_schedules})

        # CASE 3: Single day & single group query
        else:
            gid = int(group_id_param)
            if day > 6:
                return web.json_response([])
                
            lessons = get_group_lessons_helper(dept, gid, day, date_str)
            
            # Apply Overrides
            all_data = {(dept, gid): lessons}
            overridden = kalich.apply_teacher_overrides(all_data, day, date_str)
            final_lessons = overridden.get((dept, gid), lessons)
            
            return web.json_response(final_lessons)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Get Teacher Schedule
async def handle_teacher_schedule(request):
    try:
        chat_id = int(request.query.get('chat_id', 0))
        day = int(request.query.get('day', 1))
        date_str = request.query.get('date', '')
        if not date_str:
            date_str = kalich.get_date_for_weekday(day)
            
        if chat_id != 1234567 and not kalich.is_teacher(chat_id) and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        all_data = kalich.get_all_schedules_for_day(day)
        all_data = kalich.apply_teacher_overrides(all_data, day, date_str)
        
        dept, rooms, schedule = kalich.get_teacher_schedule(chat_id, day, all_data)
        return web.json_response(schedule)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Post Substitution Override
async def handle_override(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        chat_id = int(device_id) if device_id else 1234567
        
        if chat_id != 1234567 and not kalich.is_teacher(chat_id) and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        dept = int(data.get('department'))
        day = int(data.get('day'))
        slot_idx = int(data.get('slot_idx'))
        group_id = int(data.get('group_id'))
        new_room = data.get('new_room')
        new_subject = data.get('new_subject')
        date_str = data.get('date')
        
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
            
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Offline sync bulk overrides
async def handle_sync(request):
    try:
        data = await request.json()
        init_data = data.get('initData', '')
        overrides = data.get('overrides', [])
        
        user_data = verify_telegram_init_data(init_data, kalich.BOT_TOKEN)
        chat_id = user_data.get('id') if user_data else 1234567
        
        if chat_id != 1234567 and not kalich.is_teacher(chat_id) and chat_id not in kalich.MODERATOR_IDS:
            return web.json_response({'error': 'Unauthorized'}, status=401)
            
        for o in overrides:
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
                
        return web.json_response({'status': 'success', 'synced': len(overrides)})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Settings Update
async def handle_settings(request):
    try:
        data = await request.json()
        init_data = data.get('initData', '')
        settings = data.get('settings', {})
        
        user_data = verify_telegram_init_data(init_data, kalich.BOT_TOKEN)
        chat_id = user_data.get('id') if user_data else 1234567
        
        for k, v in settings.items():
            kalich.set_user_setting(chat_id, k, v)
            
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# Analytics Data
async def handle_analytics(request):
    try:
        stats_type = request.query.get('type', 'group')
        target = request.query.get('target', '')
        
        if not target:
            return web.json_response({'error': 'Missing target'}, status=400)
            
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
            
        return web.json_response(response_data)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# =================== MODERATOR DATA CONTROL ENDPOINTS ===================

# Get all active overrides
async def handle_admin_overrides(request):
    try:
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
        conn = sqlite3.connect(kalich.DB_FILE)
        conn.execute("DELETE FROM teacher_room_overrides WHERE id=?", (override_id,))
        conn.commit()
        conn.close()
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
        return web.json_response({'status': 'success'})
    except Exception as e:
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
            today = datetime.now()
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


# Static file serving handlers to prevent mime-type mismatches
async def serve_index(request):
    return web.FileResponse('pwa/index.html')

async def serve_styles(request):
    return web.FileResponse('pwa/styles.css')

async def serve_app_js(request):
    return web.FileResponse('pwa/app.js')

async def serve_manifest(request):
    return web.FileResponse('pwa/manifest.json')

async def serve_sw(request):
    return web.FileResponse('pwa/sw.js')

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
    
    app = web.Application()
    
    # API endpoints
    app.router.add_post('/api/auth', handle_auth)
    app.router.add_post('/api/auth/request_teacher', handle_request_teacher)
    app.router.add_get('/api/groups', handle_groups)
    app.router.add_get('/api/schedule', handle_schedule)
    app.router.add_get('/api/teacher/schedule', handle_teacher_schedule)
    app.router.add_post('/api/override', handle_override)
    app.router.add_post('/api/sync', handle_sync)
    app.router.add_post('/api/settings', handle_settings)
    app.router.add_get('/api/analytics', handle_analytics)
    
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
    
    # Static directory for icons
    app.router.add_static('/icons', 'pwa/icons')
    
    port = int(os.getenv('PWA_PORT', 8080))
    print(f"[API] Starting web app server on http://localhost:{port}")
    web.run_app(app, host='0.0.0.0', port=port, handle_signals=False)
