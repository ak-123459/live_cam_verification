"""
Watchlist Management Page
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QDialog, QComboBox, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QHeaderView, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from app.db.watchlist_manager import WatchlistManager
from app.db.database import UserManager
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AddToWatchlistDialog(QDialog):
    """Dialog to add user to watchlist"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add to Watchlist")
        self.setModal(True)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # User selection
        self.user_combo = QComboBox()
        self.user_combo.setPlaceholderText("Select user...")
        layout.addWidget(QLabel("User:"))
        layout.addWidget(self.user_combo)

        # Load users
        self.load_users()

        # Category
        self.category_combo = QComboBox()
        self.category_combo.addItems(['blacklist', 'whitelist', 'vip'])
        layout.addWidget(QLabel("Category:"))
        layout.addWidget(self.category_combo)

        # Threshold
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(0.75)
        layout.addWidget(QLabel("Recognition Threshold:"))
        layout.addWidget(self.threshold_spin)

        # Cooldown
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(5, 300)
        self.cooldown_spin.setSuffix(" seconds")
        self.cooldown_spin.setValue(10)
        layout.addWidget(QLabel("Alarm Cooldown:"))
        layout.addWidget(self.cooldown_spin)

        # Alert enabled
        self.alert_check = QCheckBox("Enable Alerts")
        self.alert_check.setChecked(True)
        layout.addWidget(self.alert_check)

        # Alarm enabled
        self.alarm_check = QCheckBox("Enable Alarm")
        self.alarm_check.setChecked(True)
        layout.addWidget(self.alarm_check)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def load_users(self):
        """Load all users into combo box"""
        try:
            users = UserManager.get_all_users()

            # Filter out users already in watchlist
            existing = WatchlistManager.get_all_watchlist()
            existing_ids = {w['user_id'] for w in existing}

            available_users = [u for u in users if u['user_id'] not in existing_ids]

            for user in available_users:
                self.user_combo.addItem(
                    f"{user['name']} ({user['user_id']})",
                    user['user_id']
                )

            if not available_users:
                self.user_combo.addItem("No available users", None)
                self.user_combo.setEnabled(False)

        except Exception as e:
            print(f"[WATCHLIST] Error loading users: {e}")

    def get_data(self):
        """Get dialog data"""
        user_id = self.user_combo.currentData()
        category = self.category_combo.currentText()
        threshold = self.threshold_spin.value()
        cooldown = self.cooldown_spin.value()
        alert_enabled = self.alert_check.isChecked()
        alarm_enabled = self.alarm_check.isChecked()

        return user_id, category, threshold, cooldown, alert_enabled, alarm_enabled


class WatchlistPage(QWidget):
    """Watchlist management page"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_watchlist)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Watchlist Management")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")

        self.count_label = QLabel("0 entries")
        self.count_label.setStyleSheet("color: #64748b; font-size: 14px;")

        self.add_btn = QPushButton("+ Add to Watchlist")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #111;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffb300;
            }
        """)
        self.add_btn.clicked.connect(self.add_to_watchlist)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.refresh_btn.clicked.connect(self.load_watchlist)

        header_layout.addWidget(title)
        header_layout.addWidget(self.count_label)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)
        header_layout.addWidget(self.add_btn)

        layout.addLayout(header_layout)

        # Info frame
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)

        info_text = QLabel(
            "ℹ️ The watchlist monitors specified users and triggers alerts when detected. "
            "Configure per-user thresholds, cooldowns, and alarm settings."
        )
        info_text.setStyleSheet("color: #94a3b8; font-size: 13px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_frame)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Name", "User ID", "Category", "Threshold",
            "Cooldown", "Alerts", "Alarm", "Actions"
        ])

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                color: #fff;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #ffc107;
                padding: 10px;
                border: none;
                font-weight: bold;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # User ID
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Category
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Threshold
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Cooldown
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Alerts
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Alarm
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Actions

        layout.addWidget(self.table)

        # Load data
        self.load_watchlist()

    def load_watchlist(self):
        """Load watchlist entries into table"""
        try:
            entries = WatchlistManager.get_all_watchlist()

            self.table.setRowCount(len(entries))
            self.count_label.setText(f"{len(entries)} entries")

            for row, entry in enumerate(entries):
                # Name
                name_item = QTableWidgetItem(entry['name'])
                self.table.setItem(row, 0, name_item)

                # User ID
                user_id_item = QTableWidgetItem(entry['user_id'])
                user_id_item.setForeground(QColor("#64748b"))
                self.table.setItem(row, 1, user_id_item)

                # Category
                category = entry['category']
                category_item = QTableWidgetItem(category.upper())

                if category == 'blacklist':
                    category_item.setForeground(QColor("#ef4444"))
                elif category == 'whitelist':
                    category_item.setForeground(QColor("#22c55e"))
                else:  # vip
                    category_item.setForeground(QColor("#fbbf24"))

                self.table.setItem(row, 2, category_item)

                # Threshold
                threshold_item = QTableWidgetItem(f"{entry['threshold']:.2f}")
                self.table.setItem(row, 3, threshold_item)

                # Cooldown
                cooldown_item = QTableWidgetItem(f"{entry['cooldown_sec']}s")
                self.table.setItem(row, 4, cooldown_item)

                # Alerts
                alert_item = QTableWidgetItem("✓" if entry['alert_enabled'] else "✗")
                alert_item.setForeground(
                    QColor("#22c55e") if entry['alert_enabled'] else QColor("#64748b")
                )
                self.table.setItem(row, 5, alert_item)

                # Alarm
                alarm_item = QTableWidgetItem("🔔" if entry['alarm_enabled'] else "🔕")
                self.table.setItem(row, 6, alarm_item)

                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(4, 4, 4, 4)

                remove_btn = QPushButton("Remove")
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #7f1d1d;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #991b1b;
                    }
                """)
                remove_btn.clicked.connect(
                    lambda checked, uid=entry['user_id']: self.remove_from_watchlist(uid)
                )

                actions_layout.addWidget(remove_btn)

                self.table.setCellWidget(row, 7, actions_widget)

        except Exception as e:
            print(f"[WATCHLIST] Error loading watchlist: {e}")
            import traceback
            traceback.print_exc()

    def add_to_watchlist(self):
        """Show dialog to add user to watchlist"""
        dialog = AddToWatchlistDialog(self)

        if dialog.exec() == QDialog.Accepted:
            user_id, category, threshold, cooldown, alert_enabled, alarm_enabled = dialog.get_data()

            if not user_id:
                QMessageBox.warning(self, "Invalid Selection", "Please select a user.")
                return

            success = WatchlistManager.add_to_watchlist(
                user_id, category, alert_enabled, alarm_enabled, threshold, cooldown
            )

            if success:
                QMessageBox.information(
                    self, "Success",
                    f"User added to {category} watchlist successfully!"
                )
                self.load_watchlist()
            else:
                QMessageBox.warning(
                    self, "Failed",
                    "Failed to add user to watchlist. User may already be in watchlist."
                )

    def remove_from_watchlist(self, user_id):
        """Remove user from watchlist"""
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Are you sure you want to remove this user from the watchlist?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = WatchlistManager.remove_from_watchlist(user_id)

            if success:
                QMessageBox.information(self, "Success", "User removed from watchlist.")
                self.load_watchlist()
            else:
                QMessageBox.warning(self, "Failed", "Failed to remove user from watchlist.")