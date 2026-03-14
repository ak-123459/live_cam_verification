"""
Login Page for Face Recognition Attendance System
WITH FIREBASE AUTHENTICATION
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QPainter, QPainterPath, QColor, QPixmap


class AuthWorker(QThread):
    """Background thread for authentication with device check"""
    finished = Signal(bool, str, object)

    def __init__(self, email, password, device_id):
        super().__init__()
        self.email = email
        self.password = password
        self.device_id = device_id

    def run(self):
        try:
            from app.auth.firebase_auth import firebase_auth

            # Use device check authentication
            success, message, user_data = firebase_auth.login_with_device_check(
                self.email,
                self.password,
                self.device_id
            )

            self.finished.emit(success, message, user_data)

        except Exception as e:
            self.finished.emit(False, f"Authentication error: {str(e)}", None)




class LoginPage(QWidget):
    """Modern login page with Firebase authentication"""

    login_successful = Signal(dict)  # Emits user_data on successful login

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth_worker = None
        self.progress_dialog = None
        self.setup_ui()

    def setup_ui(self):
        """Setup the login interface"""
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left side - Branding panel
        left_panel = self.create_branding_panel()
        main_layout.addWidget(left_panel, 1)

        # Right side - Login form
        right_panel = self.create_login_panel()
        main_layout.addWidget(right_panel, 1)

    def create_branding_panel(self):
        """Create the left branding panel"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #111111,
                    stop:1 #1a1a1a
                );
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(60, 60, 60, 60)

        # Logo
        logo_widget = self.create_large_logo()
        layout.addWidget(logo_widget, alignment=Qt.AlignCenter)

        layout.addSpacing(30)

        # Title
        title = QLabel("Aptal AI")
        title.setStyleSheet("""
            color: #ffffff;
            font-size: 48px;
            font-weight: bold;
            letter-spacing: 2px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Surveillance System")
        subtitle.setStyleSheet("""
            color: #ffc107;
            font-size: 24px;
            font-weight: 500;
            letter-spacing: 1px;
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Description
        desc = QLabel("Advanced Face Recognition\nAttendance Management")
        desc.setStyleSheet("""
            color: #94a3b8;
            font-size: 16px;
            line-height: 1.6;
        """)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        # Firebase badge
        firebase_label = QLabel("🔐 Secured with Firebase")
        firebase_label.setStyleSheet("color: #64748b; font-size: 12px;")
        firebase_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(firebase_label)

        layout.addSpacing(5)

        # Version info
        version = QLabel("v1.0.0")
        version.setStyleSheet("color: #64748b; font-size: 12px;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

        return panel

    def create_login_panel(self):
        """Create the right login panel"""
        panel = QWidget()
        panel.setStyleSheet("background-color: #1a1a1a;")

        # Center container
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)

        # Login form container
        form_container = QWidget()
        form_container.setFixedWidth(400)
        form_layout = QVBoxLayout(form_container)
        form_layout.setSpacing(20)

        # Welcome text
        welcome = QLabel("Welcome Back")
        welcome.setStyleSheet("""
            color: #ffffff;
            font-size: 32px;
            font-weight: bold;
        """)
        form_layout.addWidget(welcome)

        subtext = QLabel("Please enter your credentials to continue")
        subtext.setStyleSheet("""
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 20px;
        """)
        form_layout.addWidget(subtext)

        form_layout.addSpacing(20)

        # Email field
        email_label = QLabel("Email Address")
        email_label.setStyleSheet("color: #ffffff; font-weight: 500;")
        form_layout.addWidget(email_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter your email")
        self.email_input.setStyleSheet("""
            QLineEdit {
                background-color: #222222;
                color: #fff;
                border: 2px solid #333333;
                padding: 14px;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #ffc107;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        form_layout.addWidget(self.email_input)

        # Password field
        password_label = QLabel("Password")
        password_label.setStyleSheet("color: #ffffff; font-weight: 500;")
        form_layout.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #222222;
                color: #fff;
                border: 2px solid #333333;
                padding: 14px;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #ffc107;
            }
            QLineEdit::placeholder {
                color: #64748b;
            }
        """)
        self.password_input.returnPressed.connect(self.handle_login)
        form_layout.addWidget(self.password_input)

        # Remember me & Forgot password row
        options_layout = QHBoxLayout()

        self.remember_checkbox = QCheckBox("Remember me")
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                color: #94a3b8;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #333333;
                background-color: #222222;
            }
            QCheckBox::indicator:checked {
                background-color: #ffc107;
                border: 2px solid #ffc107;
            }
        """)
        options_layout.addWidget(self.remember_checkbox)

        options_layout.addStretch()

        forgot_btn = QPushButton("Forgot Password?")
        forgot_btn.setStyleSheet("""
            QPushButton {
                color: #ffc107;
                background: transparent;
                border: none;
                font-size: 13px;
                text-decoration: underline;
                padding: 0;
            }
            QPushButton:hover {
                color: #ffca2c;
            }
        """)
        forgot_btn.setCursor(Qt.PointingHandCursor)
        forgot_btn.clicked.connect(self.show_forgot_password)
        options_layout.addWidget(forgot_btn)

        form_layout.addLayout(options_layout)

        form_layout.addSpacing(10)

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #000000;
                border: none;
                padding: 16px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #ffca2c;
            }
            QPushButton:pressed {
                background-color: #e6ac00;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self.handle_login)
        form_layout.addWidget(self.login_btn)

        # Divider
        form_layout.addSpacing(20)

        divider_layout = QHBoxLayout()
        line1 = QLabel()
        line1.setFixedHeight(1)
        line1.setStyleSheet("background-color: #333333;")
        divider_layout.addWidget(line1)

        or_text = QLabel("OR")
        or_text.setStyleSheet("color: #64748b; padding: 0 10px;")
        divider_layout.addWidget(or_text)

        line2 = QLabel()
        line2.setFixedHeight(1)
        line2.setStyleSheet("background-color: #333333;")
        divider_layout.addWidget(line2)

        form_layout.addLayout(divider_layout)

        form_layout.addSpacing(20)

        # Create account button
        create_btn = QPushButton("📧  Create New Account")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #222222;
                color: #ffffff;
                border: 2px solid #333333;
                padding: 14px;
                border-radius: 8px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton:hover {
                border: 2px solid #ffc107;
                background-color: #2a2a2a;
            }
        """)
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.clicked.connect(self.show_create_account)
        form_layout.addWidget(create_btn)

        center_layout.addWidget(form_container)

        # Main panel layout
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(center_widget)

        return panel

    def create_large_logo(self):
        """Create large hexagonal logo for branding panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        size = 120
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Outer hexagon
        outer = QPainterPath()
        outer.moveTo(size / 2, 8)
        outer.lineTo(size - 12, size * 0.27)
        outer.lineTo(size - 12, size * 0.73)
        outer.lineTo(size / 2, size - 8)
        outer.lineTo(12, size * 0.73)
        outer.lineTo(12, size * 0.27)
        outer.closeSubpath()

        painter.fillPath(outer, QColor("#ffc107"))

        # Inner hexagon for depth
        inner = QPainterPath()
        inner.moveTo(size / 2, 18)
        inner.lineTo(size - 22, size * 0.32)
        inner.lineTo(size - 22, size * 0.68)
        inner.lineTo(size / 2, size - 18)
        inner.lineTo(22, size * 0.68)
        inner.lineTo(22, size * 0.32)
        inner.closeSubpath()

        painter.fillPath(inner, QColor(0, 0, 0, 35))

        # "A" letter
        s = size / 100.0
        a_path = QPainterPath()

        a_path.moveTo(50 * s, 24 * s)
        a_path.lineTo(72 * s, 78 * s)
        a_path.lineTo(60 * s, 78 * s)
        a_path.lineTo(56 * s, 66 * s)
        a_path.lineTo(44 * s, 66 * s)
        a_path.lineTo(40 * s, 78 * s)
        a_path.lineTo(28 * s, 78 * s)
        a_path.closeSubpath()

        # A hole
        hole = QPainterPath()
        hole.moveTo(46 * s, 58 * s)
        hole.lineTo(54 * s, 58 * s)
        hole.lineTo(50 * s, 44 * s)
        hole.closeSubpath()

        a_path.setFillRule(Qt.WindingFill)
        a_path.addPath(hole)

        painter.fillPath(a_path, QColor("#111111"))
        painter.end()

        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        return widget

    # REPLACE handle_login method in LoginPage class:
    def handle_login(self):
        """Handle login with device check"""
        email = self.email_input.text().strip()
        password = self.password_input.text()

        # Validation
        if not email or not password:
            QMessageBox.warning(self, "Login Failed", "Please enter both email and password.")
            return

        if '@' not in email:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return

        # Disable UI
        self.login_btn.setEnabled(False)
        self.email_input.setEnabled(False)
        self.password_input.setEnabled(False)

        # Show progress
        self.progress_dialog = QProgressDialog("Authenticating...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Please Wait")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.show()

        # Get device ID and start authentication
        from app.auth.session_manager import session_manager
        device_id = session_manager.get_device_id()

        self.auth_worker = AuthWorker(email, password, device_id)
        self.auth_worker.finished.connect(self.on_auth_complete)
        self.auth_worker.start()


    # ADD this method to LoginPage class:
    def on_auth_complete(self, success, message, user_data):
        """Handle authentication completion"""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        self.login_btn.setEnabled(True)
        self.email_input.setEnabled(True)
        self.password_input.setEnabled(True)

        if success:
            # Save session if "Remember me" is checked
            if self.remember_checkbox.isChecked():
                from app.auth.session_manager import session_manager
                session_manager.save_session(user_data)

            print(f"[Login] ✓ User authenticated: {user_data.get('email')}")
            self.login_successful.emit(user_data)
        else:
            # Show specific error for multiple device login
            if "another device" in message.lower():
                QMessageBox.critical(
                    self,
                    "Multiple Device Login Not Permitted",
                    "Your account is already active on another device.\n\n"
                    "Please logout from the other device first, or wait 30 seconds."
                )
            else:
                QMessageBox.critical(self, "Login Failed", message)

            self.password_input.clear()
            self.password_input.setFocus()

    def on_auth_complete(self, success, message, user_data):
        """Handle authentication completion"""
        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # Re-enable UI
        self.login_btn.setEnabled(True)
        self.email_input.setEnabled(True)
        self.password_input.setEnabled(True)

        if success:
            # Successful login
            print(f"[Login] ✓ User authenticated: {user_data.get('email')}")
            self.login_successful.emit(user_data)
        else:
            # Failed login
            QMessageBox.critical(
                self,
                "Login Failed",
                message
            )
            self.password_input.clear()
            self.password_input.setFocus()

    def show_forgot_password(self):
        """Show forgot password dialog"""
        from PySide6.QtWidgets import QInputDialog

        email, ok = QInputDialog.getText(
            self,
            "Password Reset",
            "Enter your email address:",
            QLineEdit.Normal
        )

        if ok and email:
            try:
                from app.auth.firebase_auth import firebase_auth
                success, message = firebase_auth.reset_password(email)

                if success:
                    QMessageBox.information(
                        self,
                        "Password Reset",
                        "Password reset link has been sent to your email."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Password Reset Failed",
                        message
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to send reset link: {str(e)}"
                )

    def show_create_account(self):
        """Show create account dialog"""
        QMessageBox.information(
            self,
            "Create Account",
            "Account creation feature coming soon.\n"
            "Please contact your system administrator."
        )