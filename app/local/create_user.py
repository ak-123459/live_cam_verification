"""
Firebase User Registration UI using PySide6
(Fixed DPI scaling, fullscreen, readable UI)
"""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

# Import your Firebase auth manager
from app.auth.firebase_auth import firebase_auth



# ============================
# Worker Thread
# ============================
class SignupWorker(QThread):
    finished = Signal(bool, str, str)

    def __init__(self, email, password, display_name):
        super().__init__()
        self.email = email
        self.password = password
        self.display_name = display_name

    def run(self):
        try:
            success, message, uid = firebase_auth.create_user(
                email=self.email,
                password=self.password,
                display_name=self.display_name
            )
            self.finished.emit(success, message, uid or "")
        except Exception as e:
            self.finished.emit(False, str(e), "")


# ============================
# Main UI
# ============================
class FirebaseSignupUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Create Account - Firebase Auth")

        # ✅ Allow resize + fullscreen
        self.resize(520, 720)
        self.setMinimumSize(480, 650)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(50, 40, 50, 40)
        main_layout.setSpacing(18)

        # ============================
        # STYLESHEET
        # ============================
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f7fa;
            }

            QLabel#title {
                font-size: 30px;
                font-weight: bold;
                color: #2c3e50;
            }

            QLabel#subtitle {
                font-size: 15px;
                color: #7f8c8d;
            }

            QLabel#field_label {
                font-size: 14px;
                font-weight: 600;
                color: #34495e;
            }

            QLineEdit {
                min-height: 44px;
                padding: 10px 14px;
                border: 2px solid #dfe6e9;
                border-radius: 8px;
                font-size: 15px;
                background-color: white;
            }

            QLineEdit:focus {
                border-color: #5e72e4;
            }

            QPushButton#signup_btn {
                min-height: 48px;
                background-color: #5e72e4;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }

            QPushButton#signup_btn:hover {
                background-color: #4c63d2;
            }

            QPushButton#signup_btn:disabled {
                background-color: #b2bec3;
            }

            QPushButton#login_link {
                background-color: transparent;
                border: none;
                color: #5e72e4;
                font-size: 14px;
                text-decoration: underline;
            }
        """)

        # ============================
        # HEADER
        # ============================
        header = QVBoxLayout()
        header.setAlignment(Qt.AlignCenter)

        icon = QLabel("👤")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 52px;")
        header.addWidget(icon)

        title = QLabel("Create Account")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        header.addWidget(title)

        subtitle = QLabel("Sign up to get started")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        header.addWidget(subtitle)

        main_layout.addLayout(header)
        main_layout.addSpacing(10)

        # ============================
        # FORM
        # ============================
        self.add_field(main_layout, "Display Name (Optional)", "John Doe", attr="display")
        self.add_field(main_layout, "Email Address *", "you@example.com", attr="email")
        self.add_field(main_layout, "Password *", "••••••••", attr="password", password=True)
        self.add_field(main_layout, "Confirm Password *", "••••••••", attr="confirm", password=True)

        hint = QLabel("Password must be at least 6 characters")
        hint.setStyleSheet("font-size: 12px; color: #95a5a6;")
        main_layout.addWidget(hint)

        main_layout.addSpacing(10)

        # ============================
        # BUTTONS
        # ============================
        self.signup_btn = QPushButton("Create Account")
        self.signup_btn.setObjectName("signup_btn")
        self.signup_btn.clicked.connect(self.handle_signup)
        main_layout.addWidget(self.signup_btn)

        login_row = QHBoxLayout()
        login_row.setAlignment(Qt.AlignCenter)

        login_row.addWidget(QLabel("Already have an account?"))

        login_btn = QPushButton("Sign In")
        login_btn.setObjectName("login_link")
        login_btn.clicked.connect(self.go_to_login)
        login_row.addWidget(login_btn)

        main_layout.addLayout(login_row)
        main_layout.addStretch()

    # ============================
    # Helpers
    # ============================
    def add_field(self, layout, label_text, placeholder, attr, password=False):
        label = QLabel(label_text)
        label.setObjectName("field_label")
        layout.addWidget(label)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if password:
            field.setEchoMode(QLineEdit.Password)

        setattr(self, f"{attr}_input", field)
        layout.addWidget(field)

    # ============================
    # Logic
    # ============================
    def handle_signup(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        display = self.display_input.text().strip() or email.split("@")[0]

        if not email or not password:
            QMessageBox.warning(self, "Error", "Email and password are required")
            return

        if len(password) < 6:
            QMessageBox.warning(self, "Error", "Password too short")
            return

        if password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return

        self.signup_btn.setDisabled(True)
        self.signup_btn.setText("Creating Account...")

        self.worker = SignupWorker(email, password, display)
        self.worker.finished.connect(self.on_signup_done)
        self.worker.start()

    def on_signup_done(self, success, message, uid):
        self.signup_btn.setDisabled(False)
        self.signup_btn.setText("Create Account")

        if success:
            QMessageBox.information(self, "Success", f"{message}\nUID: {uid}")
            self.email_input.clear()
            self.password_input.clear()
            self.confirm_input.clear()
            self.display_input.clear()
        else:
            QMessageBox.critical(self, "Failed", message)

    def go_to_login(self):
        QMessageBox.information(self, "Info", "Login screen goes here")


# ============================
# APP ENTRY
# ============================
def main():
    # ✅ HIGH DPI FIX (CRITICAL)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ✅ Global font
    app.setFont(QFont("Segoe UI", 11))

    window = FirebaseSignupUI()
    window.showMaximized()   # or window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
