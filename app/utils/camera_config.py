"""
Camera Configuration Manager
Handles saving, loading, and managing camera configurations

Save this file as: app/utils/camera_config.py
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class CameraConfigManager:
    """Manages camera configurations with persistence"""

    CONFIG_FILE = "camera_config.json"

    def __init__(self):
        self.config_path = self._get_config_path()
        self.cameras = []
        self.load_cameras()
        print(f"[CONFIG] Configuration file path: {self.config_path}")

    def _get_config_path(self):
        """Get the path to the configuration file"""
        # Save in the project root directory
        try:
            # Try to get the main app directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up to project root (assuming this is in app/utils/)
            project_root = os.path.dirname(os.path.dirname(current_dir))
            config_path = os.path.join(project_root, self.CONFIG_FILE)
        except:
            # Fallback to current directory
            config_path = self.CONFIG_FILE

        return config_path

    def load_cameras(self) -> List[Dict]:
        """Load camera configurations from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cameras = data.get('cameras', [])
                    print(f"[CONFIG] ✓ Loaded {len(self.cameras)} camera(s) from {self.config_path}")
                    for cam in self.cameras:
                        print(f"[CONFIG]   - {cam['name']} ({cam['camera_id']})")
                    return self.cameras
            else:
                print(f"[CONFIG] No existing configuration file found at {self.config_path}")
                print(f"[CONFIG] Will create new configuration file on first save")
                self.cameras = []
                return []
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to load cameras: {e}")
            import traceback
            traceback.print_exc()
            self.cameras = []
            return []

    def save_cameras(self) -> bool:
        """Save camera configurations to file"""
        try:
            data = {
                'cameras': self.cameras,
                'last_updated': datetime.now().isoformat()
            }

            # Create directory if it doesn't exist
            config_dir = os.path.dirname(self.config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            print(f"[CONFIG] ✓ Saved {len(self.cameras)} camera(s) to {self.config_path}")
            return True

        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save cameras: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_camera(self, camera_id: str, name: str, source: str, source_type: str) -> bool:
        """Add a new camera to configuration"""
        # Check if camera with this ID already exists
        if self.get_camera(camera_id):
            print(f"[CONFIG] Camera {camera_id} already exists")
            return False

        camera = {
            'camera_id': camera_id,
            'name': name,
            'source': source,
            'source_type': source_type,
            'enabled': True,
            'created_at': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat()
        }

        self.cameras.append(camera)
        self.save_cameras()
        print(f"[CONFIG] ✓ Added camera: {name} ({camera_id})")
        return True

    def remove_camera(self, camera_id: str) -> bool:
        """Remove a camera from configuration"""
        initial_count = len(self.cameras)
        self.cameras = [c for c in self.cameras if c['camera_id'] != camera_id]

        if len(self.cameras) < initial_count:
            self.save_cameras()
            print(f"[CONFIG] ✓ Removed camera: {camera_id}")
            return True

        print(f"[CONFIG] Camera {camera_id} not found")
        return False

    def get_camera(self, camera_id: str) -> Optional[Dict]:
        """Get camera configuration by ID"""
        for camera in self.cameras:
            if camera['camera_id'] == camera_id:
                return camera
        return None

    def get_all_cameras(self) -> List[Dict]:
        """Get all camera configurations"""
        return self.cameras.copy()

    def update_camera(self, camera_id: str, **kwargs) -> bool:
        """Update camera configuration"""
        for camera in self.cameras:
            if camera['camera_id'] == camera_id:
                camera.update(kwargs)
                camera['last_used'] = datetime.now().isoformat()
                self.save_cameras()
                print(f"[CONFIG] ✓ Updated camera: {camera_id}")
                return True

        print(f"[CONFIG] Camera {camera_id} not found for update")
        return False

    def toggle_camera(self, camera_id: str) -> bool:
        """Enable/disable a camera"""
        for camera in self.cameras:
            if camera['camera_id'] == camera_id:
                camera['enabled'] = not camera.get('enabled', True)
                self.save_cameras()
                print(f"[CONFIG] ✓ Toggled camera {camera_id}: enabled={camera['enabled']}")
                return camera['enabled']
        return False

    def get_enabled_cameras(self) -> List[Dict]:
        """Get only enabled cameras"""
        enabled = [c for c in self.cameras if c.get('enabled', True)]
        print(f"[CONFIG] Found {len(enabled)} enabled camera(s)")
        return enabled