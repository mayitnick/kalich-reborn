#!/usr/bin/env python3
"""
Скрипт автоматического безопасного бэкапа базы данных SQLite с ротацией (Phase 9.3).
Выполняет VACUUM INTO для создания целостного снимка даже при активных операциях записи.
"""
import os
import sys
import glob
import time
import sqlite3
from datetime import datetime

DB_FILE = os.getenv("DB_FILE", "data/schedules.db")
BACKUP_DIR = os.getenv("BACKUP_DIR", "data/backups")
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", 14))


def create_backup():
    if not os.path.exists(DB_FILE):
        print(f"[Backup] Database file {DB_FILE} does not exist, skipping.")
        return False

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"schedules_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    print(f"[Backup] Creating backup: {backup_path}")
    try:
        conn = sqlite3.connect(DB_FILE)
        # SQLite VACUUM INTO безопасно копирует базу в WAL-режиме
        conn.execute(f"VACUUM INTO '{backup_path}';")
        conn.close()
        print(f"[Backup] Successfully created {backup_path}")
    except Exception as e:
        print(f"[Backup] Error during backup: {e}", file=sys.stderr)
        return False

    # Ротация старых бэкапов
    now = time.time()
    for f in glob.glob(os.path.join(BACKUP_DIR, "schedules_backup_*.db")):
        try:
            mtime = os.path.getmtime(f)
            if now - mtime > RETENTION_DAYS * 86400:
                os.remove(f)
                print(f"[Backup] Removed expired backup: {f}")
        except Exception as e:
            print(f"[Backup] Error removing old backup {f}: {e}")

    return True


if __name__ == "__main__":
    success = create_backup()
    sys.exit(0 if success else 1)
