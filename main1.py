"""
Main Application Entry Point
Face Recognition Attendance System
"""


import sys
import os


os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;4000000|stimeout;4000000"
os.environ["OPENCV_VIDEOIO_PRIORITY_FFMPEG"] = "1"
os.environ["OPENCV_FFMPEG_READ_ATTEMPTS"]    = "3"


from PySide6.QtWidgets import ( QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QMessageBox)

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QColor, QPixmap

from app.pages.about import AboutPage
from app.pages.profile import ProfilePage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))



# Import configurations and managers
from app.db.database import (
    init_database, AttendanceManager, UserManager
)

from app.pages.registered_faces import UsersPage

# Import workers
from app.workers.face_registration import FaceRegistration

# Import pages
from app.pages.live_detection_page import LiveDetectionPage
from app.pages.registration_page import RegistrationPage
from app.pages.attendance_page import AttendancePage
from app.pages.registered_users.watchlist import WatchlistPage



#APP UI_STYLESHEET
APP_STYLESHEET = """
    * {
        font-family: "Segoe UI", "Inter", sans-serif;
    }

    QMainWindow, QWidget {
        background-color: #1a1a1a;
        color: #fff;
    }

    QWidget#sidebar {
        background-color: #111111;
        border-right: 1px solid #222222;
    }

    QPushButton {
        background-color: #222222;
        color: #94a3b8;
        border: none;
        padding: 12px 16px;
        text-align: left;
        border-radius: 8px;
        font-weight: 500;
        font-size: 14px;
        min-height: 44px;
    }

    QPushButton:hover {
        background-color: #333333;
        color: #fff;
    }

    QPushButton#selectedNav {
        background-color: #ffc107;
        color: #111111;
        font-weight: bold;
    }

    QLineEdit, QComboBox, QDateEdit {
        background-color: #222222;
        color: #fff;
        border: 1px solid #333333;
        padding: 10px;
        border-radius: 8px;
        font-size: 14px;
    }

    QLineEdit::placeholder {
        color: #64748b;
    }

    QWidget#card {
        background-color: #222222;
        border: 1px solid #333333;
        border-radius: 12px;
        padding: 16px;
    }

    QGroupBox {
        background-color: #222222;
        border: 1px solid #333333;
        border-radius: 12px;
        padding: 20px;
        margin-top: 10px;
        font-size: 16px;
        font-weight: bold;
        color: #fff;
    }

    /* UPDATED: Register Face Button - Yellow background, Black text */
    QPushButton#addApplicationButton {
        background-color: #ffc107;  /* Yellow background */
        color: #000000;             /* Black text */
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 14px;
        min-height: 44px;
    }

    QPushButton#addApplicationButton:hover {
        background-color: #ffca2c;  /* Lighter yellow on hover */
        color: #000000;             /* Keep black text */
    }

    QPushButton#addApplicationButton:disabled {
        background-color: #666666;  /* Gray when disabled */
        color: #999999;             /* Light gray text */
    }

    QProgressBar {
        background-color: #222222;
        border: 1px solid #333333;
        border-radius: 8px;
        text-align: center;
        color: #fff;
    }

    QProgressBar::chunk {
        background-color: #ffc107;
        border-radius: 7px;
    }
"""


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("APTAL AI - Surveillance Monitoring System")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize managers
        self.init_managers()

        # Setup UI
        self.setup_ui()

        # Navigate to default page
        self.navigate_to_page("live")

    def init_managers(self):
        """Initialize database and managers"""
        try:
            # Database paths
            self.faiss_index_path = 'faiss_db/face_index.faiss'
            self.faiss_metadata_path = 'faiss_db/face_index_ids.pkl'

            # Create directories
            os.makedirs('faiss_db', exist_ok=True)

            # Initialize database
            print("[INIT] Initializing database...")
            init_database()

            # Pre-initialize shared model (this speeds up everything)
            print("[INIT] Pre-loading InsightFace model...")
            from app.workers.model_manager import get_shared_model
            shared_model = get_shared_model()
            print("[INIT] ✓ Model loaded and cached")

            # Create managers (they will use the cached model)
            self.attendance_manager = AttendanceManager()
            self.user_manager = UserManager()
            self.face_registration = FaceRegistration(
                self.faiss_index_path,
                self.faiss_metadata_path,
                shared_model=shared_model  # Pass shared model
            )

            print("[INIT] ✓ All managers initialized successfully")

        except Exception as e:

            QMessageBox.critical(
                self, "Initialization Error",
                f"Failed to initialize application:\n{str(e)}"
            )
            sys.exit(1)

    def setup_ui(self):
        """Setup user interface"""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(main_widget)

        # Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # Content area with stacked pages
        self.stacked_widget = QStackedWidget()

        # Create ALL pages first
        self.live_page = LiveDetectionPage(
            self.attendance_manager,
            self.faiss_index_path,
            self.faiss_metadata_path
        )

        self.registration_page = RegistrationPage(
        )

        self.attendance_page = AttendancePage(
            self.attendance_manager,
            self.user_manager
        )

        self.users_page = UsersPage(
           face_registration= self.face_registration
        )

        self.watchlist_page = WatchlistPage()

        self.profile_page = ProfilePage()

        self.about_page = AboutPage()

        # Add ALL pages to stack in the correct order - DO THIS ONLY ONCE
        self.stacked_widget.addWidget(self.live_page)  # Index 0
        self.stacked_widget.addWidget(self.registration_page)  # Index 1
        self.stacked_widget.addWidget(self.attendance_page)  # Index 2
        self.stacked_widget.addWidget(self.users_page)  # Index 3
        self.stacked_widget.addWidget(self.watchlist_page)  # Index 4
        self.stacked_widget.addWidget(self.profile_page)  # Index 5
        self.stacked_widget.addWidget(self.about_page)  # Index 6

        main_layout.addWidget(self.stacked_widget)

    def create_sidebar(self):
        """Create navigation sidebar with logout"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        # Logo
        logo_widget = self.create_logo()
        layout.addWidget(logo_widget)
        layout.addSpacing(30)

        # Navigation buttons
        nav_items = [
            ("Live Detection", "live", "👁"),
            ("Register Face", "register", "➕"),
            ("Users", "users", "👥"),
            ("Attendance", "attendance", "📋"),
            ("Watchlist", "watchlist", "🚨"),
            ("Profile", "profile", "👤"),
            ("About", "about", "ℹ")
        ]

        self.nav_buttons = {}

        for name, obj_name, icon in nav_items:
            button = QPushButton(f"{icon}  {name}")
            button.setObjectName(obj_name)
            button.clicked.connect(
                lambda checked=False, page=obj_name: self.navigate_to_page(page)
            )
            self.nav_buttons[obj_name] = button
            layout.addWidget(button)

        layout.addStretch()

        # User info section (if logged in)
        if hasattr(self, 'current_user'):
            user_card = QWidget()
            user_card.setStyleSheet("""
                QWidget {
                    background-color: #222222;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
            user_layout = QVBoxLayout(user_card)
            user_layout.setSpacing(4)

            user_email = QLabel(self.current_user.get('email', 'User'))
            user_email.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500;")
            user_layout.addWidget(user_email)

            user_role = QLabel(f"Role: {self.current_user.get('role', 'user').title()}")
            user_role.setStyleSheet("color: #94a3b8; font-size: 11px;")
            user_layout.addWidget(user_role)

            layout.addWidget(user_card)
            layout.addSpacing(10)

        # Logout button
        logout_btn = QPushButton("🚪  Logout")
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #ff4444;
                border: 1px solid #ff4444;
                padding: 12px 16px;
                text-align: left;
                border-radius: 8px;
                font-weight: 500;
                font-size: 14px;
                min-height: 44px;
            }
            QPushButton:hover {
                background-color: #ff4444;
                color: #ffffff;
            }
        """)
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)

        layout.addSpacing(10)

        # Footer info
        info_label = QLabel("v1.0.0 | Aptal AI")
        info_label.setStyleSheet("color: #64748b; font-size: 12px;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        return sidebar

    def create_logo(self):

        """Create application logo with thick hexagonal A icon"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        size = 52
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # ---------- OUTER HEXAGON ----------
        outer = QPainterPath()
        outer.moveTo(size / 2, 4)
        outer.lineTo(size - 6, size * 0.27)
        outer.lineTo(size - 6, size * 0.73)
        outer.lineTo(size / 2, size - 4)
        outer.lineTo(6, size * 0.73)
        outer.lineTo(6, size * 0.27)
        outer.closeSubpath()

        painter.fillPath(outer, QColor("#ffc107"))

        # ---------- INNER HEXAGON (THICKNESS EFFECT) ----------
        inner = QPainterPath()
        inner.moveTo(size / 2, 10)
        inner.lineTo(size - 12, size * 0.32)
        inner.lineTo(size - 12, size * 0.68)
        inner.lineTo(size / 2, size - 10)
        inner.lineTo(12, size * 0.68)
        inner.lineTo(12, size * 0.32)
        inner.closeSubpath()

        painter.fillPath(inner, QColor(0, 0, 0, 35))  # subtle depth

        # ---------- EXTRA THICK "A" ICON (SVG MATCH) ----------
        a_path = QPainterPath()

        # Scale helpers (SVG was 100x100)
        s = size / 100.0

        # Main A body
        a_path.moveTo(50 * s, 24 * s)
        a_path.lineTo(72 * s, 78 * s)
        a_path.lineTo(60 * s, 78 * s)
        a_path.lineTo(56 * s, 66 * s)
        a_path.lineTo(44 * s, 66 * s)
        a_path.lineTo(40 * s, 78 * s)
        a_path.lineTo(28 * s, 78 * s)
        a_path.closeSubpath()

        # Inner triangle (A hole)
        hole = QPainterPath()
        hole.moveTo(46 * s, 58 * s)
        hole.lineTo(54 * s, 58 * s)
        hole.lineTo(50 * s, 44 * s)
        hole.closeSubpath()

        # Proper fill rule (CRITICAL)
        a_path.setFillRule(Qt.WindingFill)
        a_path.addPath(hole)

        painter.fillPath(a_path, QColor("#111111"))

        painter.end()

        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(size, size)

        # ---------- TEXT ----------
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        title1 = QLabel("Aptal AI")
        title1.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")

        title2 = QLabel("Surveillance System")
        title2.setStyleSheet("color: #94a3b8; font-size: 12px;")

        text_layout.addWidget(title1)
        text_layout.addWidget(title2)

        layout.addWidget(icon_label)
        layout.addSpacing(12)
        layout.addWidget(text_widget)

        return widget

    def navigate_to_page(self, page_name):
        """Navigate to specified page"""
        page_map = {
            "live": 0,
            "register": 1,
            "attendance": 2,
            "users": 3,  # ← ADD THIS LINE
            "watchlist": 4,  # ✅ ADD THIS LINE

            "profile": 5,
            "about": 6
        }

        page_index = page_map.get(page_name)

        if page_index is None:
            QMessageBox.information(
                self, "Coming Soon",
                f"The {page_name.title()} page is not yet implemented."
            )
            return

        current_index = self.stacked_widget.currentIndex()

        print(f"[NAV] Navigating from page {current_index} to {page_name} (index {page_index})")

        # ========== CLEANUP WHEN LEAVING PAGES ==========

        # Cleanup registration page when leaving
        if current_index == 1 and page_index != 1:  # Leaving registration
            print("[NAV] Cleaning up registration page...")
            if hasattr(self, 'registration_page'):
                self.registration_page.cleanup()

        # ========== RESET WHEN ENTERING REGISTRATION PAGE ==========

        if page_index == 1:  # Going TO Registration page (from anywhere)
            print("[NAV] 🔄 RESETTING Registration page for fresh start...")
            if hasattr(self, 'registration_page'):
                self.registration_page
            print("[NAV] ✓ Registration page reset complete")

        # In navigate_to_page(), add this:
        if page_index == 2:  # Going TO Attendance page
            print("[NAV] 🔄 REFRESHING Attendance page with latest data...")
            if hasattr(self, 'attendance_page'):
                self.attendance_page.load_attendance_data()
            print("[NAV] ✓ Attendance page refreshed")

         # ========== REFRESH WHEN ENTERING USERS PAGE ==========

        if page_index == 3:  # Going TO Users page (from anywhere)
            print("[NAV] 🔄 REFRESHING Users page with latest data...")
            if hasattr(self, 'users_page'):
                self.users_page.load_users()
            print("[NAV] ✓ Users page refreshed")


        # ✅ ADD THIS: REFRESH WHEN ENTERING WATCHLIST PAGE
        if page_index == 4:
            print("[NAV] 🔄 REFRESHING Watchlist page with latest data...")
            if hasattr(self, 'watchlist_page'):
                self.watchlist_page.load_watchlist()
            print("[NAV] ✓ Watchlist page refreshed")


        # Switch page
        self.stacked_widget.setCurrentIndex(page_index)

        # Update navigation buttons
        self.update_nav_selection(page_name)

        print(f"[NAV] ✓ Navigated to {page_name}")

    def update_nav_selection(self, selected_page):
        """Update navigation button styles"""
        for name, button in self.nav_buttons.items():
            if name == selected_page:
                button.setObjectName("selectedNav")
            else:
                button.setObjectName(name)

            # Force style update
            button.style().unpolish(button)
            button.style().polish(button)

    def closeEvent(self, event):
        """Handle application close"""
        # Cleanup camera workers
        if hasattr(self, 'live_page'):
            self.live_page.cleanup()

        if hasattr(self, 'registration_page'):
            self.registration_page.cleanup()

        event.accept()

    def start_heartbeat(self):
        """Start heartbeat for this session"""
        if not hasattr(self, 'current_user'):
            return

        from app.auth.session_manager import session_manager
        from app.auth.heartbeat_manager import heartbeat_manager
        from app.auth.firebase_auth import firebase_auth

        device_id = session_manager.get_device_id()

        self.heartbeat_worker = heartbeat_manager.start_heartbeat(
            self.current_user['uid'],
            device_id,
            firebase_auth.db
        )

        # Handle session conflicts
        self.heartbeat_worker.session_conflict.connect(self.on_session_conflict)

    def on_session_conflict(self, other_device_id):
        """Handle when session is taken over by another device"""
        QMessageBox.warning(
            self,
            "Session Ended",
            "Your account has been logged in from another device.\n"
            "This session will now close."
        )

        # Clear session and close
        from app.auth.session_manager import session_manager
        session_manager.clear_session()

        self.close()

    # Update the logout method in MainWindow class as well:
    def logout(self):
        """Logout current user"""
        if hasattr(self, 'current_user'):
            from app.auth.firebase_auth import firebase_auth
            from app.auth.session_manager import session_manager
            from app.auth.heartbeat_manager import heartbeat_manager

            # Stop heartbeat
            heartbeat_manager.stop_heartbeat()

            # Clear Firebase session
            firebase_auth.logout_device(self.current_user['uid'])

            # ✅ FIX: Clear local session to prevent auto-login
            session_manager.clear_session()

            print("[Logout] ✓ User logged out")

            # Show login page
            from app.pages.auth.login import LoginPage
            login_page = LoginPage()
            login_page.show()

            # ✅ FIX: Save session after successful login
            def on_login_success(user_data):
                session_manager.save_session(user_data)

                window = MainWindow()
                window.current_user = user_data
                window.start_heartbeat()
                window.show()
                login_page.close()

            login_page.login_successful.connect(on_login_success)

            self.close()


