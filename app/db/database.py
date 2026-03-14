"""
Database Configuration and Table Creation (SQLite)
"""

import sqlite3
from datetime import datetime
import os
import struct


class DatabaseConfig:
    """SQLite database configuration and connection manager"""

    DB_NAME = "face_recognition.db"

    @staticmethod
    def get_db_path():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, DatabaseConfig.DB_NAME)

    @staticmethod
    def get_connection():
        """Get SQLite connection"""
        try:
            conn = sqlite3.connect(DatabaseConfig.get_db_path(), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"[ERROR] Database connection failed: {e}")
            return None

    @staticmethod
    def initialize_tables():
        """Create all required tables"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                department TEXT,
                role TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON users(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_role ON users(role)")

        # Attendance table — includes status column (P=Present, A=Absent, L=Late, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT DEFAULT 'P',
                image_path TEXT,
                confidence_score REAL,
                camera_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # ── Migrate existing DB: add status column if it doesn't exist yet ──
        try:
            cursor.execute("ALTER TABLE attendance ADD COLUMN status TEXT DEFAULT 'P'")
            print("[INFO] Migrated: added 'status' column to attendance table")
        except sqlite3.OperationalError:
            pass  # Column already exists — safe to ignore

        # Backfill any existing rows that have NULL status
        cursor.execute("UPDATE attendance SET status = 'P' WHERE status IS NULL")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON attendance(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_date ON attendance(user_id, date)")

        # Cameras table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                camera_name TEXT NOT NULL,
                camera_source TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Watchlist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                watchlist_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT CHECK(category IN ('blacklist','whitelist','vip')) DEFAULT 'blacklist',
                alert_enabled INTEGER DEFAULT 1,
                alarm_enabled INTEGER DEFAULT 1,
                threshold REAL DEFAULT 0.75,
                cooldown_sec INTEGER DEFAULT 10,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # Watchlist events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_id TEXT,
                user_id TEXT,
                camera_id TEXT,
                confidence_score REAL,
                image_path TEXT,
                alarm_triggered INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_events_date ON watchlist_events(created_at)")

        conn.commit()
        cursor.close()
        conn.close()
        print("[INFO] SQLite database tables initialized successfully")


# ─────────────────────────────────────────────────────────────────────────────
# Status constants — import these wherever you need them
# ─────────────────────────────────────────────────────────────────────────────
class AttendanceStatus:

    PRESENT = 'P'
    ABSENT  = 'A'
    LATE    = 'L'
    LEAVE   = 'LV'

    LABELS = {
        'P':  'Present',
        'A':  'Absent',
        'L':  'Late',
        'LV': 'On Leave',
    }

    @classmethod
    def label(cls, code):
        return cls.LABELS.get(code, code or 'Present')


class AttendanceManager:
    """Manages attendance records with optimization"""

    def __init__(self):
        self.today_attendance_cache = set()
        self.load_today_cache()

    def load_today_cache(self):
        conn = DatabaseConfig.get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()

            cursor.execute("""
                SELECT user_id FROM attendance WHERE date = ?
            """, (today,))

            self.today_attendance_cache = {row["user_id"] for row in cursor.fetchall()}
            cursor.close()
            conn.close()

        except sqlite3.Error as e:
            print(f"[ERROR] Loading attendance cache: {e}")

    def mark_attendance(self, user_id, confidence_score, image_path=None,
                        camera_id=None, status=AttendanceStatus.PRESENT):
        """
        Mark attendance for a user.

        Parameters
        ----------
        user_id         : str   – unique user identifier
        confidence_score: float – face-recognition confidence (0–1)
        image_path      : str   – path to the saved face-crop image
        camera_id       : str   – which camera triggered the recognition
        status          : str   – attendance status code; defaults to 'P' (Present).
                                  Use AttendanceStatus.PRESENT / LATE / etc.
        """
        if user_id in self.today_attendance_cache:
            return False

        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            today        = datetime.now().date().isoformat()
            current_time = datetime.now().time().strftime("%H:%M:%S")

            # Auto-create user if missing (e.g. face enrolled outside UI)
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                print(f"[ATTENDANCE] User {user_id} not found, creating...")
                cursor.execute("""
                    INSERT INTO users (user_id, name, department, role)
                    VALUES (?, ?, ?, ?)
                """, (user_id, f"User {user_id[-8:]}", "Unknown", "Employee"))
                print(f"[ATTENDANCE] ✓ User {user_id} created")

            # Normalise confidence_score to plain float
            if isinstance(confidence_score, bytes):
                confidence_score = struct.unpack('f', confidence_score)[0]
            elif not isinstance(confidence_score, (int, float)):
                confidence_score = float(confidence_score)

            cursor.execute("""
                INSERT INTO attendance (user_id, date, time, status, image_path, confidence_score, camera_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, today, current_time,
                  status,                   # ← 'P' by default
                  image_path,
                  float(confidence_score),
                  camera_id))

            conn.commit()
            self.today_attendance_cache.add(user_id)

            print(f"[ATTENDANCE] ✓ Marked {user_id} as [{status}] {AttendanceStatus.label(status)}")

            cursor.close()
            conn.close()
            return True

        except sqlite3.IntegrityError:
            self.today_attendance_cache.add(user_id)
            return False
        except sqlite3.Error as e:
            print(f"[ERROR] Marking attendance: {e}")
            return False

    def get_attendance_records(self, start_date=None, end_date=None, user_id=None):
        """Get attendance records with proper confidence score conversion"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()

            query = """
                SELECT
                    a.id,
                    a.user_id,
                    a.date,
                    a.time,
                    a.status,
                    a.image_path,
                    a.confidence_score,
                    a.camera_id,
                    a.created_at,
                    u.name,
                    u.department,
                    u.role,
                    u.email,
                    u.phone
                FROM attendance a
                JOIN users u ON a.user_id = u.user_id
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND a.date >= ?"
                params.append(start_date)

            if end_date:
                query += " AND a.date <= ?"
                params.append(end_date)

            if user_id:
                query += " AND a.user_id = ?"
                params.append(user_id)

            query += " ORDER BY a.date DESC, a.time DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            records = []
            for row in rows:
                record_dict = dict(row)

                # Normalise binary confidence_score (legacy rows)
                conf_score = record_dict.get('confidence_score')
                if isinstance(conf_score, bytes):
                    try:
                        record_dict['confidence_score'] = struct.unpack('f', conf_score)[0]
                    except Exception:
                        record_dict['confidence_score'] = 0.0
                elif conf_score is None:
                    record_dict['confidence_score'] = 0.0
                else:
                    record_dict['confidence_score'] = float(conf_score)

                # Always surface a status value
                if not record_dict.get('status'):
                    record_dict['status'] = AttendanceStatus.PRESENT

                records.append(record_dict)

            cursor.close()
            conn.close()

            print(f"[DEBUG] Retrieved {len(records)} attendance records")
            if records:
                print(f"[DEBUG] Sample record: {records[0]}")

            return records

        except sqlite3.Error as e:
            print(f"[ERROR] Getting attendance records: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_all_attendance_details(self):
        """Get all attendance details"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attendance")
            rows = cursor.fetchall()

            records = []
            for row in rows:
                record_dict = dict(row)

                conf_score = record_dict.get('confidence_score')
                if isinstance(conf_score, bytes):
                    try:
                        record_dict['confidence_score'] = struct.unpack('f', conf_score)[0]
                    except Exception:
                        record_dict['confidence_score'] = 0.0
                elif conf_score is None:
                    record_dict['confidence_score'] = 0.0
                else:
                    record_dict['confidence_score'] = float(conf_score)

                if not record_dict.get('status'):
                    record_dict['status'] = AttendanceStatus.PRESENT

                records.append(record_dict)

            return records

        except Exception as e:
            print(f"[ERROR] Fetching attendance details: {e}")
            import traceback
            traceback.print_exc()
            return []

        finally:
            cursor.close()
            conn.close()


class UserManager:
    """Manages user records"""

    @staticmethod
    def add_user(user_id, name, email=None, phone=None, department=None, role="Employee"):
        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, name, email, phone, department, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, name, email, phone, department, role))

            conn.commit()
            cursor.close()
            conn.close()
            return True

        except sqlite3.IntegrityError:
            print(f"[WARN] User {user_id} already exists")
            return False
        except sqlite3.Error as e:
            print(f"[ERROR] Adding user: {e}")
            return False

    @staticmethod
    def get_user_by_id(user_id):
        conn = DatabaseConfig.get_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, name, email, phone, department, role,
                       created_at, updated_at
                FROM users
                WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            print(f"[USER_MANAGER ERROR] Failed to get user: {e}")
            return None

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_user(user_id):
        conn = DatabaseConfig.get_connection()
        if not conn:
            return None

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def get_all_users():
        conn = DatabaseConfig.get_connection()
        if not conn:
            return []

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY name")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(user) for user in users]

    @staticmethod
    def update_user(user_id, **kwargs):
        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        fields, values = [], []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return False

        values.append(user_id)
        query = f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?"

        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        return True


def init_database():
    """Initialize SQLite database"""
    DatabaseConfig.initialize_tables()
    print("[INFO] SQLite database initialization complete")


def fix_existing_confidence_scores():
    """
    One-time migration: fix binary confidence scores stored in legacy rows.
    """
    conn = DatabaseConfig.get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, confidence_score FROM attendance")
        records = cursor.fetchall()

        fixed_count = 0
        for record in records:
            record_id  = record['id']
            conf_score = record['confidence_score']

            if isinstance(conf_score, bytes):
                try:
                    float_score = struct.unpack('f', conf_score)[0]
                    cursor.execute(
                        "UPDATE attendance SET confidence_score = ? WHERE id = ?",
                        (float_score, record_id)
                    )
                    fixed_count += 1
                except Exception as e:
                    print(f"[ERROR] Failed to convert record {record_id}: {e}")

        conn.commit()
        print(f"[INFO] Fixed {fixed_count} confidence score records")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()