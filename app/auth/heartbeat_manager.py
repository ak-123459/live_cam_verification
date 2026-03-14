"""
Heartbeat Manager for tracking active sessions
Prevents multiple device logins
"""
import time
from PySide6.QtCore import QThread, Signal
from firebase_admin import firestore


class HeartbeatWorker(QThread):
    """Background thread for sending heartbeats"""

    session_conflict = Signal(str)  # Emits device info if conflict detected

    def __init__(self, uid: str, device_id: str, db):
        super().__init__()
        self.uid = uid
        self.device_id = device_id
        self.db = db
        self.running = True
        self.heartbeat_interval = 3600  # seconds


    def run(self):
        """Send heartbeat every interval"""
        while self.running:
            try:
                # Check if another device is active
                session_ref = self.db.collection('active_sessions').document(self.uid)
                session_doc = session_ref.get()

                if session_doc.exists:
                    session_data = session_doc.to_dict()
                    active_device = session_data.get('device_id')

                    # If another device is active, emit conflict
                    if active_device != self.device_id:
                        last_heartbeat = session_data.get('last_heartbeat', 0)

                        # Only conflict if other device sent heartbeat recently (within 30 seconds)
                        if time.time() - last_heartbeat < 30:
                            self.session_conflict.emit(active_device)
                            self.running = False
                            return

                # Update heartbeat
                session_ref.set({
                    'device_id': self.device_id,
                    'last_heartbeat': time.time(),
                    'timestamp': firestore.SERVER_TIMESTAMP
                }, merge=True)

                # Wait before next heartbeat
                time.sleep(self.heartbeat_interval)

            except Exception as e:
                print(f"[Heartbeat] Error: {e}")
                time.sleep(5)  # Wait before retry

    def stop(self):
        """Stop heartbeat thread"""
        self.running = False

        # Clear session from Firebase
        try:
            self.db.collection('active_sessions').document(self.uid).delete()
            print("[Heartbeat] ✓ Session cleared from Firebase")
        except Exception as e:
            print(f"[Heartbeat] Error clearing session: {e}")


class HeartbeatManager:
    """Manages heartbeat for active session"""

    _instance = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.worker = None
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'worker'):
            self.worker = None

    def start_heartbeat(self, uid: str, device_id: str, db) -> HeartbeatWorker:
        """Start sending heartbeats"""
        if self.worker and self.worker.isRunning():
            self.stop_heartbeat()

        self.worker = HeartbeatWorker(uid, device_id, db)
        self.worker.start()
        print(f"[Heartbeat] ✓ Started for device {device_id[:8]}...")

        return self.worker

    def stop_heartbeat(self):
        """Stop heartbeat"""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None
            print("[Heartbeat] ✓ Stopped")

    def check_existing_session(self, uid: str, device_id: str, db) -> tuple[bool, str]:
        """
        Check if user has active session on another device
        Returns: (has_conflict, device_id)
        """
        try:
            session_ref = db.collection('active_sessions').document(uid)
            session_doc = session_ref.get()

            if session_doc.exists:
                session_data = session_doc.to_dict()
                active_device = session_data.get('device_id')
                last_heartbeat = session_data.get('last_heartbeat', 0)

                # Check if another device is active (heartbeat within 30 seconds)
                if active_device != device_id and (time.time() - last_heartbeat < 30):
                    return True, active_device

            return False, None

        except Exception as e:
            print(f"[Heartbeat] Error checking session: {e}")
            return False, None


# Singleton instance - CRITICAL: Must be at module level
heartbeat_manager = HeartbeatManager()