def main():
    """Application entry point with auto-login"""
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_STYLESHEET)

    # Show splash screen
    from app.components.splash_screen import show_splash_with_progress
    splash = show_splash_with_progress()

    splash.update_progress(10, "Initializing...")
    app.processEvents()

    # Create directories
    os.makedirs('faiss_db', exist_ok=True)
    os.makedirs('attendance_images', exist_ok=True)
    os.makedirs('registered_faces', exist_ok=True)

    splash.update_progress(20, "Initializing database...")
    app.processEvents()

    from app.db.database import init_database
    init_database()

    splash.update_progress(40, "Loading AI model...")
    app.processEvents()

    from app.workers.model_manager import get_shared_model
    get_shared_model()

    splash.update_progress(60, "Checking authentication...")
    app.processEvents()

    # Check for saved session
    from app.auth.session_manager import session_manager
    from app.auth.firebase_auth import firebase_auth

    saved_session = session_manager.get_saved_session()

    if saved_session:
        # Verify saved session is still valid
        splash.update_progress(70, "Verifying session...")
        app.processEvents()

        user_data = firebase_auth.get_user_by_uid(saved_session['uid'])

        if user_data and user_data.get('is_active', True):
            # ✅ FIX: Don't check for device conflicts during auto-login
            # The saved session means THIS device was already logged in

            splash.update_progress(90, "Auto-login successful...")
            app.processEvents()

            window = MainWindow()
            window.current_user = user_data
            window.start_heartbeat()

            splash.update_progress(100, "Ready!")
            app.processEvents()

            splash.finish_loading(window)
            window.show()
        else:
            # Session invalid, show login
            session_manager.clear_session()
            splash.close()

            from app.pages.auth.login import LoginPage
            login_page = LoginPage()
            login_page.show()

            # ✅ FIX: Save session after successful login
            def on_login_success(user_data):
                # Save session for auto-login next time
                session_manager.save_session(user_data)

                window = MainWindow()
                window.current_user = user_data
                window.start_heartbeat()
                window.show()
                login_page.close()

            login_page.login_successful.connect(on_login_success)
    else:
        # No saved session, show login
        splash.update_progress(100, "Ready!")
        app.processEvents()

        splash.close()

        from app.pages.auth.login import LoginPage
        login_page = LoginPage()
        login_page.show()

        # ✅ FIX: Save session after successful login
        def on_login_success(user_data):
            # Save session for auto-login next time
            session_manager.save_session(user_data)

            window = MainWindow()
            window.current_user = user_data
            window.start_heartbeat()
            window.show()
            login_page.close()

        login_page.login_successful.connect(on_login_success)

    sys.exit(app.exec())



# ADD these methods to MainWindow class:





def closeEvent(self, event):
    """Handle application close"""
    # Cleanup camera workers
    if hasattr(self, 'live_page'):
        self.live_page.cleanup()

    if hasattr(self, 'registration_page'):
        self.registration_page.cleanup()

    # Stop heartbeat
    if hasattr(self, 'heartbeat_worker'):
        from app.auth.heartbeat_manager import heartbeat_manager
        heartbeat_manager.stop_heartbeat()

    event.accept()


if __name__ == "__main__":
    main()