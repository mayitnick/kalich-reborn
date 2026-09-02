import io
import re
import json
import collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.config import CALLS
from src.database import get_db_connection, extract_room, custom_names_manager
from src.services.parser import GROUP_ID_TO_NAME


def apply_chart_style():
    """Применяет темную тему для графиков Matplotlib."""
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


def generate_group_subject_chart(group_id, department, group_name, start_date=None, end_date=None, chat_id=None):
    """Генерирует круговую/столбчатую диаграмму предметов для группы."""
    conn = get_db_connection()
    query = "SELECT lessons_text FROM schedule_history WHERE group_id = ? AND department = ?"
    params = [group_id, department]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    subject_counts = collections.Counter()
    for (lessons_json,) in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
        for lesson in lessons:
            l_str = str(lesson).strip()
            if not l_str or l_str.lower() == "обед" or l_str in ["—", "о", "О", "x", "X", "."]:
                continue

            if chat_id:
                applied = custom_names_manager.apply(chat_id, l_str)
                if not applied:
                    continue
                l_str = applied

            subj = re.sub(r'\s*\(.*$', '', l_str).strip()
            if subj:
                subject_counts[subj] += 1

    if not subject_counts:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    sorted_data = sorted(subject_counts.items(), key=lambda x: x[1])
    subjects = [x[0] for x in sorted_data]
    counts = [x[1] for x in sorted_data]

    colors = ['#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#a6e3a1', '#f9e2af', '#fab387', '#f38ba8']
    bar_colors = [colors[i % len(colors)] for i in range(len(subjects))]

    bars = ax.barh(subjects, counts, color=bar_colors, edgecolor='#1e1e2e', height=0.6)

    for bar in bars:
        width = bar.get_width()
        pairs = width / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f'{int(width)}ч{pairs_str}',
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    ax.set_title(
        f"Распределение часов по предметам{date_range_str}\nГруппа: {group_name}",
        fontsize=12, pad=15, fontweight='bold'
    )
    ax.set_xlabel("Академические часы (пара = 2 ч)", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def generate_group_daily_chart(group_id, department, group_name, start_date=None, end_date=None):
    """Генерирует график нагрузки группы по дням."""
    conn = get_db_connection()
    query = "SELECT date, lessons_text FROM schedule_history WHERE group_id = ? AND department = ?"
    params = [group_id, department]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    daily_stats = {}
    for date_str, lessons_json in rows:
        try:
            lessons = json.loads(lessons_json)
        except Exception:
            continue
        hours = sum(1 for l in lessons if str(l).strip() and str(l).strip().lower() != "обед" and str(l).strip() not in ["—", "о", "О", "x", "X", "."])
        parts = date_str.split('-')
        formatted_date = f"{parts[2]}.{parts[1]}"
        daily_stats[formatted_date] = hours

    if not daily_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    dates = list(daily_stats.keys())
    counts = list(daily_stats.values())

    bars = ax.bar(dates, counts, color='#94e2d5', edgecolor='#1e1e2e', width=0.4 if len(dates) > 1 else 0.2)

    for bar in bars:
        height = bar.get_height()
        pairs = height / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.1, f'{int(height)}ч{pairs_str}',
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    ax.set_title(f"Учебная нагрузка по дням{date_range_str}\nГруппа: {group_name}", fontsize=12, pad=15, fontweight='bold')
    ax.set_ylabel("Академические часы", labelpad=10)
    ax.set_ylim(0, max(counts) + 2 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def get_teacher_aggregated_data(teacher_rooms, department, start_date=None, end_date=None, chat_id=None):
    """Стягивает агрегированные данные по кабинетам преподавателя."""
    conn = get_db_connection()
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
                if chat_id:
                    applied = custom_names_manager.apply(chat_id, l_str)
                    if applied:
                        subj = re.sub(r'\s*\(.*$', '', applied).strip()

                hours_by_group[group_name] += 1
                hours_by_subject[subj] += 1

    hours_by_date = {d: len(slots) for d, slots in teacher_active_slots_by_date.items()}
    sorted_hours_by_date = dict(sorted(hours_by_date.items()))

    return {
        "daily": sorted_hours_by_date,
        "groups": dict(hours_by_group),
        "subjects": dict(hours_by_subject)
    }


def generate_teacher_daily_chart(teacher_name, teacher_rooms, department, start_date=None, end_date=None):
    """Генерирует график нагрузки преподавателя по дням."""
    data = get_teacher_aggregated_data(teacher_rooms, department, start_date, end_date)
    daily_stats = data["daily"]
    if not daily_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    dates = []
    for d in daily_stats.keys():
        parts = d.split('-')
        dates.append(f"{parts[2]}.{parts[1]}")
    counts = list(daily_stats.values())

    bars = ax.bar(dates, counts, color='#fab387', edgecolor='#1e1e2e', width=0.4 if len(dates) > 1 else 0.2)

    for bar in bars:
        height = bar.get_height()
        pairs = height / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.1, f'{int(height)}ч{pairs_str}',
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(
        f"Преподаватель: {teacher_name} (каб. {rooms_str})\nУчебные часы по дням{date_range_str}",
        fontsize=11, pad=15, fontweight='bold'
    )
    ax.set_ylabel("Академические часы", labelpad=10)
    ax.set_ylim(0, max(counts) + 2 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def generate_teacher_groups_chart(teacher_name, teacher_rooms, department, start_date=None, end_date=None):
    """Генерирует график нагрузки преподавателя по учебным группам."""
    data = get_teacher_aggregated_data(teacher_rooms, department, start_date, end_date)
    group_stats = data["groups"]
    if not group_stats:
        return None

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
        ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f'{int(width)}ч{pairs_str}',
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(
        f"Преподаватель: {teacher_name} (каб. {rooms_str})\nРаспределение часов по группам{date_range_str}",
        fontsize=11, pad=15, fontweight='bold'
    )
    ax.set_xlabel("Академические часы", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def generate_teacher_subjects_chart(teacher_name, teacher_rooms, department, start_date=None, end_date=None, chat_id=None):
    """Генерирует график распределения предметов у преподавателя."""
    data = get_teacher_aggregated_data(teacher_rooms, department, start_date, end_date, chat_id)
    subject_stats = data["subjects"]
    if not subject_stats:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    sorted_data = sorted(subject_stats.items(), key=lambda x: x[1])
    subjects = [x[0] for x in sorted_data]
    counts = [x[1] for x in sorted_data]

    colors = ['#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#a6e3a1', '#f9e2af', '#fab387', '#f38ba8']
    bar_colors = [colors[i % len(colors)] for i in range(len(subjects))]

    bars = ax.barh(subjects, counts, color=bar_colors, edgecolor='#1e1e2e', height=0.6)

    for bar in bars:
        width = bar.get_width()
        pairs = width / 2
        pairs_str = f" ({pairs:.1f}п)" if pairs % 1 != 0 else f" ({int(pairs)}п)"
        ax.text(width + 0.1, bar.get_y() + bar.get_height() / 2, f'{int(width)}ч{pairs_str}',
                va='center', ha='left', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    rooms_str = ", ".join(teacher_rooms)
    ax.set_title(
        f"Преподаватель: {teacher_name} (каб. {rooms_str})\nНагрузка по предметам{date_range_str}",
        fontsize=11, pad=15, fontweight='bold'
    )
    ax.set_xlabel("Академические часы", labelpad=10)
    ax.grid(axis='x', linestyle='--', alpha=0.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def get_time_distribution_stats(department=None, start_date=None, end_date=None):
    """Считает общую статистику занятости пар по слотам."""
    conn = get_db_connection()
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


def generate_time_distribution_chart(department=None, start_date=None, end_date=None):
    """Генерирует график распределения занятий по времени (номерам пар)."""
    slot_counts = get_time_distribution_stats(department, start_date, end_date)
    if sum(slot_counts) == 0:
        return None

    apply_chart_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    slots = [f"{i+1} пара\n({CALLS[i][0]})" for i in range(len(slot_counts))]
    counts = slot_counts

    bars = ax.bar(slots, counts, color='#b4befe', edgecolor='#1e1e2e', width=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.1, f'{int(height)}',
                va='bottom', ha='center', color='#cdd6f4', fontweight='bold', fontsize=9)

    date_range_str = ""
    if start_date and end_date:
        if start_date == end_date:
            date_range_str = f" за {start_date}"
        else:
            date_range_str = f" с {start_date} по {end_date}"

    dep_str = f" | Отделение {department}" if department is not None else ""
    ax.set_title(
        f"Распределение занятий по времени (парам){date_range_str}{dep_str}\n(Загруженность расписания)",
        fontsize=11, pad=15, fontweight='bold'
    )
    ax.set_ylabel("Количество проведенных часов (слотов)", labelpad=10)
    ax.set_ylim(0, max(counts) + max(counts) * 0.15 if counts else 10)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.xticks(rotation=15)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf
