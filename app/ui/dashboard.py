import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFrame,
    QSizePolicy, QFileDialog, QSpacerItem, QScrollArea, QDialog,
    QComboBox, QDialogButtonBox, QStackedWidget
)
from PySide6.QtGui import QPixmap, QIcon, QFont, QImage, QPainter, QPainterPath, QColor
from PySide6.QtCore import Qt, QSize, QTimer, QRectF
from components import add_new_person_form




# The Qt Style Sheet (QSS) for the entire application, mimicking the dark theme.
QSS = """
    * {
        font-family: "Segoe UI", "Inter", sans-serif;
    }

    QMainWindow, QWidget#mainContent {
        background-color: #1a1a1a;
        color: #fff;
    }

    QWidget#sidebar {
        background-color: #111111;
        border-radius: 0 12px 12px 0;
        padding: 16px;
    }

    QLabel#logoName, QLabel#logoNameSmall {
        color: #fff;
        font-weight: bold;
    }
    QLabel#logoName { font-size: 20px; }
    QLabel#logoNameSmall { font-size: 14px; }

    QPushButton {
        background-color: #222222;
        color: #94a3b8;
        border: none;
        padding: 10px;
        text-align: left;
        border-radius: 12px;
        font-weight: 500;
        font-size: 14px;
        min-height: 36px;
    }
    QPushButton:hover {
        background-color: #333333;
        color: #fff;
    }
    QPushButton#selectedNav {
        background-color: #ffc107;
        color: #111111;
    }

    QLineEdit {
        background-color: #222222;
        color: #fff;
        border: none;
        padding: 12px 12px 12px 12px;
        border-radius: 20px;
        font-size: 14px;
    }
    QLineEdit::placeholder {
        color: #64748b;
    }

    QWidget#card {
        background-color: #222222;
        border: 1px solid #333333;
        border-radius: 16px;
        padding: 16px;
    }

    QComboBox {
        background-color: #222222;
        color: #fff;
        border: none;
        padding: 12px;
        border-radius: 20px;
    }

    QLabel#cardTitle {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 8px;
    }

    QFrame#videoFeed {
        min-height: 192px;
        border-radius: 12px;
        margin-top: 16px;
        background-color: #000;
    }
    QFrame#videoFeed1 {
        border: 2px dashed #ffc107;
    }
    QFrame#videoFeed2 {
    }
    QFrame#videoFeed3 {
    }

    QLabel#videoText {
        font-size: 20px;
        font-weight: bold;
        color: #fff;
        background: transparent;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
    }

    QLabel#tag {
        background-color: rgba(255, 255, 255, 0.2);
        color: #fff;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: 500;
    }

    QLabel#userIdLabel {
        background-color: #222222;
        padding: 16px;
        border-radius: 8px;
        color: #64748b;
    }
    QLabel#userIdValue {
        color: #ffc107;
        font-family: monospace;
    }

    /* New "Add Application" button style */
    #addApplicationButton {
        background-color: #ffc107;
        color: #111;
        border: none;
        padding: 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 16px;
        min-height: 36px;
    }
    #addApplicationButton:hover {
        background-color: #ffca2c;
    }

    /* Style for the QDialog */
    QDialog {
        background-color: #1a1a1a;
        color: #fff;
        border-radius: 16px;
        padding: 20px;
    }

    QDialog #browseButton {
        min-height: 32px;
        padding: 6px 12px;
    }

    QLabel {
        color: #fff;
    }

    QDialogButtonBox QPushButton {
        background-color: #ffc107;
        color: #111;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: bold;
        min-height: 32px;
    }
"""


