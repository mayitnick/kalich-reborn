import sqlite3
import json
import collections
import re
import os
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DB_FILE = 'schedules.db'

CALLS = [
    ("08:20", "09:05"), ("09:05", "09:50"), ("10:00", "10:45"), ("10:45", "11:30"),
    ("11:35", "12:20"), ("12:25", "13:10"), ("13:15", "14:00"), ("14:00", "14:45"),
    ("14:50", "15:35"), ("15:40", "16:25")
]

# Simple reverse lookup cache for testing group name
GROUP_ID_TO_NAME = {
    1: {50: "Бух-41"},
    2: {},
    3: {360: "ИС-41-22"}
}

def extract_room(lesson_text):
    if not lesson_text:
        return None
    first_open = lesson_text.find('(')
    if first_open == -1:
        return None
    last_close = lesson_text.rfind(')')
    if last_close == -1 or last_close < first_open:
        return None
    return lesson_text[first_open+1:last_close].strip()

def parse_date_range(text):
    if not text:
        return None, None
    matches = re.findall(r'(\d{2})\.(\d{2})\.(\d{4})', text)
    if not matches:
        return None, None
    
    dates = []
    for d, m, y in matches:
        try:
            dt = datetime(int(y), int(m), int(d))
            dates.append(dt.strftime('%Y-%m-%d'))
        except ValueError:
            continue
            
    if len(dates) == 1:
        return dates[0], dates[0]
    elif len(dates) >= 2:
        d1, d2 = dates[0], dates[1]
        if d1 > d2:
            return d2, d1
        return d1, d2
    return None, None

def apply_chart_style():
    plt.style.use('dark_background')
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Segoe UI', 'Arial', 'sans-serif']
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['figure.facecolor'] = '#181825'
    plt.rcParams['axes.facecolor'] = '#1e1e2e'
    plt.rcParams['axes.edgecolor'] = '#45475a'
    plt.rcParams['axes.labelcolor'] = '#cdd6f4'
    plt.rcParams['xtick.color'] = '#bac2de'
    plt.rcParams['ytick.color'] = '#bac2de'
    plt.rcParams['grid.color'] = '#313244'
    plt.rcParams['text.color'] = '#cdd6f4'

def get_teacher_aggregated_data(teacher_rooms, department, start_date=None, end_date=None):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT date, group_id, lessons_text FROM schedule_history WHERE department = ?"
    params = [department]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    teacher_active_slots_by_date = collections.defaultdict(set)
    hours_by_group = collections.Counter()
    hours_by_subject = collections.Counter()
    
    for date_str, group_id, lessons_json in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
            
        group_name = GROUP_ID_TO_NAME.get(department, {}).get(group_id, f"Гр. {group_id}")
        
        for idx, lesson in enumerate(lessons):
            l_str = str(lesson).strip()
            if not l_str or l_str.lower() == "обед" or l_str in ["—", "о", "О", "x", "X", "."]:
                continue
                
            room = extract_room(l_str)
            if room and any(r.strip() in room for r in teacher_rooms):
                teacher_active_slots_by_date[date_str].add(idx)
                
                subj = re.sub(r'\s*\(.*$', '', l_str).strip()
                hours_by_group[group_name] += 1
                hours_by_subject[subj] += 1
                
    hours_by_date = {d: len(slots) for d, slots in teacher_active_slots_by_date.items()}
    sorted_hours_by_date = dict(sorted(hours_by_date.items()))
    
    return {
        "daily": sorted_hours_by_date,
        "groups": dict(hours_by_group),
        "subjects": dict(hours_by_subject)
    }

def get_time_distribution_stats(department=None, start_date=None, end_date=None):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT lessons_text FROM schedule_history"
    conditions = []
    params = []
    if department is not None:
        conditions.append("department = ?")
        params.append(department)
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    slot_counts = [0] * 10
    for (lessons_json,) in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
        for idx in range(min(len(lessons), 10)):
            l_str = str(lessons[idx]).strip()
            if not l_str or l_str.lower() == "обед" or l_str in ["—", "о", "О", "x", "X", "."]:
                continue
            slot_counts[idx] += 1
            
    return slot_counts

def generate_teacher_groups_chart(teacher_name, teacher_rooms, department, start_date=None, end_date=None):
    data = get_teacher_aggregated_data(teacher_rooms, department, start_date, end_date)
    group_stats = data["groups"]
    if not group_stats:
        print("No teacher group stats found.")
        return False
        
    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 6))
    
    sorted_data = sorted(group_stats.items(), key=lambda x: x[1])
    groups = [x[0] for x in sorted_data]
    counts = [x[1] for x in sorted_data]
    
    colors = ['#a6e3a1', '#94e2d5', '#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#fab387', '#f38ba8']
    bar_colors = [colors[i % len(colors)] for i in range(len(groups))]
    
    bars = ax.barh(groups, counts, color=bar_colors, edgecolor='#1e1e2e', height=0.6)
    
    for bar in bars:
        width = bar.get_width()
        pairs = width / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(width + 0.1, bar.get_y() + bar.get_height()/2, f'{int(width)}ч{pairs_str}', 
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)
                
    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"
            
    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(f"Преподаватель: {teacher_name} (каб. {rooms_str})\nРаспределение часов по группам{date_range_str}", fontsize=11, pad=15, fontweight='bold')
    ax.set_xlabel("Академические часы", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('scratch/test_teacher_groups.png', dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print("Teacher groups chart saved to scratch/test_teacher_groups.png")
    return True

def generate_time_distribution_chart(department=None, start_date=None, end_date=None):
    slot_counts = get_time_distribution_stats(department, start_date, end_date)
    if sum(slot_counts) == 0:
        print("No time slots data found.")
        return False
        
    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    
    slots = [f"{i+1} пара\n({CALLS[i][0]})" for i in range(len(slot_counts))]
    counts = slot_counts
    
    bars = ax.bar(slots, counts, color='#b4befe', edgecolor='#1e1e2e', width=0.5)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.1, f'{int(height)}', 
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)
                
    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"
            
    dep_str = f" | Отделение {department}" if department is not None else ""
    ax.set_title(f"Распределение занятий по времени (парам){date_range_str}{dep_str}\n(Загруженность расписания)", fontsize=11, pad=15, fontweight='bold')
    ax.set_ylabel("Количество проведенных часов (слотов)", labelpad=10)
    ax.set_ylim(0, max(counts) + max(counts)*0.15 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig('scratch/test_time_distribution.png', dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print("Time distribution chart saved to scratch/test_time_distribution.png")
    return True

if __name__ == "__main__":
    # Test date parsing
    print("Test date parsing '15.06.2026 - 19.06.2026':", parse_date_range('15.06.2026 - 19.06.2026'))
    print("Test date parsing '17.06.2026':", parse_date_range('17.06.2026'))
    print("Test date parsing 'invalid':", parse_date_range('invalid'))
    
    # Test teacher stats (using room '203' from department 1 as an example room)
    generate_teacher_groups_chart("Тест Учитель", ["203"], 1)
    
    # Test time distribution
    generate_time_distribution_chart(1)
