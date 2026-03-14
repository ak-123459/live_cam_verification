"""
One-time script to sync attendance user_ids with users table
Run this to fix existing attendance records
"""
from app.db.database import DatabaseConfig, UserManager
import sqlite3


def sync_attendance_users():
    """Create user records for all user_ids in attendance that don't exist in users"""
    conn = DatabaseConfig.get_connection()
    if not conn:
        print("Failed to connect to database")
        return

    try:
        cursor = conn.cursor()

        # Find user_ids in attendance that don't exist in users
        cursor.execute("""
            SELECT DISTINCT a.user_id
            FROM attendance a
            LEFT JOIN users u ON a.user_id = u.user_id
            WHERE u.user_id IS NULL
        """)

        missing_users = cursor.fetchall()

        print(f"\n[SYNC] Found {len(missing_users)} user_ids in attendance without user records")

        for row in missing_users:
            user_id = row[0]
            print(f"[SYNC] Creating user record for: {user_id}")

            # Create a basic user record
            UserManager.add_user(
                user_id=user_id,
                name=f"User {user_id[-8:]}",  # Use last 8 chars of ID as name
                email=None,
                phone=None,
                department="Unknown",
                role="Employee"
            )

        print(f"\n[SYNC] ✓ Sync complete! Created {len(missing_users)} user records")

    except Exception as e:
        print(f"[SYNC ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    sync_attendance_users()