class AddCardDialog(QDialog):
    """
    A custom dialog for adding a new application card.
    It collects all the necessary information in a single, modern UI.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Camera")
        self.setGeometry(200, 200, 400, 300)
        self.setModal(True)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter Application Title")
        self.layout.addWidget(QLabel("Application Title:"))
        self.layout.addWidget(self.title_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Enter comma-separated tags (e.g., Car,Person)")
        self.layout.addWidget(QLabel("Tags:"))
        self.layout.addWidget(self.tags_input)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Image File", "Cam", "RTSP"])
        self.layout.addWidget(QLabel("Camera Source:"))
        self.layout.addWidget(self.source_combo)

        self.image_layout = QHBoxLayout()
        self.image_path_input = QLineEdit()
        self.image_path_input.setPlaceholderText("Select an image file")
        self.image_path_input.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setObjectName("browseButton")
        self.image_layout.addWidget(self.image_path_input)
        self.image_layout.addWidget(self.browse_button)
        self.layout.addLayout(self.image_layout)

        self.source_combo.currentIndexChanged.connect(self.update_image_input_state)
        self.browse_button.clicked.connect(self.select_image_file)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.image_path = ""
        self.update_image_input_state(0)  # Initialize with first item

    def update_image_input_state(self, index):
        is_file_source = self.source_combo.itemText(index) == "Image File"
        self.image_path_input.setEnabled(is_file_source)
        self.browse_button.setEnabled(is_file_source)

    def select_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.image_path_input.setText(file_path)
            self.image_path = file_path

    @staticmethod
    def get_card_data(parent=None):
        dialog = AddCardDialog(parent)
        result = dialog.exec()
        if result == QDialog.Accepted:
            return (
                dialog.title_input.text().strip(),
                [tag.strip() for tag in dialog.tags_input.text().split(",") if tag.strip()],
                dialog.source_combo.currentText(),
                dialog.image_path if dialog.source_combo.currentText() == "Image File" else None
            )
        return None, None, None, None





class ApplicationsPage(QWidget):
    """
    A widget representing the 'Applications' page content.
    It contains the grid of application cards and the 'Add New' button.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("applicationsPage")
        self.card_count = 0
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        applications_label = QLabel("Explore Applications")
        applications_label.setObjectName("cardTitle")
        applications_label.setStyleSheet("font-size: 24px;")
        main_layout.addWidget(applications_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.cards_container = QWidget()
        self.cards_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

        self.cards_grid_layout = QGridLayout(self.cards_container)
        self.cards_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_grid_layout.setSpacing(8)
        self.cards_grid_layout.setColumnStretch(0, 1)
        self.cards_grid_layout.setColumnStretch(1, 1)
        self.cards_grid_layout.setColumnStretch(2, 1)

        # Initial cards
        card1 = self.create_application_card("Object Recognition", "assets/images/camera_1.jpg", ["Person", "Car"],
                                             "videoFeed1")
        card2 = self.create_application_card("Facial Recognition", "assets/images/cctv2.jpg", ["Face"], "videoFeed2")
        card3 = self.create_application_card("Semantic Understanding", "assets/images/cctv3.jpg", ["Building", "Road"],
                                             "videoFeed3")
        self.cards_grid_layout.addWidget(card1, 0, 0)
        self.cards_grid_layout.addWidget(card2, 0, 1)
        self.cards_grid_layout.addWidget(card3, 0, 2)
        self.card_count = 3

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area)

        self.add_button = QPushButton("Add New Application")
        self.add_button.setObjectName("addApplicationButton")
        self.add_button.clicked.connect(self.show_add_card_dialog)
        main_layout.addWidget(self.add_button)

        # This is the new line to fix the layout. It adds a stretchable spacer
        # that will consume all remaining vertical space, pushing the button up.
        main_layout.addStretch()

    def create_application_card(self, title, image_path, tags, video_feed_id):
        card = QWidget()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card.setMinimumSize(250, 300)
        card.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        card_layout.addWidget(title_label)

        video_feed = QFrame()
        video_feed.setObjectName(video_feed_id)
        video_feed.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        video_feed_layout = QVBoxLayout(video_feed)
        video_feed_layout.setContentsMargins(0, 0, 0, 0)
        video_feed_layout.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(image_path) if image_path and os.path.exists(image_path) else QPixmap()

        if pixmap.isNull():
            placeholder_image = QImage(320, 320, QImage.Format_ARGB32)
            placeholder_image.fill(QColor("#cccccc"))
            pixmap = QPixmap.fromImage(placeholder_image)

        pixmap_label = QLabel()
        pixmap = pixmap.scaled(180, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pixmap_label.setPixmap(pixmap)
        pixmap_label.setFixedSize(180, 200)
        pixmap_label.setAlignment(Qt.AlignCenter)
        pixmap_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pixmap_label.setScaledContents(True)

        video_feed_layout.addWidget(pixmap_label)
        card_layout.addWidget(video_feed)

        tags_widget = QWidget()
        tags_layout = QHBoxLayout(tags_widget)
        tags_layout.setAlignment(Qt.AlignTop | Qt.AlignRight)
        tags_layout.setContentsMargins(8, 8, 8, 8)
        tags_layout.setSpacing(8)

        for tag in tags:
            tag_label = QLabel(tag)
            tag_label.setObjectName("tag")
            tags_layout.addWidget(tag_label)

        tags_widget.setParent(video_feed)
        return card

    def show_add_card_dialog(self):
        title, tags, source, image_path = AddCardDialog.get_card_data(self)
        if not title or not title.strip():
            print("Title cannot be empty. Card not added.")
            return

        if title and tags:
            if source == "Cam":
                tags.append("Live Cam")
            elif source == "RTSP":
                tags.append("RTSP")
            new_image_path = image_path if source == "Image File" else None

            row = self.card_count // 3
            col = self.card_count % 3

            new_card = self.create_application_card(title, new_image_path, tags, f"videoFeed{self.card_count + 1}")
            self.cards_grid_layout.addWidget(new_card, row, col)
            self.card_count += 1
            QTimer.singleShot(0, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        v_scroll_bar = self.scroll_area.verticalScrollBar()
        v_scroll_bar.setValue(v_scroll_bar.maximum())

#
# class DataSetsPage(QWidget):
#     """
#     A placeholder widget for the 'Data Sets' page.
#     """
#
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         layout = QVBoxLayout(self)
#         label = QLabel("This is the Data Sets Page.")
#         label.setAlignment(Qt.AlignCenter)
#         label.setStyleSheet("font-size: 24px; color: #64748b;")
#         layout.addWidget(label)





class MainWindow(QMainWindow):
    """
    The main window of the application, handling the sidebar and page navigation.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Perceptual AI Dashboard")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(main_widget)

        # === Sidebar Setup ===
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(8)

        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setAlignment(Qt.AlignLeft)
        logo_layout.setContentsMargins(0, 0, 0, 0)

        pixmap = QPixmap(QSize(40, 40))
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.moveTo(20, 0);
        path.lineTo(37.32, 10);
        path.lineTo(37.32, 30)
        path.lineTo(20, 40);
        path.lineTo(2.68, 30);
        path.lineTo(2.68, 10)
        path.closeSubpath()
        painter.fillPath(path, QColor("#ffc107"))
        font = QFont("sans-serif", 16);
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#2c2c2c"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "AI")
        painter.end()

        logo_label = QLabel()
        logo_label.setPixmap(pixmap)
        logo_text_widget = QWidget()
        logo_text_layout = QVBoxLayout(logo_text_widget)
        logo_text_layout.setContentsMargins(0, 0, 0, 0)
        logo_text_layout.setSpacing(0)
        perceptual_label = QLabel("Perceptual");
        perceptual_label.setObjectName("logoNameSmall")
        ai_label = QLabel("AI");
        ai_label.setObjectName("logoName")
        logo_text_layout.addWidget(perceptual_label)
        logo_text_layout.addWidget(ai_label)
        logo_layout.addWidget(logo_label)
        logo_layout.addSpacing(8)
        logo_layout.addWidget(logo_text_widget)
        sidebar_layout.addWidget(logo_widget)
        sidebar_layout.addSpacing(24)

        # === Navigation Buttons ===
        nav_items = [
            ("Applications", "applications"),
            ("Add New Face", "add-face"),
            ("Algorithms", "algorithms"),
            ("Models", "models"),
            ("API Documentation", "api-docs")
        ]

        self.nav_buttons = {}

        for name, obj_name in nav_items:
            button = QPushButton(name)
            button.setObjectName(obj_name)
            button.setFixedSize(QSize(218, 48))
            self.nav_buttons[obj_name] = button

            # The robust fix: using a lambda that correctly handles the signal
            # and passes the desired string to the navigation function.
            button.clicked.connect(lambda checked=False, name=obj_name: self.navigate_to_page(name))

            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch()

        user_id_label = QLabel(
            "User ID: <span style='font-family: monospace; color: #ffc107;'>ANONYMOUS_USER_12345</span>")
        user_id_label.setObjectName("userIdLabel")
        user_id_label.setWordWrap(True)
        sidebar_layout.addWidget(user_id_label)

        main_layout.addWidget(self.sidebar)

        # === Main Content Area with QStackedWidget ===
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("mainContent")

        self.applications_page = ApplicationsPage()
        self.add_person_page = add_new_person_form.PersonFaceForm()

        self.stacked_widget.addWidget(self.applications_page)  # Index 0
        self.stacked_widget.addWidget(self.add_person_page)  # Index 1

        main_layout.addWidget(self.stacked_widget)

        # Set the initial page and update nav button style
        self.navigate_to_page("applications")

    def navigate_to_page(self, page_name):
        """
        Switches to the specified page in the QStackedWidget and updates the nav button style.
        """
        # A simple placeholder for other pages not yet implemented
        if page_name == "applications":
            self.stacked_widget.setCurrentWidget(self.applications_page)
        elif page_name == "add-face":
            self.stacked_widget.setCurrentWidget(self.add_person_page)
        else:
            print(f"Navigation to '{page_name}' is not yet implemented.")
            return

        self.update_nav_selection(page_name)

    def update_nav_selection(self, selected_page_name):
        """
        Updates the stylesheet of the navigation buttons to highlight the selected one.
        """
        for name, button in self.nav_buttons.items():
            if name == selected_page_name:
                button.setObjectName("selectedNav")
            else:
                button.setObjectName(name)
            # This is essential to force the stylesheet to be re-evaluated
            button.style().unpolish(button)
            button.style().polish(button)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
