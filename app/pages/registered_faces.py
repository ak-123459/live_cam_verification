"""
Registered Users Page  —  all data operations go through REST API.
No direct DB / UserManager imports.
"""
from __future__ import annotations

import os
import cv2
import requests
from dotenv import load_dotenv

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFrame, QMessageBox, QComboBox, QDialog,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QColor

from dotenv import load_dotenv, dotenv_values
from pathlib import Path
from app.config.api_config import _get_api_base, _get_timeout, _get_endpoint



_ENV_PATH = Path(".env")




# ─── Low-level API helpers ────────────────────────────────────────────────────

def _request(method: str, path: str, **kwargs):
    api_base = _get_api_base()          # ← fresh every call
    timeout  = _get_timeout()           # ← fresh every call
    url = f"{api_base}{path}"
    try:
        resp = requests.request(method, url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to API at {api_base}.\n"
            "Check that the server is running and API_HOST / API_PORT are correct in .env"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(f"API request timed out after {timeout}s")
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except Exception:
            detail = e.response.text
        raise RuntimeError(f"API {e.response.status_code}: {detail}")



def api_get_users(department=None, role=None, name=None) -> list[dict]:
    params = {}
    if department: params["department"] = department
    if role:       params["role"]       = role
    if name:       params["name"]       = name
    data = _request("GET", "/users", params=params)
    return data.get("users", [])


def api_get_user(user_id: int) -> dict:
    return _request("GET", f"/users/{user_id}")


def api_update_user(user_id: int, **fields) -> dict:
    """PATCH /users/{user_id} — returns updated user dict."""
    return _request("PATCH", f"/users/{user_id}", json=fields)


def api_delete_user(user_id: int) -> dict:
    """DELETE /users/{user_id} — returns {success, user_id, message}."""
    return _request("DELETE", f"/users/{user_id}")


# ─── Background worker ────────────────────────────────────────────────────────

class FetchUsersWorker(QThread):
    finished = Signal(list)
    error    = Signal(str)

    def __init__(self, department=None, role=None, name=None):
        super().__init__()
        self.department = department
        self.role       = role
        self.name       = name

    def run(self):
        try:
            users = api_get_users(self.department, self.role, self.name)
            self.finished.emit(users)
        except Exception as e:
            self.error.emit(str(e))


# ─── User Details Dialog ──────────────────────────────────────────────────────

class UserDetailsDialog(QDialog):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"User Details — {user.get('name', 'N/A')}")
        self.setMinimumSize(550, 650)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Face image ──
        img_frame = QFrame(); img_frame.setObjectName("card")
        img_layout = QVBoxLayout(img_frame)
        img_layout.setContentsMargins(20, 20, 20, 20)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(200, 200)
        self.image_label.setStyleSheet("""
            QLabel { border: 3px solid #ffc107; border-radius: 100px;
                     background-color: #333333; }
        """)
        self._load_face_image()
        img_layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        layout.addWidget(img_frame)

        # ── Detail rows ──
        detail_frame = QFrame(); detail_frame.setObjectName("card")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(12)

        d = self.user
        fields = [
            ("User ID:",    str(d.get("user_id",    "N/A"))),
            ("Name:",           d.get("name",       "N/A")),
            ("Email:",      str(d.get("email",      "") or "N/A")),
            ("Phone:",      str(d.get("phone",      "") or "N/A")),
            ("Department:", str(d.get("department", "") or "N/A")),
            ("Role:",       str(d.get("role",       "Employee") or "Employee")),
            ("Created:",    str(d.get("created_at", "N/A"))[:19]),
        ]
        for lbl_txt, val_txt in fields:
            row = QHBoxLayout(); row.setSpacing(10)
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet("color: #ffc107; font-weight: bold; font-size: 13px;")
            lbl.setMinimumWidth(100)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val = QLabel(val_txt)
            val.setStyleSheet("color: #fff; font-size: 14px;")
            val.setWordWrap(True)
            row.addWidget(lbl); row.addWidget(val, 1)
            detail_layout.addLayout(row)
        layout.addWidget(detail_frame)

        # ── Buttons ──
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        edit_btn = QPushButton("✏ Edit User")
        edit_btn.setMinimumHeight(40)
        edit_btn.setStyleSheet("""
            QPushButton { background-color:#ffc107; color:#111; border:none;
                          border-radius:5px; font-weight:bold; font-size:14px; }
            QPushButton:hover { background-color:#ffb300; }
        """)
        edit_btn.clicked.connect(self._open_edit)

        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(40)
        close_btn.setStyleSheet("""
            QPushButton { background-color:#555; color:#fff; border:none;
                          border-radius:5px; font-weight:bold; font-size:14px; }
            QPushButton:hover { background-color:#666; }
        """)
        close_btn.clicked.connect(self.close)

        btn_row.addWidget(edit_btn); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_face_image(self):
        uid = str(self.user.get("user_id", ""))
        for path in [
            f"registered_faces/{uid}.jpg",
            f"registered_faces/{uid}/face_1.jpg",
            f"registered_faces/{uid}/face_0.jpg",
        ]:
            if os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    qi = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                    px = QPixmap.fromImage(qi).scaled(190, 190,
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_label.setPixmap(px)
                    return
        self.image_label.setText("No Image")
        self.image_label.setStyleSheet("""
            QLabel { border:2px solid #333; border-radius:100px;
                     background-color:#222; color:#666; font-size:14px; }
        """)

    def _open_edit(self):
        dlg = EditUserDialog(self.user, parent=self)
        if dlg.exec() == QDialog.Accepted:
            # Refresh our own view with latest data from API
            try:
                updated = api_get_user(self.user["user_id"])
                self.user = updated
            except Exception:
                pass


# ─── Edit User Dialog ─────────────────────────────────────────────────────────

class EditUserDialog(QDialog):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"Edit User — {user.get('name', '')}")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        form_frame = QFrame(); form_frame.setObjectName("card")
        form = QVBoxLayout(form_frame)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(15)

        d = self.user

        # User ID — read-only
        id_row = QHBoxLayout()
        id_lbl = QLabel("User ID:"); id_lbl.setStyleSheet("color:#ffc107;font-weight:bold;")
        id_val = QLabel(str(d.get("user_id", ""))); id_val.setStyleSheet("color:#fff;")
        id_row.addWidget(id_lbl); id_row.addWidget(id_val); id_row.addStretch()
        form.addLayout(id_row)

        def _field(label, value):
            lbl = QLabel(label); lbl.setStyleSheet("color:#ffc107;font-weight:bold;")
            form.addWidget(lbl)
            inp = QLineEdit(str(value or "")); inp.setMinimumHeight(35)
            form.addWidget(inp)
            return inp

        self.name_input       = _field("Name: *",     d.get("name",       ""))
        self.email_input      = _field("Email:",      d.get("email",      ""))
        self.phone_input      = _field("Phone:",      d.get("phone",      ""))
        self.department_input = _field("Department:", d.get("department", ""))

        role_lbl = QLabel("Role:"); role_lbl.setStyleSheet("color:#ffc107;font-weight:bold;")
        form.addWidget(role_lbl)
        self.role_combo = QComboBox(); self.role_combo.setMinimumHeight(35)
        self.role_combo.addItems(["Employee", "Manager", "Admin", "Intern"])
        idx = self.role_combo.findText(d.get("role", "Employee") or "Employee")
        if idx >= 0: self.role_combo.setCurrentIndex(idx)
        form.addWidget(self.role_combo)

        layout.addWidget(form_frame)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        save_btn = QPushButton("💾 Save Changes"); save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet("""
            QPushButton { background-color:#10b981; color:white; border:none;
                          border-radius:5px; font-weight:bold; font-size:14px; }
            QPushButton:hover { background-color:#059669; }
        """)
        save_btn.clicked.connect(self._save)

        cancel_btn = QPushButton("Cancel"); cancel_btn.setMinimumHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton { background-color:#555; color:white; border:none;
                          border-radius:5px; font-weight:bold; font-size:14px; }
            QPushButton:hover { background-color:#666; }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(save_btn); btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Name is required!")
            return

        user_id = self.user.get("user_id")
        updates = {
            "name":       name,
            "email":      self.email_input.text().strip()      or None,
            "phone":      self.phone_input.text().strip()      or None,
            "department": self.department_input.text().strip() or None,
            "role":       self.role_combo.currentText(),
        }
        # Remove None values — API will only update supplied fields
        updates = {k: v for k, v in updates.items() if v is not None}

        try:
            updated = api_update_user(user_id, **updates)   # PATCH /users/{id}

            msg = QMessageBox(self)
            msg.setWindowTitle("✅ User Updated Successfully")
            msg.setIcon(QMessageBox.Information)
            msg.setText(
                f"<b>User updated successfully!</b><br><br>"
                f"<table cellpadding='5' style='color:#333;'>"
                f"<tr><td><b>User ID:</b></td><td>{user_id}</td></tr>"
                f"<tr><td><b>Name:</b></td><td>{updated.get('name')}</td></tr>"
                f"<tr><td><b>Email:</b></td><td>{updated.get('email') or 'N/A'}</td></tr>"
                f"<tr><td><b>Phone:</b></td><td>{updated.get('phone') or 'N/A'}</td></tr>"
                f"<tr><td><b>Department:</b></td><td>{updated.get('department') or 'N/A'}</td></tr>"
                f"<tr><td><b>Role:</b></td><td>{updated.get('role')}</td></tr>"
                f"</table>"
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            self.accept()

        except RuntimeError as e:
            QMessageBox.critical(self, "API Error", str(e))


# ─── Main Users Page ──────────────────────────────────────────────────────────

class UsersPage(QWidget):
    """Registered Users page — all CRUD via REST API (GET / PATCH / DELETE /users)."""

    def __init__(self, face_registration=None, parent=None):
        super().__init__(parent)
        # face_registration: optional FaceRegistration instance for FAISS cleanup
        self.face_registration = face_registration
        self.all_users: list[dict] = []

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._do_fetch)

        self._worker = None
        self._setup_ui()
        self.load_users()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Registered Users")
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#fff;")
        header.addWidget(title)
        header.addStretch()

        self.api_status = QLabel(f"🔗 {_get_api_base()}")

        self.api_status.setStyleSheet("color:#94a3b8; font-size:12px;")
        header.addWidget(self.api_status)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedWidth(120)
        refresh_btn.clicked.connect(self.load_users)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        # Stats
        stats_row = QHBoxLayout(); stats_row.setSpacing(15)
        self.card_total     = self._stat_card("Total Users", "0", "#ffc107")
        self.card_employees = self._stat_card("Employees",   "0", "#3b82f6")
        self.card_managers  = self._stat_card("Managers",    "0", "#10b981")
        self.card_admins    = self._stat_card("Admins",      "0", "#ef4444")
        for c in (self.card_total, self.card_employees, self.card_managers, self.card_admins):
            stats_row.addWidget(c)
        stats_row.addStretch()
        root.addLayout(stats_row)

        # Filters
        filter_frame = QFrame(); filter_frame.setObjectName("card")
        filter_row = QHBoxLayout(filter_frame); filter_row.setSpacing(15)

        def _lbl(text):
            l = QLabel(text); l.setStyleSheet("color:#ffc107; font-weight:bold;")
            return l

        filter_row.addWidget(_lbl("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, email, department…")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(lambda: self._search_timer.start())
        filter_row.addWidget(self.search_input, 2)

        filter_row.addWidget(_lbl("Role:"))
        self.role_filter = QComboBox(); self.role_filter.setMinimumHeight(40)
        self.role_filter.addItems(["All Roles", "Employee", "Manager", "Admin", "Intern"])
        self.role_filter.currentTextChanged.connect(self.load_users)
        filter_row.addWidget(self.role_filter)

        filter_row.addWidget(_lbl("Department:"))
        self.dept_filter = QComboBox(); self.dept_filter.setMinimumHeight(40)
        self.dept_filter.addItem("All Departments")
        self.dept_filter.currentTextChanged.connect(self.load_users)
        filter_row.addWidget(self.dept_filter)

        root.addWidget(filter_frame)

        # Results label
        self.results_label = QLabel("Loading…")
        self.results_label.setStyleSheet("color:#94a3b8; font-size:13px;")
        root.addWidget(self.results_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "User ID", "Name", "Email", "Phone",
            "Department", "Role", "Created", "Actions"
        ])
        self.table.setStyleSheet("""
            QTableWidget { background-color:#222; border:1px solid #333;
                           border-radius:8px; color:#fff; gridline-color:#333; }
            QTableWidget::item { padding:10px; }
            QTableWidget::item:selected { background-color:#ffc107; color:#111; }
            QHeaderView::section { background-color:#2a2a2a; color:#fff;
                                   padding:12px; border:none; font-weight:bold; }
        """)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for col, width in enumerate([80, 140, 180, 110, 110, 90, 100, 280]):
            self.table.setColumnWidth(col, width)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(75)
        root.addWidget(self.table)

    def _stat_card(self, title, value, color):
        frame = QFrame(); frame.setObjectName("card"); frame.setMinimumHeight(90)
        vl = QVBoxLayout(frame)
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"font-size:32px; font-weight:bold; color:{color};")
        val_lbl.setAlignment(Qt.AlignCenter)
        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet("font-size:13px; color:#94a3b8;")
        ttl_lbl.setAlignment(Qt.AlignCenter)
        vl.addWidget(val_lbl); vl.addWidget(ttl_lbl)
        frame.value_label = val_lbl
        return frame

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def load_users(self):
        self._search_timer.stop()
        self._do_fetch()

    def _do_fetch(self):
        if self._worker and self._worker.isRunning():
            self._worker.quit()

        self.results_label.setText("⏳ Fetching users…")
        self.results_label.setStyleSheet("color:#ffc107; font-size:13px;")

        role = self.role_filter.currentText()
        dept = self.dept_filter.currentText()
        name = self.search_input.text().strip()

        self._worker = FetchUsersWorker(
            department = dept if dept != "All Departments" else None,
            role       = role if role != "All Roles"       else None,
            name       = name or None,
        )
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, users: list[dict]):
        self.all_users = users

        # Rebuild dept dropdown without triggering another fetch
        depts = sorted({u.get("department") or "" for u in users if u.get("department")})
        prev = self.dept_filter.currentText()
        self.dept_filter.blockSignals(True)
        self.dept_filter.clear()
        self.dept_filter.addItem("All Departments")
        self.dept_filter.addItems(depts)
        idx = self.dept_filter.findText(prev)
        if idx >= 0: self.dept_filter.setCurrentIndex(idx)
        self.dept_filter.blockSignals(False)

        self._display_users()
        self._update_stats()

        n = len(users)
        self.results_label.setText(f"Showing {n} user{'s' if n != 1 else ''}")
        self.results_label.setStyleSheet("color:#94a3b8; font-size:13px;")
        self.api_status.setText(f"✅ {_get_api_base()}")
        self.api_status.setStyleSheet("color:#10b981; font-size:12px;")

    def _on_error(self, msg: str):
        self.results_label.setText("❌ Failed to load users")
        self.results_label.setStyleSheet("color:#ef4444; font-size:13px;")
        self.api_status.setText(f"❌ {_get_api_base()}")
        self.api_status.setStyleSheet("color:#ef4444; font-size:12px;")
        QMessageBox.critical(self, "API Error", f"Failed to fetch users:\n\n{msg}")

    # ── Display ───────────────────────────────────────────────────────────────

    def _display_users(self):
        self.table.setRowCount(len(self.all_users))

        for row, user in enumerate(self.all_users):
            def _v(key, default="N/A"):
                v = user.get(key, default)
                return str(v) if v is not None else default

            self.table.setItem(row, 0, QTableWidgetItem(_v("user_id")))
            self.table.setItem(row, 1, QTableWidgetItem(_v("name")))
            self.table.setItem(row, 2, QTableWidgetItem(_v("email")))
            self.table.setItem(row, 3, QTableWidgetItem(_v("phone")))
            self.table.setItem(row, 4, QTableWidgetItem(_v("department")))

            role      = _v("role", "Employee")
            role_item = QTableWidgetItem(role)
            role_item.setForeground({
                "Admin":    QColor("#ef4444"),
                "Manager":  QColor("#10b981"),
                "Employee": QColor("#3b82f6"),
                "Intern":   QColor("#f59e0b"),
            }.get(role, QColor("#94a3b8")))
            self.table.setItem(row, 5, role_item)

            self.table.setItem(row, 6, QTableWidgetItem(_v("created_at")[:10]))

            # Action buttons
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(5, 5, 5, 5)
            cell_layout.setSpacing(5)

            def _btn(icon, tip, bg, hover, slot):
                b = QPushButton(icon)
                b.setToolTip(tip)
                b.setFixedSize(60, 55)
                b.setStyleSheet(
                    f"QPushButton {{ background-color:{bg}; color:white; border:none;"
                    f" border-radius:5px; font-weight:bold; font-size:16px; }}"
                    f"QPushButton:hover {{ background-color:{hover}; }}"
                )
                b.clicked.connect(slot)
                return b

            cell_layout.addWidget(_btn("👁",  "View Details", "#3b82f6", "#2563eb",
                                        lambda _, u=user: self._view(u)))
            cell_layout.addWidget(_btn("✏",  "Edit User",    "#10b981", "#059669",
                                        lambda _, u=user: self._edit(u)))
            cell_layout.addWidget(_btn("🗑", "Delete User",  "#ef4444", "#dc2626",
                                        lambda _, u=user: self._delete(u)))
            cell_layout.addStretch()
            self.table.setCellWidget(row, 7, cell)

    def _update_stats(self):
        counts = {"Employee": 0, "Manager": 0, "Admin": 0}
        for u in self.all_users:
            r = u.get("role", "Employee") or "Employee"
            if r in counts: counts[r] += 1
        self.card_total.value_label.setText(str(len(self.all_users)))
        self.card_employees.value_label.setText(str(counts["Employee"]))
        self.card_managers.value_label.setText(str(counts["Manager"]))
        self.card_admins.value_label.setText(str(counts["Admin"]))

    # ── CRUD actions ──────────────────────────────────────────────────────────

    def _view(self, user: dict):
        UserDetailsDialog(user, self).exec()

    def _edit(self, user: dict):
        dlg = EditUserDialog(user, self)
        if dlg.exec() == QDialog.Accepted:
            self.load_users()

    def _delete(self, user: dict):
        user_id   = user.get("user_id")
        user_name = user.get("name", "Unknown")

        reply = QMessageBox.question(
            self, "⚠ Confirm Deletion",
            f"Are you sure you want to delete:\n\n"
            f"ID: {user_id}\nName: {user_name}\n\n"
            f"This will permanently remove:\n"
            f"• User record from database\n"
            f"• Face embeddings from FAISS\n"
            f"• All registered face images\n\n"
            f"This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success_steps: list[str] = []
        failed_steps:  list[str] = []

        # 1 — FAISS (local, no API needed)
        if self.face_registration:
            try:
                ok, msg = self.face_registration.delete_user(user_id)
                (success_steps if ok else failed_steps).append(
                    f"{'✓' if ok else '✗'} FAISS: {msg}"
                )
            except Exception as e:
                failed_steps.append(f"✗ FAISS error: {e}")
        else:
            failed_steps.append("⚠️ FAISS skipped (no instance)")

        # 2 — Face images (local filesystem)
        try:
            import shutil
            user_dir = os.path.join("registered_faces", str(user_id))
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
            success_steps.append("✓ Deleted face images")
        except Exception as e:
            failed_steps.append(f"✗ File error: {e}")

        # 3 — Database via API  →  DELETE /users/{user_id}
        try:
            result = api_delete_user(user_id)
            if result.get("success"):
                success_steps.append(f"✓ {result.get('message', 'Removed from database')}")
            else:
                failed_steps.append("✗ API reported failure for database deletion")
        except RuntimeError as e:
            failed_steps.append(f"✗ API error: {e}")

        # ── Result dialog ──
        if not failed_steps:
            msg = QMessageBox(self)
            msg.setWindowTitle("✅ User Deleted Successfully")
            msg.setIcon(QMessageBox.Information)
            msg.setText(
                f"<b>User '{user_name}' deleted successfully!</b><br><br>"
                f"<table cellpadding='5' style='color:#333;'>"
                f"<tr><td><b>User ID:</b></td><td>{user_id}</td></tr>"
                f"<tr><td><b>Name:</b></td><td>{user_name}</td></tr>"
                f"</table><br><b>Operations completed:</b><br>"
                + "".join(f"&nbsp;&nbsp;{s}<br>" for s in success_steps)
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        else:
            body = f"<b>Deletion of '{user_name}' finished with issues:</b><br><br>"
            if success_steps:
                body += "<b>✓ Successful:</b><br>" + \
                        "".join(f"&nbsp;&nbsp;{s}<br>" for s in success_steps) + "<br>"
            body += "<b>✗ Failed:</b><br>" + \
                    "".join(f"&nbsp;&nbsp;{s}<br>" for s in failed_steps)
            msg = QMessageBox(self)
            msg.setWindowTitle("⚠ Partial Deletion")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(body)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

        self.load_users()