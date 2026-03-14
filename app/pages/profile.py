"""
Profile Page - Display and manage user profile information
Fetches data from Firebase Authentication and session file
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QLineEdit,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont
from datetime import datetime
import os
import json



class ProfilePage(QWidget):
    """User profile page with Firebase data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user = None
        self.setup_ui()
        self.load_user_from_session()
        self.load_profile_data()


    def setup_ui(self):
        """Setup profile page UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Profile")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")

        self.last_updated_label = QLabel("Loading...")
        self.last_updated_label.setStyleSheet("color: #64748b; font-size: 14px;")

        header_layout.addWidget(title)
        header_layout.addWidget(self.last_updated_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Left column - Profile card
        self.profile_card = self.create_profile_card()
        content_layout.addWidget(self.profile_card, 1)

        # Right column - Account details
        self.details_card = self.create_details_card()
        content_layout.addWidget(self.details_card, 2)

        layout.addLayout(content_layout)

        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh Profile")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #ffc107;
                border: 1px solid #ffc107;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ffc107;
                color: #111;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_profile)

        self.edit_btn = QPushButton("✏️ Edit Profile")
        self.edit_btn.setObjectName("addApplicationButton")
        self.edit_btn.clicked.connect(self.edit_profile)

        actions_layout.addWidget(self.refresh_btn)
        actions_layout.addWidget(self.edit_btn)
        layout.addLayout(actions_layout)

        layout.addStretch()

    def create_profile_card(self):
        """Create left profile card with avatar and basic info"""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(16)

        # Avatar placeholder
        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setAlignment(Qt.AlignCenter)
        avatar_layout.setSpacing(12)

        self.avatar_label = QLabel("👤")
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet("""
            background-color: #333333;
            border: 3px solid #ffc107;
            border-radius: 75px;
            font-size: 72px;
            min-width: 150px;
            max-width: 150px;
            min-height: 150px;
            max-height: 150px;
        """)

        self.change_photo_btn = QPushButton("Change Photo")
        self.change_photo_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #94a3b8;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #444444;
                color: #fff;
            }
        """)
        self.change_photo_btn.clicked.connect(self.change_photo)

        avatar_layout.addWidget(self.avatar_label)
        avatar_layout.addWidget(self.change_photo_btn)
        layout.addWidget(avatar_container)

        # User name
        self.name_label = QLabel("Loading...")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #fff;
            padding: 8px;
        """)
        layout.addWidget(self.name_label)

        # Email
        self.email_label = QLabel("email@example.com")
        self.email_label.setAlignment(Qt.AlignCenter)
        self.email_label.setStyleSheet("""
            font-size: 14px;
            color: #94a3b8;
            padding-bottom: 16px;
        """)
        layout.addWidget(self.email_label)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #333333; max-height: 1px;")
        layout.addWidget(divider)

        # Status badges
        badges_layout = QVBoxLayout()
        badges_layout.setSpacing(8)

        self.role_badge = self.create_info_row("Role", "user", "#3b82f6")
        self.status_badge = self.create_info_row("Status", "Active", "#22c55e")

        badges_layout.addWidget(self.role_badge)
        badges_layout.addWidget(self.status_badge)
        layout.addLayout(badges_layout)

        return card

    def create_details_card(self):
        """Create right details card with account information"""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setSpacing(20)

        # Section: Account Information
        account_title = QLabel("Account Information")
        account_title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #fff;
            padding-bottom: 8px;
            border-bottom: 2px solid #ffc107;
        """)
        layout.addWidget(account_title)

        # Account details grid
        account_grid = QGridLayout()
        account_grid.setSpacing(16)
        account_grid.setColumnStretch(1, 1)

        self.uid_field = self.create_detail_field("User ID", "Loading...")
        self.created_field = self.create_detail_field("Account Created", "Loading...")
        self.last_login_field = self.create_detail_field("Last Login", "Loading...")
        self.email_verified_field = self.create_detail_field("Email Verified", "Loading...")

        account_grid.addWidget(self.uid_field, 0, 0, 1, 2)
        account_grid.addWidget(self.created_field, 1, 0)
        account_grid.addWidget(self.last_login_field, 1, 1)
        account_grid.addWidget(self.email_verified_field, 2, 0, 1, 2)

        layout.addLayout(account_grid)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #333333; max-height: 1px;")
        layout.addWidget(divider)

        # Section: Security
        security_title = QLabel("Security Settings")
        security_title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #fff;
            padding-bottom: 8px;
            border-bottom: 2px solid #ffc107;
        """)
        layout.addWidget(security_title)

        security_layout = QVBoxLayout()
        security_layout.setSpacing(12)



        layout.addLayout(security_layout)

        layout.addStretch()

        return card

    def create_info_row(self, label, value, color="#ffc107"):
        """Create a small info row with colored indicator"""
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        label_widget = QLabel(label + ":")
        label_widget.setStyleSheet("color: #94a3b8; font-size: 13px;")

        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"""
            color: {color};
            font-size: 13px;
            font-weight: bold;
            background-color: {color}22;
            padding: 4px 12px;
            border-radius: 12px;
        """)

        container_layout.addWidget(label_widget)
        container_layout.addStretch()
        container_layout.addWidget(value_widget)

        return container

    def create_detail_field(self, label, value):
        """Create a detail field with label and value"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("""
            color: #64748b;
            font-size: 12px;
            font-weight: 500;
        """)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("""
            color: #fff;
            font-size: 14px;
            font-weight: 500;
            padding: 8px 12px;
            background-color: #333333;
            border-radius: 6px;
        """)
        value_widget.setWordWrap(True)

        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        # Store reference for updating
        container.value_label = value_widget

        return container

    def load_user_from_session(self):
        """Load user data from session file"""
        try:
            # Try to load from session manager
            from app.auth.session_manager import session_manager
            saved_session = session_manager.get_saved_session()

            if saved_session:
                self.current_user = saved_session
                print(f"[PROFILE] ✓ Loaded user from session: {saved_session.get('email')}")
                return True

            # Fallback: Try to read session file directly
            session_file = os.path.join(os.path.expanduser('~'), '.aptalai_session.json')

            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    self.current_user = json.load(f)
                    print(f"[PROFILE] ✓ Loaded user from file: {self.current_user.get('email')}")
                    return True

            print("[PROFILE] ⚠ No session found")
            self.current_user = {
                'uid': 'unknown',
                'email': 'No session',
                'display_name': 'Guest User',
                'role': 'guest',
                'is_active': False
            }
            return False

        except Exception as e:
            print(f"[PROFILE ERROR] Failed to load session: {e}")
            self.current_user = {
                'uid': 'error',
                'email': 'Error loading session',
                'display_name': 'Error',
                'role': 'unknown',
                'is_active': False
            }
            return False

    def load_profile_data(self):
        """Load user profile data from current_user"""
        try:
            if not self.current_user:
                print("[PROFILE] No user data available")
                return

            print(f"[PROFILE] Loading profile for user: {self.current_user.get('uid')}")

            # Basic info
            display_name = self.current_user.get('display_name', 'User')
            email = self.current_user.get('email', 'No email')
            uid = self.current_user.get('uid', 'Unknown')
            role = self.current_user.get('role', 'user')
            is_active = self.current_user.get('is_active', True)

            # Update name and email
            self.name_label.setText(display_name)
            self.email_label.setText(email)

            # Update badges
            self.role_badge.findChild(QLabel, "", Qt.FindChildrenRecursively).setText(role.title())
            self.status_badge.findChild(QLabel, "", Qt.FindChildrenRecursively).setText(
                "Active" if is_active else "Inactive"
            )

            # Update account details
            self.uid_field.value_label.setText(uid)

            # Format dates
            created_at = self.current_user.get('created_at', 'Unknown')
            if created_at and created_at != 'Unknown':
                try:
                    # Assuming created_at is a timestamp
                    if isinstance(created_at, (int, float)):
                        created_at = datetime.fromtimestamp(created_at).strftime("%B %d, %Y at %I:%M %p")
                    elif hasattr(created_at, 'strftime'):
                        created_at = created_at.strftime("%B %d, %Y at %I:%M %p")
                except:
                    pass
            self.created_field.value_label.setText(str(created_at))

            last_login = self.current_user.get('last_login', 'Unknown')
            if last_login and last_login != 'Unknown':
                try:
                    if isinstance(last_login, (int, float)):
                        last_login = datetime.fromtimestamp(last_login).strftime("%B %d, %Y at %I:%M %p")
                    elif hasattr(last_login, 'strftime'):
                        last_login = last_login.strftime("%B %d, %Y at %I:%M %p")
                except:
                    pass
            self.last_login_field.value_label.setText(str(last_login))

            # Email verification status
            email_verified = self.current_user.get('email_verified', False)
            verified_text = "✓ Verified" if email_verified else "✗ Not Verified"
            verified_color = "#22c55e" if email_verified else "#ef4444"
            self.email_verified_field.value_label.setText(verified_text)
            self.email_verified_field.value_label.setStyleSheet(f"""
                color: {verified_color};
                font-size: 14px;
                font-weight: bold;
                padding: 8px 12px;
                background-color: {verified_color}22;
                border-radius: 6px;
            """)

            # Update last updated label
            self.last_updated_label.setText(f"Last updated: {datetime.now().strftime('%I:%M %p')}")

            print("[PROFILE] ✓ Profile loaded successfully")

        except Exception as e:
            print(f"[PROFILE ERROR] Failed to load profile: {e}")
            import traceback
            traceback.print_exc()

            QMessageBox.warning(
                self,
                "Profile Load Error",
                f"Failed to load profile data:\n{str(e)}"
            )

    def refresh_profile(self):
        """Refresh profile data from session and Firebase"""
        print("[PROFILE] Refreshing profile data...")

        try:
            # First reload from session
            self.load_user_from_session()

            # Try to get fresh data from Firebase
            from app.auth.firebase_auth import firebase_auth

            if self.current_user and self.current_user.get('uid'):
                updated_user = firebase_auth.get_user_by_uid(self.current_user['uid'])

                if updated_user:
                    self.current_user = updated_user
                    self.load_profile_data()

                    QMessageBox.information(
                        self,
                        "Profile Refreshed",
                        "Your profile has been updated with the latest data."
                    )
                else:
                    # Just reload from session
                    self.load_profile_data()
                    QMessageBox.information(
                        self,
                        "Profile Refreshed",
                        "Profile reloaded from session."
                    )
            else:
                QMessageBox.warning(
                    self,
                    "No User Session",
                    "No active user session found."
                )

        except Exception as e:
            print(f"[PROFILE ERROR] Refresh failed: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to refresh profile:\n{str(e)}"
            )

    def edit_profile(self):
        """Edit profile information"""
        QMessageBox.information(
            self,
            "Coming Soon",
            "Profile editing functionality will be available soon."
        )

    def change_photo(self):
        """Change profile photo"""
        QMessageBox.information(
            self,
            "Coming Soon",
            "Photo upload functionality will be available soon."
        )

    def change_password(self):
        """Change user password"""
        QMessageBox.information(
            self,
            "Coming Soon",
            "Password change functionality will be available soon."
        )

    def setup_two_factor(self):
        """Setup two-factor authentication"""
        QMessageBox.information(
            self,
            "Coming Soon",
            "Two-factor authentication setup will be available soon."
        )