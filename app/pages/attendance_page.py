"""
Attendance Details Page - View, filter, update, and delete attendance records
Fetches data from the remote API instead of querying the local database directly.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QDateEdit, QLineEdit, QFrame, QMessageBox, QSizePolicy,
    QDialog, QFormLayout, QTimeEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, QDate, QTime, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QColor
from datetime import datetime, timedelta
import requests
import cv2
import os
# Import status constants
from app.db.database import DatabaseConfig, AttendanceStatus
from dotenv import load_dotenv, dotenv_values
from pathlib import Path
from app.config.api_config import _get_api_base, _get_timeout, _get_endpoint


_ENV_PATH = Path(".env")





# ─────────────────────────────────────────────────────────────────────────────
#  Background worker — GET /attendance so the UI never freezes
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceFetchWorker(QThread):
    """Calls GET /attendance in a background thread."""
    finished = Signal(list)   # emits list[dict]
    failed   = Signal(str)    # emits error message

    def __init__(self, start_date=None, end_date=None, user_id=None, parent=None):
        super().__init__(parent)
        self.start_date = start_date
        self.end_date   = end_date
        self.user_id    = user_id

    def run(self):
        try:
            params = {}
            if self.start_date:
                params["start_date"] = self.start_date
            if self.end_date:
                params["end_date"] = self.end_date
            if self.user_id:
                params["user_id"] = self.user_id

            resp = requests.get(
                f"{_get_api_base()}/attendance",
                params=params,
                timeout=_get_timeout(),
            )

            if resp.status_code == 200:
                data = resp.json()
                # API returns {"total": N, "records": [...]}
                records = data.get("records", data) if isinstance(data, dict) else data
                self.finished.emit(records)
            else:
                self.failed.emit(f"API error {resp.status_code}: {resp.text}")

        except requests.exceptions.ConnectionError:
            self.failed.emit(
                f"Cannot connect to API at {_get_api_base()}.\n"
                "Check that the server is running and API_HOST/API_PORT in .env are correct."
            )
        except requests.exceptions.Timeout:
            self.failed.emit(f"Request timed out after {_get_timeout()}s.")
        except Exception as e:
            self.failed.emit(f"Unexpected error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Status badge helpers
# ─────────────────────────────────────────────────────────────────────────────

STATUS_COLORS = {
    'P':  ('#1a7a3c', '#6ee99a'),
    'A':  ('#7a1a1a', '#f08080'),
    'L':  ('#7a5a1a', '#ffd080'),
    'LV': ('#1a4a7a', '#80c8f0'),
}

def _status_item(code: str) -> QTableWidgetItem:
    label   = AttendanceStatus.label(code)
    item    = QTableWidgetItem(f"{label}  ")
    item.setTextAlignment(Qt.AlignCenter)
    bg, fg  = STATUS_COLORS.get(code, ('#333', '#fff'))
    item.setBackground(QColor(bg))
    item.setForeground(QColor(fg))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


# ─────────────────────────────────────────────────────────────────────────────
#  Edit dialog  (unchanged — still writes directly to DB)
# ─────────────────────────────────────────────────────────────────────────────

class EditAttendanceDialog(QDialog):
    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(f"Edit Attendance — {record['name']}")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel  { color: #fff; font-size: 13px; }
            QLineEdit, QDateEdit, QTimeEdit, QComboBox {
                background-color: #2a2a2a; color: #fff;
                border: 1px solid #444; border-radius: 5px;
                padding: 6px 10px; min-height: 36px; font-size: 13px;
            }
            QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus {
                border: 1px solid #ffc107;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a; color: #fff;
                selection-background-color: #ffc107; selection-color: #111;
            }
            QDialogButtonBox QPushButton {
                min-width: 90px; min-height: 36px;
                border-radius: 5px; font-weight: bold; font-size: 13px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel(f"Editing record for  <b style='color:#ffc107'>{self.record['name']}</b>")
        header.setStyleSheet("color:#fff; font-size:15px;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        date_val = self.record.get('date', '')
        self.date_edit.setDate(
            QDate.fromString(str(date_val), "yyyy-MM-dd") if date_val else QDate.currentDate()
        )
        form.addRow("Date:", self.date_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm:ss")
        time_val = self.record.get('time', '00:00:00')
        self.time_edit.setTime(QTime.fromString(str(time_val), "HH:mm:ss"))
        form.addRow("Time:", self.time_edit)

        self.status_combo = QComboBox()
        for code, label in AttendanceStatus.LABELS.items():
            self.status_combo.addItem(f"{code} – {label}", code)
        current_status = self.record.get('status') or AttendanceStatus.PRESENT
        idx = self.status_combo.findData(current_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        form.addRow("Status:", self.status_combo)

        self.dept_edit = QLineEdit(self.record.get('department') or '')
        self.dept_edit.setPlaceholderText("e.g. Engineering")
        form.addRow("Department:", self.dept_edit)

        self.role_edit = QLineEdit(self.record.get('role') or '')
        self.role_edit.setPlaceholderText("e.g. Employee")
        form.addRow("Role:", self.role_edit)

        conf_score = self.record.get('confidence_score')
        conf_str   = f"{conf_score:.4f}" if conf_score else 'N/A'
        conf_label = QLabel(conf_str)
        conf_label.setStyleSheet("color: #94a3b8;")
        form.addRow("Confidence (read-only):", conf_label)

        layout.addLayout(form)

        btn_box    = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_btn   = btn_box.button(QDialogButtonBox.Save)
        cancel_btn = btn_box.button(QDialogButtonBox.Cancel)
        save_btn.setStyleSheet("background-color: #ffc107; color: #111;")
        cancel_btn.setStyleSheet("background-color: #444; color: #fff;")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_updated_values(self):
        return {
            'date':       self.date_edit.date().toString("yyyy-MM-dd"),
            'time':       self.time_edit.time().toString("HH:mm:ss"),
            'status':     self.status_combo.currentData(),
            'department': self.dept_edit.text().strip() or None,
            'role':       self.role_edit.text().strip() or 'Employee',
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Main page
# ─────────────────────────────────────────────────────────────────────────────

class AttendancePage(QWidget):
    COL_USER_ID    = 0
    COL_NAME       = 1
    COL_DATE       = 2
    COL_TIME       = 3
    COL_STATUS     = 4
    COL_DEPARTMENT = 5
    COL_ROLE       = 6
    COL_CONFIDENCE = 7
    COL_IMAGE      = 8
    COL_EDIT       = 9
    COL_DELETE     = 10

    HEADERS = [
        "User ID", "Name", "Date", "Time", "Status",
        "Department", "Role", "Confidence",
        "Image", "Edit", "Delete"
    ]

    def __init__(self, attendance_manager, user_manager, parent=None):
        super().__init__(parent)
        # Keep managers for edit/delete DB ops and user list
        self.attendance_manager = attendance_manager
        self.user_manager       = user_manager
        self.current_records    = []
        self._fetch_worker      = None

        self.setup_ui()
        self.load_attendance_data()

    # ─────────────────────────────────────────────────────────────
    #  UI construction
    # ─────────────────────────────────────────────────────────────

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ── Title row ─────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("Attendance Records")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")
        title_row.addWidget(title)
        title_row.addStretch()

        # API indicator
        self.api_label = QLabel(f"🌐 {_get_api_base()}/attendance")
        self.api_label.setStyleSheet("color: #64748b; font-size: 12px;")
        title_row.addWidget(self.api_label)
        layout.addLayout(title_row)

        # ── Filters ───────────────────────────────────────────────
        filters_frame = QFrame()
        filters_frame.setObjectName("card")
        filters_layout = QVBoxLayout(filters_frame)
        filters_layout.setSpacing(15)

        filter_title = QLabel("Filters")
        filter_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        filters_layout.addWidget(filter_title)

        controls_layout = QHBoxLayout()

        # User filter
        user_layout = QVBoxLayout()
        user_layout.addWidget(QLabel("User:"))
        self.user_combo = QComboBox()
        self.user_combo.setMinimumHeight(40)
        self.user_combo.addItem("All Users", None)
        user_layout.addWidget(self.user_combo)
        controls_layout.addLayout(user_layout)

        # Date filter
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("Select Date:"))
        self.select_date = QDateEdit()
        self.select_date.setCalendarPopup(True)
        self.select_date.setDate(QDate.currentDate())
        self.select_date.setMinimumHeight(40)
        date_layout.addWidget(self.select_date)
        controls_layout.addLayout(date_layout)

        # Status filter (client-side)
        status_layout = QVBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.setMinimumHeight(40)
        self.status_filter.addItem("All", None)
        for code, label in AttendanceStatus.LABELS.items():
            self.status_filter.addItem(f"{code} – {label}", code)
        status_layout.addWidget(self.status_filter)
        controls_layout.addLayout(status_layout)

        # Quick date buttons
        quick_layout = QVBoxLayout()
        quick_layout.addWidget(QLabel("Quick Select:"))
        quick_btn_layout = QHBoxLayout()
        today_btn = QPushButton("Today")
        today_btn.setMinimumHeight(40)
        today_btn.clicked.connect(lambda: self.select_date.setDate(QDate.currentDate()))
        quick_btn_layout.addWidget(today_btn)
        yesterday_btn = QPushButton("Yesterday")
        yesterday_btn.setMinimumHeight(40)
        yesterday_btn.clicked.connect(
            lambda: self.select_date.setDate(QDate.currentDate().addDays(-1))
        )
        quick_btn_layout.addWidget(yesterday_btn)
        quick_layout.addLayout(quick_btn_layout)
        controls_layout.addLayout(quick_layout)

        # Apply button
        apply_layout = QVBoxLayout()
        apply_layout.addWidget(QLabel(" "))
        self.search_btn = QPushButton("Apply Filters")
        self.search_btn.setObjectName("addApplicationButton")
        self.search_btn.setMinimumHeight(40)
        self.search_btn.clicked.connect(self.load_attendance_data)
        apply_layout.addWidget(self.search_btn)
        controls_layout.addLayout(apply_layout)

        # Export button
        export_layout = QVBoxLayout()
        export_layout.addWidget(QLabel(" "))
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setMinimumHeight(40)
        self.export_btn.clicked.connect(self.export_to_csv)
        export_layout.addWidget(self.export_btn)
        controls_layout.addLayout(export_layout)

        controls_layout.addStretch()
        filters_layout.addLayout(controls_layout)
        layout.addWidget(filters_frame)

        # ── Stats ─────────────────────────────────────────────────
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        self.total_label   = self._stat_card("Total Records", "0")
        self.present_label = self._stat_card("Present Today", "0")
        self.week_label    = self._stat_card("This Week",     "0")
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.present_label)
        stats_layout.addWidget(self.week_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # ── Loading indicator ─────────────────────────────────────
        self.loading_label = QLabel("⏳ Loading…")
        self.loading_label.setStyleSheet("color:#ffc107; font-size:14px;")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.hide()
        layout.addWidget(self.loading_label)

        # ── Table ─────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #222222; border: 1px solid #333333;
                border-radius: 8px; color: #fff; gridline-color: #333333;
            }
            QTableWidget::item          { padding: 8px; }
            QTableWidget::item:selected { background-color: #ffc107; color: #111; }
            QHeaderView::section {
                background-color: #2a2a2a; color: #fff;
                padding: 10px; border: none; font-weight: bold;
            }
        """)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        for col in (self.COL_IMAGE, self.COL_EDIT, self.COL_DELETE):
            hdr.setSectionResizeMode(col, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_IMAGE,  90)
        self.table.setColumnWidth(self.COL_EDIT,   70)
        self.table.setColumnWidth(self.COL_DELETE, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        self._load_user_combo()

    def _stat_card(self, title, value):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setMinimumHeight(80)
        card_layout = QVBoxLayout(frame)
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #ffc107;")
        value_label.setAlignment(Qt.AlignCenter)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; color: #94a3b8;")
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value_label)
        card_layout.addWidget(title_label)
        return frame

    def _load_user_combo(self):
        """Populate user dropdown from user_manager (local — list doesn't need API)."""
        users = self.user_manager.get_all_users()
        self.user_combo.clear()
        self.user_combo.addItem("All Users", None)
        for user in users:
            self.user_combo.addItem(
                f"{user['name']} ({user['user_id']})", user['user_id']
            )

    # ─────────────────────────────────────────────────────────────
    #  Fetch from API (non-blocking)
    # ─────────────────────────────────────────────────────────────

    def load_attendance_data(self):
        """Fire off a background API fetch with current filter values."""
        # Prevent stacking concurrent requests
        if self._fetch_worker and self._fetch_worker.isRunning():
            return

        selected_date = self.select_date.date().toString("yyyy-MM-dd")
        user_id       = self.user_combo.currentData()   # None = all users

        # Disable controls while loading
        self.search_btn.setEnabled(False)
        self.loading_label.show()
        self.api_label.setText(f"🌐 Fetching {_get_api_base()}/attendance …")

        self._fetch_worker = AttendanceFetchWorker(
            start_date=selected_date,
            end_date=selected_date,
            user_id=str(user_id) if user_id else None,
        )
        self._fetch_worker.finished.connect(self._on_fetch_done)
        self._fetch_worker.failed.connect(self._on_fetch_failed)
        self._fetch_worker.start()

    def _on_fetch_done(self, records: list):
        """Called in the main thread when the API response arrives."""
        self.search_btn.setEnabled(True)
        self.loading_label.hide()
        self.api_label.setText(f"🌐 {_get_api_base()}/attendance")

        # Client-side status filter
        status_filter = self.status_filter.currentData()
        if status_filter:
            records = [r for r in records if r.get('status') == status_filter]

        self.current_records = records
        self._populate_table(records)
        self._update_statistics(records)

    def _on_fetch_failed(self, error_msg: str):
        self.search_btn.setEnabled(True)
        self.loading_label.hide()
        self.api_label.setText(f"🌐 {_get_api_base()}/attendance  ❌")
        QMessageBox.critical(self, "Failed to Load Attendance", error_msg)

    # ─────────────────────────────────────────────────────────────
    #  Populate table
    # ─────────────────────────────────────────────────────────────

    def _populate_table(self, records: list):
        self.table.setRowCount(len(records))

        for row, record in enumerate(records):
            self.table.setRowHeight(row, 75)

            self.table.setItem(row, self.COL_USER_ID,
                               QTableWidgetItem(str(record.get('user_id', ''))))
            self.table.setItem(row, self.COL_NAME,
                               QTableWidgetItem(str(record.get('name', ''))))

            date_val = record.get('date', '')
            self.table.setItem(row, self.COL_DATE, QTableWidgetItem(str(date_val)))
            self.table.setItem(row, self.COL_TIME,
                               QTableWidgetItem(str(record.get('time', ''))))

            status_code = record.get('status') or AttendanceStatus.PRESENT
            self.table.setItem(row, self.COL_STATUS, _status_item(status_code))

            self.table.setItem(row, self.COL_DEPARTMENT,
                               QTableWidgetItem(record.get('department') or 'N/A'))
            self.table.setItem(row, self.COL_ROLE,
                               QTableWidgetItem(record.get('role') or 'Employee'))

            conf = record.get('confidence_score')
            self.table.setItem(row, self.COL_CONFIDENCE,
                               QTableWidgetItem(f"{conf:.2%}" if conf else 'N/A'))

            # ── Image button ──────────────────────────────────────
            img_container = QWidget()
            img_container.setStyleSheet("background-color: transparent;")
            img_layout = QHBoxLayout(img_container)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.setAlignment(Qt.AlignCenter)
            img_btn = QPushButton("View")
            img_btn.setFixedSize(70, 35)
            img_btn.setStyleSheet("""
                QPushButton {
                    background-color: #304FFE; color: #fff;
                    border: none; border-radius: 5px; font-weight: bold;
                }
                QPushButton:hover    { background-color: #5C6BC0; }
                QPushButton:disabled { background-color: #555; color: #888; }
            """)
            img_path = record.get('image_path')
            if img_path and os.path.exists(img_path):
                img_btn.clicked.connect(lambda checked, r=record: self._show_image(r))
            else:
                img_btn.setEnabled(False)
                img_btn.setText("N/A")
            img_layout.addWidget(img_btn)
            self.table.setCellWidget(row, self.COL_IMAGE, img_container)

            # ── Edit / Delete buttons ─────────────────────────────
            self.table.setCellWidget(row, self.COL_EDIT,
                self._cell_btn("Edit", "#28a745", "#218838",
                               lambda checked, r=record: self._edit_record(r)))
            self.table.setCellWidget(row, self.COL_DELETE,
                self._cell_btn("Delete", "#dc3545", "#c82333",
                               lambda checked, r=record: self._delete_record(r)))

    def _cell_btn(self, text, color, hover, callback):
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        lay = QHBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setAlignment(Qt.AlignCenter)
        btn = QPushButton(text)
        btn.setFixedSize(60, 32)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: #fff;
                border: none; border-radius: 5px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """)
        btn.clicked.connect(callback)
        lay.addWidget(btn)
        return container

    # ─────────────────────────────────────────────────────────────
    #  Statistics  (derived from fetched records + two extra API calls)
    # ─────────────────────────────────────────────────────────────

    def _update_statistics(self, records: list):
        # Total = count of what's currently displayed
        total = len(records)
        self.total_label.findChildren(QLabel)[0].setText(str(total))

        today_str  = datetime.now().date().isoformat()
        week_start = (
            datetime.now().date() - timedelta(days=datetime.now().date().weekday())
        ).isoformat()

        # Today count — quick synchronous call (stats, not a big payload)
        try:
            r = requests.get(
                f"{_get_api_base()}/attendance",
                params={"start_date": today_str, "end_date": today_str},
                timeout=_get_timeout(),
            )
            today_count = r.json().get("total", 0) if r.ok else "?"
        except Exception:
            today_count = "?"

        # Week count
        try:
            r = requests.get(
                f"{_get_api_base()}/attendance",
                params={"start_date": week_start, "end_date": today_str},
                timeout=_get_timeout(),
            )
            week_count = r.json().get("total", 0) if r.ok else "?"
        except Exception:
            week_count = "?"

        self.present_label.findChildren(QLabel)[0].setText(str(today_count))
        self.week_label.findChildren(QLabel)[0].setText(str(week_count))

    # ─────────────────────────────────────────────────────────────
    #  Edit record  (still writes to DB directly — no edit API yet)
    # ─────────────────────────────────────────────────────────────

    def _edit_record(self, record):
        dialog = EditAttendanceDialog(record, self)
        if dialog.exec() != QDialog.Accepted:
            return

        updated = dialog.get_updated_values()
        conn = DatabaseConfig.get_connection()
        if not conn:
            QMessageBox.critical(self, "Error", "Could not connect to the database.")
            return

        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE attendance SET date=%s, time=%s, status=%s WHERE id=%s",
                (updated['date'], updated['time'], updated['status'], record['id'])
            )
            cursor.execute(
                "UPDATE users SET department=%s, role=%s, updated_at=%s WHERE user_id=%s",
                (updated['department'], updated['role'],
                 datetime.now().isoformat(), record['user_id'])
            )
            conn.commit()
            cursor.close()
            conn.close()

            QMessageBox.information(
                self, "Updated",
                f"Record for <b>{record['name']}</b> updated successfully."
            )
            self.load_attendance_data()   # re-fetch from API to show fresh data

        except Exception as e:
            QMessageBox.critical(self, "Update Failed", f"Could not update record:\n{e}")
            import traceback; traceback.print_exc()

    # ─────────────────────────────────────────────────────────────
    #  Delete record
    # ─────────────────────────────────────────────────────────────

    def _delete_record(self, record):
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete attendance record for\n"
            f"<b>{record['name']}</b> on <b>{record['date']}</b>?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        conn = DatabaseConfig.get_connection()
        if not conn:
            QMessageBox.critical(self, "Error", "Could not connect to the database.")
            return

        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance WHERE id=%s", (record['id'],))
            conn.commit()
            cursor.close()
            conn.close()

            QMessageBox.information(
                self, "Deleted",
                f"Record for {record['name']} on {record['date']} deleted."
            )
            self.load_attendance_data()   # re-fetch from API

        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", f"Could not delete record:\n{e}")
            import traceback; traceback.print_exc()

    # ─────────────────────────────────────────────────────────────
    #  Image viewer
    # ─────────────────────────────────────────────────────────────

    def _show_image(self, record):
        img_path = record.get('image_path')
        if not img_path or not os.path.exists(img_path):
            QMessageBox.warning(self, "Image Not Found", "Attendance image not available.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Attendance Image - {record['name']}")
        dialog.setMinimumSize(500, 600)
        layout = QVBoxLayout(dialog)

        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { background-color: #2a2a2a; border-radius: 8px; padding: 15px; }"
        )
        info_layout  = QVBoxLayout(info_frame)
        conf_score   = record.get('confidence_score', 0)
        status_code  = record.get('status') or AttendanceStatus.PRESENT
        info_text    = (
            f"<b>Name:</b> {record['name']}<br>"
            f"<b>User ID:</b> {record['user_id']}<br>"
            f"<b>Date:</b> {record['date']}<br>"
            f"<b>Time:</b> {record['time']}<br>"
            f"<b>Status:</b> {status_code} – {AttendanceStatus.label(status_code)}<br>"
            f"<b>Department:</b> {record.get('department', 'N/A')}<br>"
            f"<b>Confidence:</b> {conf_score:.2%}" if conf_score else "N/A"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #fff; font-size: 14px;")
        info_layout.addWidget(info_label)
        layout.addWidget(info_frame)

        img_label = QLabel()
        img = cv2.imread(img_path)
        if img is not None:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            q_image  = QImage(img_rgb.data, w, h, ch * w, QImage.Format_RGB888)
            pixmap   = QPixmap.fromImage(q_image)
            img_label.setPixmap(
                pixmap.scaled(450, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            img_label.setText("Failed to load image")
            img_label.setStyleSheet("color: #ff0000;")
        img_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(img_label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    # ─────────────────────────────────────────────────────────────
    #  CSV export
    # ─────────────────────────────────────────────────────────────

    def export_to_csv(self):
        if not self.current_records:
            QMessageBox.warning(self, "No Data", "No records to export.")
            return

        from PySide6.QtWidgets import QFileDialog
        import csv

        default_name = f"attendance_{self.select_date.date().toString('yyyy-MM-dd')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Attendance", default_name, "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "User ID", "Name", "Date", "Time", "Status",
                    "Department", "Role", "Confidence", "Image Path"
                ])
                for record in self.current_records:
                    conf        = record.get('confidence_score')
                    conf_str    = f"{conf:.4f}" if conf else 'N/A'
                    status_code = record.get('status') or AttendanceStatus.PRESENT
                    writer.writerow([
                        record['user_id'], record['name'],
                        record['date'],    record['time'],
                        f"{status_code} – {AttendanceStatus.label(status_code)}",
                        record.get('department', 'N/A'),
                        record.get('role', 'Employee'),
                        conf_str,
                        record.get('image_path', '')
                    ])

            QMessageBox.information(
                self, "Success",
                f"Exported {len(self.current_records)} records.\n\nFile: {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export:\n{str(e)}")