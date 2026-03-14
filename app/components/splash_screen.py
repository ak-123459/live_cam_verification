"""
Splash Screen - Shows loading progress during app initialization
"""
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont


class SplashScreen(QSplashScreen):
    """Custom splash screen with progress bar"""

    def __init__(self):
        # Create a custom pixmap
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor("#1a1a1a"))

        super().__init__(pixmap, Qt.WindowStaysOnTopHint)

        # Setup UI elements
        self.setup_ui()

    def setup_ui(self):
        """Setup splash screen UI"""
        # Create a widget for layout
        widget = QWidget(self)
        widget.setGeometry(0, 0, 500, 300)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Title
        title = QLabel("AI Surveillance Monitoring \nsystem")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #ffc107;
                font-size: 28px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)

        layout.addStretch()

        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #222222;
                border: 2px solid #333333;
                border-radius: 10px;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #ffc107;
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.progress)

        # Version info
        version = QLabel("v1.0.0 | Powered by APTAL")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 10px;
            }
        """)
        layout.addWidget(version)

    def update_progress(self, value, message=""):
        """Update progress bar and message"""
        self.progress.setValue(value)
        if message:
            self.status_label.setText(message)
        self.repaint()  # Force immediate update

    def finish_loading(self, main_window):
        """Finish splash screen and show main window"""
        self.update_progress(100, "Ready!")
        QTimer.singleShot(500, lambda: self.finish(main_window))


def show_splash_with_progress():
    """
    Show splash screen and return it for progress updates
    """
    splash = SplashScreen()
    splash.show()
    return splash