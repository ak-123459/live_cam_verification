from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt
import sys
import os



class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setStyleSheet(self.get_stylesheet())
        self.setMinimumSize(800, 600)
        self.init_ui()
        self.show()

    def init_ui(self):
        # ========== Top Bar with Logo and Exit ==========
        logo_label = QLabel()
        pixmap = QPixmap("assets/images/login.png")
        if pixmap.isNull():
            logo_label.setText("LOGO")
        else:
            pixmap = pixmap.scaled(100, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        logo_label.setObjectName("Logo")

        # close_button = QPushButton("✕")
        # close_button.setFixedSize(40, 40)
        # # close_button.clicked.connect(self.confirm_exit)
        # close_button.setObjectName("CloseButton")

        top_bar = QHBoxLayout()
        top_bar.addWidget(logo_label)
        top_bar.addStretch()
        # top_bar.addWidget(close_button)

        # ========== Login Form ==========
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: transparent;")
        form_frame.setGraphicsEffect(self.get_shadow_effect())

        title = QLabel("Sign In")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setObjectName("InputField")
        self.username_input.setFixedWidth(280)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Password")
        self.password_input.setObjectName("InputField")
        self.password_input.setFixedWidth(280)

        login_button = QPushButton("LOGIN")
        login_button.setObjectName("LoginButton")
        login_button.setFixedWidth(280)
        login_button.clicked.connect(self.handle_login)
        login_button.setDefault(True)

        form_layout = QVBoxLayout()
        form_layout.addWidget(title)
        form_layout.addSpacing(20)
        form_layout.addWidget(self.username_input, alignment=Qt.AlignCenter)
        form_layout.addWidget(self.password_input, alignment=Qt.AlignCenter)
        form_layout.addSpacing(10)
        form_layout.addWidget(login_button, alignment=Qt.AlignCenter)

        form_frame.setLayout(form_layout)

        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(form_frame)
        center_layout.addStretch()

        # ========== Main Layout ==========
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_bar)
        main_layout.addStretch()
        main_layout.addLayout(center_layout)
        main_layout.addStretch()

        self.setLayout(main_layout)
        self.username_input.setFocus()
        self.password_input.returnPressed.connect(login_button.click)

    def get_shadow_effect(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 8)
        return shadow

    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if username == "admin" and password == "1234":
            QMessageBox.information(self, "Success", "Login successful!")
            self.close()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

    # def confirm_exit(self):
    #     reply = QMessageBox.question(
    #         self, "Exit", "Are you sure you want to exit?",
    #         QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
    #     )
    #     if reply == QMessageBox.Yes:
    #         self.close()

    # def keyPressEvent(self, event):
    #     if event.key() == Qt.Key_Escape:
    #         self.confirm_exit()

    def get_stylesheet(self):
        return """
            QWidget {
                background-color: #fffff;
                font-family: 'Segoe UI', Arial;
                font-size: 14px;
                color: #6336636;
            }

            QFrame {
                background-color: white;
            }

            #Title {
                font-size: 24px;
                font-weight: bold;
                color: #333;
            }

            QLineEdit#InputField {
                padding: 10px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.95);
                color: #000;
                margin-bottom: 10px;
            }

            QLineEdit#InputField:focus {
                border: 1px solid #2979ff;
            }

                      QPushButton#LoginButton {
                background-color: transparent;
                border: 2px solid #2979ff;
                color: #2979ff;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
                transition: all 0.3s ease;
            }
            
            
            
            QPushButton#LoginButton:hover {
                background-color: #fbc02d;  /* Yellow background on hover */
                color: #1f1f1f;             /* Dark text for contrast */}

            
            QPushButton#LoginButton:pressed {
                background-color: #1565c0;
                border-color: #1565c0;
            }

    
            QLabel#Logo {
                padding-left: 20px;
            }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)

    if not os.path.exists("assets/images/login.png"):
        print("⚠️ 'login.png' not found. Logo will not be shown.")
    window = LoginWindow()
    sys.exit(app.exec())
