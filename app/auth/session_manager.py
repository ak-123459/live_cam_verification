"""
Session Manager for handling user authentication state
Manages login persistence and device session tracking
"""
import os
import json
import time
import uuid
from typing import Optional, Dict
from pathlib import Path


class SessionManager:
    """Manages user session and login state"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.session_file = Path('user_session.json')
        self.device_id = self._get_device_id()

    def _get_device_id(self) -> str:
        """Get or create unique device ID"""
        device_file = Path('device_id.txt')

        if device_file.exists():
            return device_file.read_text().strip()
        else:
            device_id = str(uuid.uuid4())
            device_file.write_text(device_id)
            return device_id

    def save_session(self, user_data: Dict):
        """Save user session to local file"""
        session_data = {
            'uid': user_data['uid'],
            'email': user_data['email'],
            'display_name': user_data.get('display_name'),
            'role': user_data.get('role', 'user'),
            'device_id': self.device_id,
            'last_login': time.time()
        }

        with open(self.session_file, 'w') as f:
            json.dump(session_data, f)

        print(f"[Session] ✓ Session saved for {user_data['email']}")

    def get_saved_session(self) -> Optional[Dict]:
        """Get saved session if exists"""
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            # Check if session is not too old (30 days)
            if time.time() - session_data.get('last_login', 0) > 30 * 24 * 60 * 60:
                print("[Session] Session expired (30 days)")
                self.clear_session()
                return None

            return session_data

        except Exception as e:
            print(f"[Session] Error reading session: {e}")
            return None

    def clear_session(self):
        """Clear saved session"""
        if self.session_file.exists():
            self.session_file.unlink()
            print("[Session] ✓ Session cleared")

    def get_device_id(self) -> str:
        """Get current device ID"""
        return self.device_id


# Singleton instance
session_manager = SessionManager()