import sqlite3
import os
from datetime import datetime

DB_FILE = os.getenv("DATABASE_FILE", "stock_tracker.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Watchlist table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        market TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 2. Notification Schedules table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notification_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time_str TEXT NOT NULL UNIQUE,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 3. Report History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_title TEXT NOT NULL,
        file_name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Insert default schedules if empty (e.g. 08:30, 15:40)
    cursor.execute("SELECT COUNT(*) FROM notification_schedules")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO notification_schedules (time_str, is_active) VALUES ('08:30', 1), ('15:40', 1)")
    
    # Insert default stocks if empty (e.g. Samsung, Apple)
    cursor.execute("SELECT COUNT(*) FROM watchlist")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO watchlist (ticker, name, market) VALUES ('005930', '삼성전자', 'KR'), ('AAPL', 'Apple Inc', 'US')")
        
    conn.commit()
    conn.close()

# Watchlist CRUD
def add_to_watchlist(ticker: str, name: str, market: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO watchlist (ticker, name, market) VALUES (?, ?, ?)",
            (ticker.strip().upper(), name.strip(), market.strip().upper())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_watchlist():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watchlist ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_from_watchlist(item_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

# Schedule CRUD
def add_schedule(time_str: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # standard validation "HH:MM"
        datetime.strptime(time_str, "%H:%M")
        cursor.execute(
            "INSERT INTO notification_schedules (time_str, is_active) VALUES (?, 1)",
            (time_str.strip(),)
        )
        conn.commit()
        return True
    except (ValueError, sqlite3.IntegrityError):
        return False
    finally:
        conn.close()

def get_schedules():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notification_schedules ORDER BY time_str ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def toggle_schedule(schedule_id: int, is_active: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notification_schedules SET is_active = ? WHERE id = ?",
        (1 if is_active else 0, schedule_id)
    )
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

def delete_schedule(schedule_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notification_schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

# Report History CRUD
def add_report_history(report_title: str, file_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO report_history (report_title, file_name) VALUES (?, ?)",
            (report_title, file_name)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_report_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM report_history ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_latest_report():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM report_history ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
