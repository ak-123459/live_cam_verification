"""
Firebase Authentication Manager
Handles user authentication with Firebase
"""
import os
import json
import firebase_admin
from firebase_admin import credentials, auth, firestore
from typing import Optional, Dict, Tuple
import time



class FirebaseAuthManager:
    """Manages Firebase authentication and user data"""

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern to ensure one Firebase instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize Firebase (only once)"""
        if not FirebaseAuthManager._initialized:
            self.initialize_firebase()
            FirebaseAuthManager._initialized = True

    def initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if already initialized
            firebase_admin.get_app()
            print("[Firebase] Already initialized")
            return
        except ValueError:
            pass

        try:
            # Path to your Firebase service account key
            cred_path = 'C:\\Users\\techma\Downloads\PAI_AATS\PAI_AATS\\app\\firebase\\aptal-ai-firebase-adminsdk-fbsvc-f430d19fa8.json'

            if not os.path.exists(cred_path):
                print(f"[Firebase] ERROR: {cred_path} not found!")
                print("[Firebase] Please download your Firebase service account key")
                raise FileNotFoundError(
                    "Firebase credentials file not found. "
                    "Please download from Firebase Console > Project Settings > Service Accounts"
                )

            # Initialize Firebase Admin
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

            # Initialize Firestore
            self.db = firestore.client()

            print("[Firebase] ✓ Successfully initialized")

        except Exception as e:
            print(f"[Firebase] Initialization error: {e}")
            raise

    def create_user(self, email: str, password: str, display_name: str = None) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new user in Firebase

        Returns:
            (success, message, uid)
        """
        try:
            # Create user in Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
                email_verified=False
            )

            # Store additional user data in Firestore
            user_data = {
                'uid': user.uid,
                'email': email,
                'display_name': display_name or email.split('@')[0],
                'created_at': firestore.SERVER_TIMESTAMP,
                'role': 'user',  # default role
                'is_active': True
            }

            self.db.collection('users').document(user.uid).set(user_data)

            print(f"[Firebase] ✓ User created: {email}")
            return True, "User created successfully", user.uid

        except auth.EmailAlreadyExistsError:
            return False, "Email already exists", None
        except Exception as e:
            print(f"[Firebase] Create user error: {e}")
            return False, f"Error: {str(e)}", None

    def verify_user(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Verify user credentials (using custom token approach)
        Note: Firebase Admin SDK doesn't directly verify passwords.
        For production, use Firebase Client SDK or REST API.

        Returns:
            (success, message, user_data)
        """
        try:
            # Get user by email
            user = auth.get_user_by_email(email)

            if not user:
                return False, "User not found", None

            # Get user data from Firestore
            user_doc = self.db.collection('users').document(user.uid).get()

            if not user_doc.exists:
                return False, "User data not found", None

            user_data = user_doc.to_dict()

            # Check if user is active
            if not user_data.get('is_active', True):
                return False, "Account is disabled", None

            # For demo purposes - in production, use Firebase Auth REST API
            # This is a simplified version
            print(f"[Firebase] ✓ User verified: {email}")

            return True, "Login successful", {
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name or user_data.get('display_name'),
                'role': user_data.get('role', 'user')
            }

        except auth.UserNotFoundError:
            return False, "Invalid email or password", None
        except Exception as e:
            print(f"[Firebase] Verify user error: {e}")
            return False, f"Error: {str(e)}", None

    def login_with_device_check(self, email: str, password: str, device_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Login with device session check
        Returns: (success, message, user_data)
        """
        try:
            # First verify credentials
            success, message, user_data = self.verify_user(email, password)

            if not success:
                return False, message, None

            uid = user_data['uid']

            # Check for existing active session
            session_ref = self.db.collection('active_sessions').document(uid)
            session_doc = session_ref.get()

            if session_doc.exists:
                session_data = session_doc.to_dict()
                active_device = session_data.get('device_id')
                last_heartbeat = session_data.get('last_heartbeat', 0)

                # Check if another device is active (heartbeat within 30 seconds)
                if active_device != device_id:
                    if time.time() - last_heartbeat < 30:
                        return False, "Already logged in on another device", None

            # Create new session
            session_ref.set({
                'device_id': device_id,
                'last_heartbeat': time.time(),
                'login_time': firestore.SERVER_TIMESTAMP,
                'email': email
            })

            print(f"[Firebase] ✓ Login successful with device check: {email}")
            return True, "Login successful", user_data

        except Exception as e:
            print(f"[Firebase] Login with device check error: {e}")
            return False, f"Error: {str(e)}", None

    def logout_device(self, uid: str) -> Tuple[bool, str]:
        """Logout and clear device session"""
        try:
            # Clear active session
            self.db.collection('active_sessions').document(uid).delete()
            print(f"[Firebase] ✓ Device session cleared for {uid}")
            return True, "Logged out successfully"

        except Exception as e:
            print(f"[Firebase] Logout error: {e}")
            return False, f"Error: {str(e)}"

    def authenticate_with_rest_api(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Authenticate user using Firebase REST API
        This properly verifies the password

        Requires: FIREBASE_API_KEY in environment or config
        """
        import requests

        try:
            # Get API key from environment or config
            api_key = os.getenv('FIREBASE_API_KEY')
            if not api_key:
                # Try to read from firebase_config.json
                try:
                    with open('firebase_config.json', 'r') as f:
                        config = json.load(f)
                        api_key = config.get('apiKey')
                except:
                    pass

            if not api_key:
                return False, "Firebase API key not configured", None

            # Firebase Auth REST API endpoint
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                result = response.json()
                user_id = result['localId']

                # Get user data from Firestore
                user_doc = self.db.collection('users').document(user_id).get()
                user_data = user_doc.to_dict() if user_doc.exists else {}

                return True, "Login successful", {
                    'uid': user_id,
                    'email': result['email'],
                    'display_name': result.get('displayName') or user_data.get('display_name'),
                    'token': result['idToken'],
                    'role': user_data.get('role', 'user')
                }
            else:
                error = response.json().get('error', {})
                message = error.get('message', 'Authentication failed')

                if 'INVALID_PASSWORD' in message or 'EMAIL_NOT_FOUND' in message:
                    return False, "Invalid email or password", None
                elif 'USER_DISABLED' in message:
                    return False, "Account has been disabled", None
                else:
                    return False, message, None

        except requests.RequestException as e:
            print(f"[Firebase] REST API error: {e}")
            return False, "Network error. Please check your connection.", None
        except Exception as e:
            print(f"[Firebase] Authentication error: {e}")
            return False, f"Error: {str(e)}", None

    def get_user_by_uid(self, uid: str) -> Optional[Dict]:
        """Get user data by UID"""
        try:
            user = auth.get_user(uid)
            user_doc = self.db.collection('users').document(uid).get()

            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_data['email'] = user.email
                user_data['display_name'] = user.display_name or user_data.get('display_name')
                return user_data

            return None

        except Exception as e:
            print(f"[Firebase] Get user error: {e}")
            return None

    def update_user_profile(self, uid: str, display_name: str = None, photo_url: str = None) -> Tuple[bool, str]:
        """Update user profile"""
        try:
            updates = {}
            if display_name:
                updates['display_name'] = display_name
            if photo_url:
                updates['photo_url'] = photo_url

            # Update Firebase Auth
            auth.update_user(uid, **updates)

            # Update Firestore
            self.db.collection('users').document(uid).update(updates)

            return True, "Profile updated successfully"

        except Exception as e:
            print(f"[Firebase] Update profile error: {e}")
            return False, f"Error: {str(e)}"

    def reset_password(self, email: str) -> Tuple[bool, str]:
        """Send password reset email"""
        try:
            # Generate password reset link
            link = auth.generate_password_reset_link(email)

            # In production, send this link via email
            print(f"[Firebase] Password reset link: {link}")

            return True, "Password reset link sent to your email"

        except auth.UserNotFoundError:
            return False, "Email not found"
        except Exception as e:
            print(f"[Firebase] Reset password error: {e}")
            return False, f"Error: {str(e)}"

    def delete_user(self, uid: str) -> Tuple[bool, str]:
        """Delete user account"""
        try:
            # Delete from Firebase Auth
            auth.delete_user(uid)

            # Delete from Firestore
            self.db.collection('users').document(uid).delete()

            return True, "User deleted successfully"

        except Exception as e:
            print(f"[Firebase] Delete user error: {e}")
            return False, f"Error: {str(e)}"

    def check_user_role(self, uid: str, required_role: str) -> bool:
        """Check if user has required role"""
        try:
            user_doc = self.db.collection('users').document(uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_role = user_data.get('role', 'user')

                # Role hierarchy: admin > manager > user
                role_levels = {'admin': 3, 'manager': 2, 'user': 1}

                return role_levels.get(user_role, 0) >= role_levels.get(required_role, 0)

            return False

        except Exception as e:
            print(f"[Firebase] Check role error: {e}")
            return False


# Singleton instance
firebase_auth = FirebaseAuthManager()