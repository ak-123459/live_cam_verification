import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QMessageBox, QFrame, QApplication, QSizePolicy, QGroupBox, QSplitter, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap


class PersonFaceForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Person Face")
        self.setMinimumSize(960, 600)
        self.setStyleSheet("padding: 10px; border: 1px solid #ddd; border-radius: 5px;")
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title_label = QLabel("Add New Person Face")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        main_layout.addWidget(title_label)

        # ==== Camera/Image Feed (small at top) ====
        feed_frame = QFrame()
        feed_frame.setFrameShape(QFrame.Box)
        feed_frame.setStyleSheet("background-color: black;")
        feed_layout = QVBoxLayout(feed_frame)
        feed_layout.setContentsMargins(10, 10, 10, 10)
        feed_layout.setSpacing(8)

        self.image_display_label = QLabel("Camera Feed / Uploaded Image")
        self.image_display_label.setAlignment(Qt.AlignCenter)
        self.image_display_label.setMinimumSize(360, 200)
        self.image_display_label.setMaximumHeight(220)
        self.image_display_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.image_display_label.setStyleSheet("border: 1px dashed #aaa; color: #777;")
        feed_layout.addWidget(self.image_display_label)

        btn_row = QHBoxLayout()
        self.capture_button = QPushButton("Capture Face")
        self.upload_button = QPushButton("Upload Image")
        for b in (self.capture_button, self.upload_button):
            b.setMinimumHeight(34)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_row.addStretch(1)
        btn_row.addWidget(self.capture_button)
        btn_row.addWidget(self.upload_button)
        btn_row.addStretch(1)
        feed_layout.addLayout(btn_row)

        feed_frame.setMaximumHeight(280)
        feed_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(feed_frame, stretch=0)

        # ==== Splitter for Details (left) and Preview (right) ====
        splitter = QSplitter(Qt.Horizontal)

        # ==== Details Section inside ScrollArea ====
        details_inner = QFrame()
        details_layout = QVBoxLayout(details_inner)
        details_layout.setContentsMargins(10, 10, 20, 10)
        details_layout.setSpacing(12)

        # Wrap in scroll area
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setWidget(details_inner)
        details_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Style scroll area + scrollbar
        details_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;              /* smaller scrollbar */
                background: transparent;
                margin: 0 2px 0 0;       /* push it to the right */
            }
            QScrollBar::handle:vertical {
                background: #888;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #555;
            }
        """)

        splitter.addWidget(details_scroll)

        # Base form (common fields)
        base_form_widget = QFrame()
        base_form = QFormLayout(base_form_widget)
        base_form.setContentsMargins(0, 0, 0, 0)
        base_form.setSpacing(10)
        base_form.setLabelAlignment(Qt.AlignRight)

        # Create styled labels
        name_label = QLabel("Name:")
        name_label.setStyleSheet("background-color: black; padding: 4px; border-radius: 4px;")

        person_label = QLabel("Person ID:")
        person_label.setStyleSheet("background-color: black; padding: 4px; border-radius: 4px;")

        group_label = QLabel("Group/Role:")
        group_label.setStyleSheet("background-color: black; padding: 4px; border-radius: 4px;")

        # Inputs
        self.name_input = self._mk_line()
        self.person_id_input = self._mk_line()

        self.group_dropdown = QComboBox()
        self.group_dropdown.addItems(["Admin", "Employee", "Student"])
        self.group_dropdown.setMinimumWidth(260)
        self.group_dropdown.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Add to form with styled labels
        base_form.addRow(name_label, self.name_input)
        base_form.addRow(person_label, self.person_id_input)
        base_form.addRow(group_label, self.group_dropdown)

        details_layout.addWidget(base_form_widget)

        # --- Student section ---
        self.student_section = QGroupBox("Student Details")
        student_layout = QFormLayout(self.student_section)
        student_layout.setContentsMargins(15, 12, 15, 12)
        student_layout.setSpacing(12)
        student_layout.setLabelAlignment(Qt.AlignRight)

        self.roll_no_input = self._mk_line()
        self.department_input = self._mk_line()
        self.semester_input = self._mk_line()

        student_layout.addRow("Roll No./Enrollment No:", self.roll_no_input)
        student_layout.addRow("Department/Class:", self.department_input)
        student_layout.addRow("Semester/Section:", self.semester_input)

        # --- Parent section (only visible when Student selected) ---
        self.parent_section = QGroupBox("Parent Details")
        parent_layout = QFormLayout(self.parent_section)
        parent_layout.setContentsMargins(15, 12, 15, 12)
        parent_layout.setSpacing(12)
        parent_layout.setLabelAlignment(Qt.AlignRight)

        self.parent_name_input = self._mk_line()
        self.parent_email_input = self._mk_line()
        self.parent_mobile_input = self._mk_line()
        self.parent_relation_input = self._mk_line()

        parent_layout.addRow("Parent Name:", self.parent_name_input)
        parent_layout.addRow("Parent Email:", self.parent_email_input)
        parent_layout.addRow("Parent Mobile:", self.parent_mobile_input)
        parent_layout.addRow("Relation:", self.parent_relation_input)

        details_layout.addWidget(self.student_section)
        details_layout.addWidget(self.parent_section)

        # --- Admin section ---
        self.admin_section = QGroupBox("Admin Details")
        admin_layout = QFormLayout(self.admin_section)
        self.admin_level_input = self._mk_line()
        admin_layout.addRow("Admin Level:", self.admin_level_input)
        details_layout.addWidget(self.admin_section)

        # --- Employee section ---
        self.employee_section = QGroupBox("Employee Details")
        employee_layout = QFormLayout(self.employee_section)

        self.emp_email_input = self._mk_line()
        self.emp_department_input = self._mk_line()
        self.emp_gender_dropdown = QComboBox()
        self.emp_gender_dropdown.addItems(["Male", "Female", "Other"])

        employee_layout.addRow("Email Address:", self.emp_email_input)
        employee_layout.addRow("Department:", self.emp_department_input)
        employee_layout.addRow("Gender:", self.emp_gender_dropdown)

        details_layout.addWidget(self.employee_section)

        # ==== Preview + Actions ====
        preview_frame = QFrame()
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(50, 12, 5, 12)
        preview_layout.setSpacing(20)

        # --- Replaced preview_label with a scrollable grid ---
        self.preview_grid_container = QWidget()
        self.preview_grid_layout = QGridLayout(self.preview_grid_container)
        self.preview_grid_layout.setSpacing(10)
        self.preview_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_image_count = 0

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setWidget(self.preview_grid_container)
        preview_scroll.setStyleSheet("border: 1px solid #ccc; background-color: #fafafa;")

        preview_layout.addWidget(preview_scroll)

        action_button_layout = QHBoxLayout()
        self.retake_button = QPushButton("Retake")
        self.save_button = QPushButton("Save Face")
        action_button_layout.addStretch(1)
        action_button_layout.addWidget(self.retake_button)
        action_button_layout.addWidget(self.save_button)
        preview_layout.addLayout(action_button_layout)

        splitter.addWidget(preview_frame)

        # Give more space to details (scrollable)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter, stretch=2)

        # Wiring
        self.save_button.clicked.connect(self.save_data)
        self.group_dropdown.currentTextChanged.connect(self.toggle_sections)
        self.capture_button.clicked.connect(self.add_preview_image)
        self.upload_button.clicked.connect(self.add_preview_image)
        self.retake_button.clicked.connect(self.clear_preview_images)

        # Initial state
        self.toggle_sections(self.group_dropdown.currentText())
        self.add_preview_image()  # Add a placeholder on start

    def _mk_line(self) -> QLineEdit:
        le = QLineEdit()
        le.setMinimumWidth(200)
        le.setMinimumHeight(34)
        return le

    def toggle_sections(self, role: str):
        is_student = role == "Student"
        self.student_section.setVisible(is_student)
        self.parent_section.setVisible(is_student)  # ✅ parent only if student
        self.admin_section.setVisible(role == "Admin")
        self.employee_section.setVisible(role == "Employee")

    def add_preview_image(self):
        """Adds a dummy image to the preview grid."""
        dummy_image = QLabel("Image " + str(self.preview_image_count + 1))
        dummy_image.setAlignment(Qt.AlignCenter)
        dummy_image.setFixedSize(120, 120)
        dummy_image.setStyleSheet("border: 1px dashed #aaa; background-color: #e0e0e0; color: #777; font-size: 10px;")

        # Calculate row and column
        row = self.preview_image_count // 3
        col = self.preview_image_count % 3

        self.preview_grid_layout.addWidget(dummy_image, row, col)
        self.preview_image_count += 1

    def clear_preview_images(self):
        """Clears all images from the preview grid."""
        while self.preview_grid_layout.count():
            item = self.preview_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.preview_image_count = 0
        self.add_preview_image()  # Add back the initial placeholder

    def save_data(self):
        name = self.name_input.text().strip()
        person_id = self.person_id_input.text().strip()
        group_role = self.group_dropdown.currentText()
        if name and person_id:
            QMessageBox.information(
                self, "Success",
                f"Person saved!\nName: {name}\nID: {person_id}\nRole: {group_role}"
            )
        else:
            QMessageBox.warning(self, "Error", "Please fill in Name and Person ID.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = PersonFaceForm()
    window.showMaximized()
    sys.exit(app.exec())
