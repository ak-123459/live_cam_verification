"""
Watchlist Manager - Handles watchlist operations
"""
import sqlite3
from datetime import datetime
from app.db.database import DatabaseConfig


class WatchlistManager:
    """Manages watchlist records and events"""

    @staticmethod
    def get_active_watchlist():
        """Get all active watchlist entries with user details"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.*, u.name
                FROM watchlist w
                JOIN users u ON w.user_id = u.user_id
                WHERE w.active = 1
            """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to get active watchlist: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def add_to_watchlist(user_id, category='blacklist', alert_enabled=True,
                         alarm_enabled=True, threshold=0.75, cooldown_sec=10):
        """Add user to watchlist"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()

            # Generate watchlist_id
            watchlist_id = f"wl_{user_id}_{int(datetime.now().timestamp())}"

            cursor.execute("""
                INSERT INTO watchlist 
                (watchlist_id, user_id, category, alert_enabled, alarm_enabled, 
                 threshold, cooldown_sec, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (watchlist_id, user_id, category,
                  1 if alert_enabled else 0,
                  1 if alarm_enabled else 0,
                  threshold, cooldown_sec))

            conn.commit()
            print(f"[WATCHLIST] ✓ Added {user_id} to watchlist as {category}")
            return True

        except sqlite3.IntegrityError:
            print(f"[WATCHLIST] User {user_id} already in watchlist")
            return False
        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to add to watchlist: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def remove_from_watchlist(user_id):
        """Remove user from watchlist"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = ?", (user_id,))
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                print(f"[WATCHLIST] ✓ Removed {user_id} from watchlist")
            return deleted

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to remove from watchlist: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def update_watchlist(user_id, **kwargs):
        """Update watchlist entry"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        try:
            fields = []
            values = []

            for key, value in kwargs.items():
                if value is not None and key in ['category', 'alert_enabled',
                                                 'alarm_enabled', 'threshold',
                                                 'cooldown_sec', 'active']:
                    fields.append(f"{key} = ?")
                    values.append(value)

            if not fields:
                return False

            values.append(user_id)
            query = f"UPDATE watchlist SET {', '.join(fields)} WHERE user_id = ?"

            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()

            print(f"[WATCHLIST] ✓ Updated {user_id} in watchlist")
            return True

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to update watchlist: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_watchlist_entry(user_id):
        """Get specific watchlist entry"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.*, u.name
                FROM watchlist w
                JOIN users u ON w.user_id = u.user_id
                WHERE w.user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to get watchlist entry: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def log_watchlist_event(watchlist_id, user_id, camera_id, confidence_score,
                            image_path, alarm_triggered):
        """Log watchlist detection event"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watchlist_events
                (watchlist_id, user_id, camera_id, confidence_score, 
                 image_path, alarm_triggered)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (watchlist_id, user_id, camera_id, confidence_score,
                  image_path, 1 if alarm_triggered else 0))

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to log event: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_watchlist_events(start_date=None, end_date=None, user_id=None,
                             category=None, limit=100):
        """Get watchlist events with filters"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()

            query = """
                SELECT 
                    we.*,
                    w.category,
                    u.name,
                    u.department
                FROM watchlist_events we
                JOIN watchlist w ON we.watchlist_id = w.watchlist_id
                JOIN users u ON we.user_id = u.user_id
                WHERE 1=1
            """
            params = []

            if start_date:
                query += " AND DATE(we.created_at) >= ?"
                params.append(start_date)

            if end_date:
                query += " AND DATE(we.created_at) <= ?"
                params.append(end_date)

            if user_id:
                query += " AND we.user_id = ?"
                params.append(user_id)

            if category:
                query += " AND w.category = ?"
                params.append(category)

            query += " ORDER BY we.created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to get events: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all_watchlist():
        """Get all watchlist entries (active and inactive)"""
        conn = DatabaseConfig.get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.*, u.name, u.department
                FROM watchlist w
                JOIN users u ON w.user_id = u.user_id
                ORDER BY w.created_at DESC
            """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[WATCHLIST ERROR] Failed to get all watchlist: {e}")
            return []
        finally:
            cursor.close()
            conn.close()