"""
Face Registration Page - Register new faces via API
Sends captured images to the face registration API endpoint.
API host/port are loaded from .env file.
"""
import os
import cv2
import importlib
import requests
import numpy as np
from pathlib import Path
import insightface
from insightface.utils import face_align as _face_align
from insightface.app import FaceAnalysis as _FaceAnalysis
from app.workers.face_registration import FaceRegistration
from dotenv import load_dotenv, dotenv_values
from pathlib import Path
from app.config.api_config import _get_api_base, _get_timeout, _get_endpoint



# ─────────────────────────────────────────────
#  Patch InsightFace face_align ONCE at import time
#  so norm_crop accepts any size (e.g. 300x300)
# ─────────────────────────────────────────────
def _patch_face_align():
    try:
        import insightface.utils.face_align as _fa
        with open(_fa.__file__, 'r') as f:
            code = f.read()
        if 'image_size%112==0 or image_size%128==0' in code:
            patched = code.replace(
                'assert image_size%112==0 or image_size%128==0',
                'assert image_size > 0  # patched: allow any size'
            )
            with open(_fa.__file__, 'w') as f:
                f.write(patched)
            print("[REG PAGE] ✅ face_align patched for 300x300")
        importlib.reload(insightface.utils.face_align)
    except Exception as e:
        print(f"[REG PAGE] ⚠️ face_align patch failed: {e}")

_patch_face_align()


FACE_CROP_SIZE = 300  # aligned crop size sent to API

# ─── Lazy face detector for registration page ────────────────
#     Shared so it initialises only once across the process
_reg_detector = None




def _get_detector():
    global _reg_detector
    if FaceRegistration._shared_model is not None:
        _reg_detector = FaceRegistration._shared_model  # ✅ reuse
        return _reg_detector

    return _reg_detector



from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QMessageBox, QFrame,
    QScrollArea, QGroupBox, QGridLayout, QProgressBar, QDialog,
    QDialogButtonBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QImage, QPixmap

from app.workers.registration_camera_worker import RegistrationCameraWorker

# ─────────────────────────────────────────────
#  Quality matcher (applied locally before API)
# ─────────────────────────────────────────────
try:
    from app.utils.global_quality_matcher import GlobalQualityMatcher
    _quality_matcher_available = True
except ImportError:
    _quality_matcher_available = False
    print("[REG PAGE] Warning: GlobalQualityMatcher not available")


_ENV_PATH = Path(".env")




def _get_register_endpoint() -> str:
    return f"{_get_api_base()}/faces/register"






# ─────────────────────────────────────────────
#  Background worker: calls the register API
# ─────────────────────────────────────────────
class RegistrationAPIWorker(QThread):
    """
    Sends captured face images + user details to /faces/register in a
    background thread so the UI never freezes.
    """
    success = Signal(dict)          # emits full JSON response on 200
    duplicate = Signal(dict)        # emits full JSON response on 409
    failed = Signal(str)            # emits error message on anything else

    def __init__(self, image_list: list, user_data: dict, parent=None):
        """
        Args:
            image_list: list of BGR numpy arrays (captured / uploaded frames)
            user_data:  dict with keys name, email, phone, department, role, threshold
        """
        super().__init__(parent)
        self.image_list = image_list
        self.user_data = user_data

    def run(self):
        try:
            # ── Build multipart files list ──────────────────────────────
            files = []
            encoded_buffers = []  # keep refs alive during request

            for i, frame in enumerate(self.image_list):
                ok, buf = cv2.imencode(".jpg", frame)
                if not ok:
                    self.failed.emit(f"Failed to encode image {i + 1}")
                    return
                encoded_buffers.append(buf)
                files.append(
                    ("files", (f"face_{i + 1}.jpg", buf.tobytes(), "image/jpeg"))
                )

            # ── POST request ────────────────────────────────────────────
            response = requests.post(
                _get_register_endpoint(),
                data=self.user_data,
                files=files,
                timeout=_get_timeout(),
            )

            if response.status_code == 200:
                self.success.emit(response.json())

            elif response.status_code == 409:
                self.duplicate.emit(response.json())

            else:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                self.failed.emit(f"API error {response.status_code}: {detail}")

        except requests.exceptions.ConnectionError:
            self.failed.emit(
                f"Cannot connect to API server at {_get_api_base()}.\n"
                "Please check that the server is running and API_HOST / API_PORT "
                "in your .env file are correct."
            )
        except requests.exceptions.Timeout:
            self.failed.emit(
                f"Request timed out after {_get_timeout()}s. "
                "The server may be busy."
            )
        except Exception as e:
            self.failed.emit(f"Unexpected error: {str(e)}")


# ─────────────────────────────────────────────
#  Duplicate user dialog  (unchanged behaviour)
# ─────────────────────────────────────────────
class DuplicateUserDialog(QDialog):
    """Shows the existing user info returned by the API on 409."""

    def __init__(self, api_response: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ Duplicate User Detected")
        self.setMinimumWidth(500)

        detail = api_response.get("detail", {})
        self.similarity = detail.get("similarity", 0.0)
        self.threshold  = detail.get("threshold", 80.0)
        self.existing   = detail.get("existing_user", {})

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── Red header ──────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("""
            QFrame { background-color: #ef4444; border-radius: 8px; padding: 12px; }
        """)
        h_layout = QVBoxLayout(header)

        lbl_title = QLabel("⚠️ User Already Registered!")
        lbl_title.setStyleSheet("color:#fff; font-size:18px; font-weight:bold;")
        lbl_title.setAlignment(Qt.AlignCenter)

        lbl_sim = QLabel(
            f"Similarity: {self.similarity:.1f}%  |  Threshold: {self.threshold:.0f}%"
        )
        lbl_sim.setStyleSheet("color:#fff; font-size:13px;")
        lbl_sim.setAlignment(Qt.AlignCenter)

        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_sim)
        layout.addWidget(header)

        # ── Existing user info ──────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color:#1a1a1a; border:1px solid #333;
                     border-radius:8px; padding:12px; }
        """)
        c_layout = QVBoxLayout(card)

        title = QLabel("Existing User Information:")
        title.setStyleSheet("color:#ffc107; font-weight:bold; font-size:14px;")
        c_layout.addWidget(title)

        rows = [
            ("User ID",    self.existing.get("user_id",    "N/A")),
            ("Name",       self.existing.get("name",       "N/A")),
            ("Department", self.existing.get("department", "N/A")),
            ("Role",       self.existing.get("role",       "N/A")),
        ]
        table_html = "<table style='width:100%; color:#fff;'>"
        for label, value in rows:
            table_html += (
                f"<tr>"
                f"<td style='padding:5px; color:#94a3b8; font-weight:bold; width:110px;'>{label}:</td>"
                f"<td style='padding:5px;'>{value}</td>"
                f"</tr>"
            )
        table_html += "</table>"

        info = QLabel(table_html)
        info.setWordWrap(True)
        c_layout.addWidget(info)
        layout.addWidget(card)

        # ── Note ────────────────────────────────────────────────────────
        note = QLabel(
            "❌ Registration blocked. Please try registering a different person."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#ef4444; font-weight:bold; font-size:13px;")
        layout.addWidget(note)

        # ── OK button ───────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


# ─────────────────────────────────────────────
#  Main Registration Page
# ─────────────────────────────────────────────
class RegistrationPage(QWidget):
    """
    Face registration page.

    Flow
    ────
    1. User picks source: live camera  OR  upload 5 images
    2. 5 face frames are collected
    3. On "Register Face":
       - All 5 frames + user details  →  POST /faces/register
       - 200  →  success dialog, form reset
       - 409  →  DuplicateUserDialog shown, form reset
       - other →  error message
    """

    registration_completed = Signal(str, str)   # user_id, name

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self.camera_worker   = None
        self.capture_timer   = None
        self.is_capturing    = False
        self.current_frame   = None
        self.captured_images = []          # list of BGR numpy arrays
        self.target_captures = 5
        self.source_mode     = "camera"
        self._api_worker     = None
        self._upload_worker  = None

        # Quality matcher — applied locally to images BEFORE sending to API
        self.quality_matcher     = None
        self.selected_profile_id = None
        self._init_quality_matcher()

        self.setup_ui()

    def _init_quality_matcher(self):
        """Initialize the GlobalQualityMatcher"""
        if not _quality_matcher_available:
            return
        try:
            self.quality_matcher = GlobalQualityMatcher()
            print("[REG PAGE] ✓ Quality matcher initialized")
        except Exception as e:
            print(f"[REG PAGE] Warning: Could not init quality matcher: {e}")

    def _apply_quality(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply the loaded quality profile to a single BGR frame.
        Returns the processed frame, or the original if no profile is loaded.
        """
        if self.quality_matcher and self.quality_matcher.quality_profile:
            try:
                return self.quality_matcher.apply_quality_profile(frame, intensity=0.7)
            except Exception as e:
                print(f"[REG PAGE] Warning: quality apply failed: {e}")
        return frame

    def _extract_300_crop(self, bgr_frame: np.ndarray):
        """
        Detect face in bgr_frame, align it using ArcFace 5-point landmarks,
        and return a 300x300 BGR crop.

        Returns:
            (success: bool, crop: np.ndarray | None, message: str)
        """
        try:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            detector = _get_detector()
            faces = detector.get(rgb)

            if len(faces) == 0:
                return False, None, "No face detected"
            if len(faces) > 1:
                return False, None, "Multiple faces detected — only one person allowed"

            face = faces[0]

            # norm_crop uses the original BGR image + 5 keypoints → 300x300 aligned crop
            crop = _face_align.norm_crop(
                bgr_frame,
                landmark=face.kps,
                image_size=FACE_CROP_SIZE
            )
            return True, crop, "OK"

        except Exception as e:
            return False, None, f"Face extraction error: {str(e)}"

    def _get_available_profiles(self):
        profile_dir = "camera_profiles"
        if not os.path.exists(profile_dir):
            return []
        return [
            f.replace("_profile.pkl", "")
            for f in os.listdir(profile_dir)
            if f.endswith("_profile.pkl")
        ]

    def _load_profile_dropdown(self):
        self.profile_combo.clear()
        self.profile_combo.addItem("No Profile (Default)", None)
        for pid in self._get_available_profiles():
            self.profile_combo.addItem(pid, pid)

    def _on_profile_selected(self, index):
        profile_id = self.profile_combo.itemData(index)
        if profile_id is None:
            self.selected_profile_id = None
            self.profile_status_label.setText("No profile — images sent as-is")
            self.profile_status_label.setStyleSheet("color:#64748b; font-size:12px;")
        elif self.quality_matcher and self.quality_matcher.load_profile(profile_id):
            self.selected_profile_id = profile_id
            self.profile_status_label.setText(f"✓ Profile loaded: {profile_id}")
            self.profile_status_label.setStyleSheet(
                "color:#22c55e; font-size:12px; font-weight:bold;"
            )
            print(f"[REG PAGE] ✓ Quality profile loaded: {profile_id}")
        else:
            self.selected_profile_id = None
            self.profile_status_label.setText("❌ Failed to load profile")
            self.profile_status_label.setStyleSheet("color:#ef4444; font-size:12px;")

    # ══════════════════════════════════════════
    #  UI BUILD
    # ══════════════════════════════════════════

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        title = QLabel("Register New Face")
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#fff;")
        main_layout.addWidget(title)

        # API status banner
        self.api_status_label = QLabel(
            f"🌐 API: {_get_api_base()}"
        )
        self.api_status_label.setStyleSheet(
            "color:#64748b; font-size:12px; padding:4px;"
        )
        main_layout.addWidget(self.api_status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background:transparent; border:none;")

        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(20)

        c_layout.addWidget(self._build_source_section())
        c_layout.addWidget(self._build_quality_profile_section())
        c_layout.addWidget(self._build_capture_section())
        c_layout.addWidget(self._build_details_section())

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.reset_button = QPushButton("Reset")
        self.reset_button.setMinimumHeight(40)
        self.reset_button.clicked.connect(self.reset_form)

        self.register_button = QPushButton("Register Face")
        self.register_button.setMinimumHeight(40)
        self.register_button.setEnabled(False)
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color:#ffc107; color:#000; border:none;
                padding:12px 24px; border-radius:8px;
                font-weight:bold; font-size:14px;
            }
            QPushButton:hover  { background-color:#ffca2c; }
            QPushButton:disabled { background-color:#666; color:#999; }
        """)
        self.register_button.clicked.connect(self.register_face)

        btn_row.addWidget(self.reset_button)
        btn_row.addWidget(self.register_button)
        c_layout.addLayout(btn_row)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _build_source_section(self):
        group = QGroupBox("Input Source")
        group.setStyleSheet("""
            QGroupBox {
                background-color:#1a1a47; border:1px solid #3b82f6;
                border-radius:12px; padding:20px; margin-top:10px;
                font-size:16px; font-weight:bold; color:#3b82f6;
            }
        """)
        layout = QVBoxLayout(group)

        desc = QLabel("Choose how to provide face images for registration:")
        desc.setStyleSheet("color:#94a3b8; font-size:13px; font-weight:normal;")
        layout.addWidget(desc)

        toggle_style = """
            QPushButton {
                background-color:#333; color:#fff;
                border:2px solid #444; padding:12px;
                border-radius:8px; font-weight:bold; font-size:14px;
            }
            QPushButton:checked        { background-color:#3b82f6; border-color:#3b82f6; }
            QPushButton:hover          { background-color:#444; }
            QPushButton:checked:hover  { background-color:#2563eb; }
        """

        self.camera_radio = QPushButton("📷 Camera Capture")
        self.camera_radio.setCheckable(True)
        self.camera_radio.setChecked(True)
        self.camera_radio.setMinimumHeight(50)
        self.camera_radio.setStyleSheet(toggle_style)
        self.camera_radio.clicked.connect(lambda: self.on_source_changed("camera"))

        self.upload_radio = QPushButton("📁 Upload Images")
        self.upload_radio.setCheckable(True)
        self.upload_radio.setMinimumHeight(50)
        self.upload_radio.setStyleSheet(toggle_style)
        self.upload_radio.clicked.connect(lambda: self.on_source_changed("upload"))

        row = QHBoxLayout()
        row.addWidget(self.camera_radio)
        row.addWidget(self.upload_radio)
        layout.addLayout(row)
        return group

    def _build_quality_profile_section(self):
        """Camera quality profile selector — profile is applied locally before API upload."""
        group = QGroupBox("Camera Quality Profile (Applied Locally)")
        group.setStyleSheet("""
            QGroupBox {
                background-color:#1a472a; border:1px solid #22c55e;
                border-radius:12px; padding:20px; margin-top:10px;
                font-size:16px; font-weight:bold; color:#22c55e;
            }
        """)
        layout = QVBoxLayout(group)

        desc = QLabel(
            "📸 Select a profile to match your live detection camera's quality "
            "(brightness, contrast, noise, blur). "
            "The profile is applied to each captured image <b>locally</b> "
            "before the images are sent to the API — improving recognition accuracy."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#94a3b8; font-size:13px; font-weight:normal; margin-bottom:8px;")
        layout.addWidget(desc)

        # Profile selector row
        row = QHBoxLayout()
        lbl = QLabel("Select Profile:")
        lbl.setStyleSheet("color:#fff; font-size:14px; font-weight:bold;")

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumHeight(40)
        self.profile_combo.setMinimumWidth(300)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.setStyleSheet("""
            QPushButton { background-color:#333; color:#fff; border:none;
                          padding:8px 16px; border-radius:6px; font-weight:bold; }
            QPushButton:hover { background-color:#444; }
        """)
        refresh_btn.clicked.connect(self._load_profile_dropdown)

        row.addWidget(lbl)
        row.addWidget(self.profile_combo)
        row.addWidget(refresh_btn)
        row.addStretch()
        layout.addLayout(row)

        self.profile_status_label = QLabel("No profile selected — images sent as-is")
        self.profile_status_label.setStyleSheet("color:#64748b; font-size:12px; margin-top:4px;")
        layout.addWidget(self.profile_status_label)

        # Info box
        info = QFrame()
        info.setStyleSheet("""
            QFrame { background-color:#1a1a1a; border:1px solid #333;
                     border-radius:8px; padding:10px; margin-top:8px; }
        """)
        info_layout = QVBoxLayout(info)
        info_title = QLabel("ℹ️ How it works:")
        info_title.setStyleSheet("color:#ffc107; font-size:13px; font-weight:bold;")
        info_layout.addWidget(info_title)
        info_text = QLabel(
            "① Profile loaded from camera_profiles/<id>_profile.pkl\n"
            "② Each captured / uploaded frame is processed through the profile\n"
            "③ Quality-matched image is sent to the API — NOT the raw frame\n"
            "④ Result: embeddings at registration match embeddings at detection"
        )
        info_text.setStyleSheet("color:#94a3b8; font-size:12px; font-weight:normal;")
        info_layout.addWidget(info_text)
        layout.addWidget(info)

        self._load_profile_dropdown()
        return group

    def _build_capture_section(self):
        group = QGroupBox("Face Capture")
        group.setStyleSheet("""
            QGroupBox {
                background-color:#222; border:1px solid #333;
                border-radius:12px; padding:20px; margin-top:10px;
                font-size:16px; font-weight:bold; color:#fff;
            }
        """)
        layout = QVBoxLayout(group)

        self.instructions_label = QLabel(
            "Position your face in the frame and click 'Start Capture'. "
            f"{self.target_captures} images will be captured automatically."
        )
        self.instructions_label.setWordWrap(True)
        self.instructions_label.setStyleSheet(
            "color:#94a3b8; font-size:14px; font-weight:normal;"
        )
        layout.addWidget(self.instructions_label)

        # ── Upload widget ───────────────────────────────────────────────
        self.upload_widget = QWidget()
        ul = QVBoxLayout(self.upload_widget)

        upload_info = QLabel(
            "Upload exactly 5 clear face images from different angles.\n"
            "• Good lighting  • Single face per image  • Face clearly visible"
        )
        upload_info.setStyleSheet("color:#94a3b8; font-size:13px; margin:8px 0;")
        ul.addWidget(upload_info)

        self.upload_button = QPushButton("📁 Select 5 Images")
        self.upload_button.setMinimumHeight(50)
        self.upload_button.setStyleSheet("""
            QPushButton { background-color:#3b82f6; color:#fff; border:none;
                          padding:15px; border-radius:8px;
                          font-weight:bold; font-size:14px; }
            QPushButton:hover { background-color:#2563eb; }
        """)
        self.upload_button.clicked.connect(self.upload_images)
        ul.addWidget(self.upload_button)

        self.upload_status_label = QLabel("No images selected")
        self.upload_status_label.setStyleSheet("color:#64748b; font-size:13px;")
        ul.addWidget(self.upload_status_label)

        layout.addWidget(self.upload_widget)
        self.upload_widget.hide()

        # ── Camera widget ───────────────────────────────────────────────
        self.camera_widget = QWidget()
        cl = QVBoxLayout(self.camera_widget)

        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setMaximumSize(640, 480)
        self.camera_label.setStyleSheet("background-color:#000; border-radius:8px;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.camera_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.camera_widget)

        # ── Progress + status ───────────────────────────────────────────
        pr_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            "color:#64748b; font-size:14px; font-weight:normal;"
        )
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(self.target_captures)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m captures")
        pr_row.addWidget(self.status_label)
        pr_row.addStretch()
        pr_row.addWidget(self.progress_bar)
        layout.addLayout(pr_row)

        # ── Preview grid ────────────────────────────────────────────────
        self.preview_grid = QGridLayout()
        self.preview_grid.setSpacing(10)
        self.preview_labels = []
        for i in range(self.target_captures):
            lbl = QLabel()
            lbl.setFixedSize(100, 100)
            lbl.setStyleSheet(
                "border:2px dashed #444; border-radius:8px; background-color:#1a1a1a;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            self.preview_labels.append(lbl)
            self.preview_grid.addWidget(lbl, 0, i)
        layout.addLayout(self.preview_grid)

        # ── Camera control buttons ──────────────────────────────────────
        ctrl = QHBoxLayout()
        self.start_camera_btn = QPushButton("Start Camera")
        self.start_camera_btn.clicked.connect(self.start_camera)

        self.capture_btn = QPushButton("Start Capture")
        self.capture_btn.setEnabled(False)
        self.capture_btn.clicked.connect(self.start_capture)

        self.stop_capture_btn = QPushButton("Stop Capture")
        self.stop_capture_btn.setEnabled(False)
        self.stop_capture_btn.clicked.connect(self.stop_capture)

        ctrl.addStretch()
        ctrl.addWidget(self.start_camera_btn)
        ctrl.addWidget(self.capture_btn)
        ctrl.addWidget(self.stop_capture_btn)
        layout.addLayout(ctrl)

        return group

    def _build_details_section(self):
        group = QGroupBox("User Details")
        group.setStyleSheet("""
            QGroupBox {
                background-color:#222; border:1px solid #333;
                border-radius:12px; padding:20px; margin-top:10px;
                font-size:16px; font-weight:bold; color:#fff;
            }
        """)
        layout = QFormLayout(group)
        layout.setSpacing(15)

        self.name_input       = QLineEdit(); self.name_input.setPlaceholderText("Full name (required)");       self.name_input.setMinimumHeight(40)
        self.email_input      = QLineEdit(); self.email_input.setPlaceholderText("Email address");             self.email_input.setMinimumHeight(40)
        self.phone_input      = QLineEdit(); self.phone_input.setPlaceholderText("Phone number");              self.phone_input.setMinimumHeight(40)
        self.department_input = QLineEdit(); self.department_input.setPlaceholderText("Department");           self.department_input.setMinimumHeight(40)
        self.role_combo       = QComboBox(); self.role_combo.addItems(["Employee","Admin","Student","Visitor"]); self.role_combo.setMinimumHeight(40)

        layout.addRow("Name*:",       self.name_input)
        layout.addRow("Email:",       self.email_input)
        layout.addRow("Phone:",       self.phone_input)
        layout.addRow("Department:",  self.department_input)
        layout.addRow("Role*:",       self.role_combo)
        return group

    # ══════════════════════════════════════════
    #  SOURCE SWITCHING
    # ══════════════════════════════════════════

    def on_source_changed(self, mode):
        self.source_mode = mode
        self._reset_captures()

        if mode == "camera":
            self.camera_radio.setChecked(True)
            self.upload_radio.setChecked(False)
            self.camera_widget.show()
            self.upload_widget.hide()
            self.instructions_label.setText(
                "Position your face in the frame and click 'Start Capture'. "
                f"{self.target_captures} images will be captured automatically."
            )
        else:
            self.upload_radio.setChecked(True)
            self.camera_radio.setChecked(False)
            self.upload_widget.show()
            self.camera_widget.hide()
            self.instructions_label.setText(
                f"Upload exactly {self.target_captures} clear face images."
            )
            if self.camera_worker:
                self.stop_camera_completely()

    def _reset_captures(self):
        self.captured_images = []
        self.progress_bar.setValue(0)
        self.register_button.setEnabled(False)
        self.upload_status_label.setText("No images selected")
        for lbl in self.preview_labels:
            lbl.clear()
            lbl.setStyleSheet(
                "border:2px dashed #444; border-radius:8px; background-color:#1a1a1a;"
            )

    # ══════════════════════════════════════════
    #  CAMERA
    # ══════════════════════════════════════════

    def start_camera(self):
        try:
            self.camera_worker = RegistrationCameraWorker(0, None)
            self.camera_worker.frame_ready.connect(self.on_frame_ready)
            self.camera_worker.error_occurred.connect(self.on_camera_error)
            self.camera_worker.start()
            self.start_camera_btn.setEnabled(False)
            self.capture_btn.setEnabled(True)
            self.status_label.setText("Camera started — position your face")
        except Exception as e:
            QMessageBox.critical(self, "Camera Error", str(e))

    def on_frame_ready(self, frame, *args):
        self.current_frame = frame
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        q_img = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self.camera_label.setPixmap(
            pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def on_camera_error(self, msg):
        QMessageBox.critical(self, "Camera Error", msg)

    def start_capture(self):
        self._reset_captures()
        self.is_capturing = True
        self.capture_btn.setEnabled(False)
        self.stop_capture_btn.setEnabled(True)
        self.status_label.setText("Capturing…")
        self.status_label.setStyleSheet("color:#ffc107; font-size:14px; font-weight:bold;")
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self._grab_frame)
        self.capture_timer.start(1000)

    def _grab_frame(self):
        if not self.is_capturing or self.current_frame is None:
            return

        frame_copy = self.current_frame.copy()

        # ── Step 1: Detect + align → 300x300 crop ──────────────────────
        success, crop, message = self._extract_300_crop(frame_copy)
        if not success:
            self.status_label.setText(f"⚠️ {message}")
            self.status_label.setStyleSheet("color:#f97316; font-size:13px;")
            return  # skip this tick, try again next second

        # ── Step 2: Apply quality profile on the 300x300 crop ──────────
        processed = self._apply_quality(crop)

        # ── Step 3: Store + update UI ───────────────────────────────────
        self.captured_images.append(processed)
        count = len(self.captured_images)
        self.progress_bar.setValue(count)
        self.status_label.setText(f"✓ Captured {count}/{self.target_captures}")
        self.status_label.setStyleSheet("color:#22c55e; font-size:13px; font-weight:bold;")
        self._show_preview(count - 1, processed)

        if count >= self.target_captures:
            self.stop_capture()
            self.status_label.setText(f"✓ {count} face crops ready — click Register")
            self.status_label.setStyleSheet("color:#22c55e; font-size:14px; font-weight:bold;")
            self.register_button.setEnabled(True)

    def stop_capture(self):
        self.is_capturing = False
        if self.capture_timer:
            self.capture_timer.stop()
            self.capture_timer = None
        self.capture_btn.setEnabled(True)
        self.stop_capture_btn.setEnabled(False)

    def stop_camera_completely(self):
        self.stop_capture()
        if self.camera_worker:
            self.camera_worker.stop()
            self.camera_worker.wait()
            self.camera_worker = None
        self.camera_label.clear()
        self.camera_label.setText("Camera Stopped")
        self.camera_label.setStyleSheet(
            "background-color:#000; border-radius:8px; color:#666; font-size:18px;"
        )
        self.current_frame = None
        self.start_camera_btn.setEnabled(True)
        self.capture_btn.setEnabled(False)
        self.stop_capture_btn.setEnabled(False)

    # ══════════════════════════════════════════
    #  IMAGE UPLOAD
    # ══════════════════════════════════════════

    def upload_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select 5 Face Images", "",
            "Images (*.jpg *.jpeg *.png *.bmp);;All Files (*)"
        )
        if not paths:
            return
        if len(paths) != self.target_captures:
            QMessageBox.warning(
                self, "Wrong Count",
                f"Please select exactly {self.target_captures} images.\n"
                f"You selected {len(paths)}."
            )
            return

        self.upload_button.setEnabled(False)
        self.upload_status_label.setText("Loading images…")
        self.upload_status_label.setStyleSheet("color:#ffc107; font-size:13px;")

        images = []
        for i, p in enumerate(paths):
            img = cv2.imread(p)
            if img is None:
                QMessageBox.critical(self, "Load Error", f"Cannot load:\n{p}")
                self.upload_button.setEnabled(True)
                self.upload_status_label.setText("Failed — try again")
                return

            # ── Step 1: Detect + align → 300x300 crop ──────────────
            success, crop, message = self._extract_300_crop(img)
            if not success:
                QMessageBox.critical(
                    self, "Face Not Found",
                    f"Image {i+1} ({os.path.basename(p)}):\n{message}\n\n"
                    "Please use a clear photo with one visible face."
                )
                self.upload_button.setEnabled(True)
                self.upload_status_label.setText("Failed — try again")
                return

            # ── Step 2: Apply quality profile on 300x300 crop ──────
            processed = self._apply_quality(crop)

            images.append(processed)
            self._show_preview(i, processed)

        self.captured_images = images
        self.progress_bar.setValue(len(images))
        self.upload_status_label.setText(
            f"✓ {len(images)} images loaded"
        )
        self.upload_status_label.setStyleSheet(
            "color:#22c55e; font-size:13px; font-weight:bold;"
        )
        self.upload_button.setEnabled(True)
        self.register_button.setEnabled(True)

    # ══════════════════════════════════════════
    #  PREVIEW HELPER
    # ══════════════════════════════════════════

    def _show_preview(self, index: int, bgr_frame: np.ndarray):
        if index >= len(self.preview_labels):
            return
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img).scaled(
            100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_labels[index].setPixmap(pixmap)
        self.preview_labels[index].setStyleSheet(
            "border:2px solid #22c55e; border-radius:8px; background-color:#1a1a1a;"
        )

    # ══════════════════════════════════════════
    #  REGISTRATION  (API call)
    # ══════════════════════════════════════════

    def register_face(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a name.")
            return
        if len(self.captured_images) < self.target_captures:
            QMessageBox.warning(
                self, "Not Enough Images",
                f"Need {self.target_captures} face images, "
                f"have {len(self.captured_images)}."
            )
            return

        user_data = {
            "name":       name,
            "email":      self.email_input.text().strip()      or "",
            "phone":      self.phone_input.text().strip()      or "",
            "department": self.department_input.text().strip() or "",
            "role":       self.role_combo.currentText(),
            "threshold":  0.80,
        }

        # ── Disable UI while request is in flight ─────────────────────
        self.register_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.status_label.setText("⏳ Sending to API…")
        self.status_label.setStyleSheet("color:#ffc107; font-size:14px; font-weight:bold;")
        self.api_status_label.setText(f"🌐 Posting to {_get_register_endpoint()} …")

        # ── Launch background worker ───────────────────────────────────
        self._api_worker = RegistrationAPIWorker(
            self.captured_images[:self.target_captures], user_data
        )
        self._api_worker.success.connect(self._on_api_success)
        self._api_worker.duplicate.connect(self._on_api_duplicate)
        self._api_worker.failed.connect(self._on_api_failed)
        self._api_worker.start()

    def _on_api_success(self, data: dict):
        user_id = data.get("user_id", "?")
        name    = self.name_input.text().strip()

        self.status_label.setText("✅ Registered successfully!")
        self.status_label.setStyleSheet("color:#22c55e; font-size:14px; font-weight:bold;")
        self.api_status_label.setText(f"🌐 API: {_get_api_base()}")

        self._show_success_dialog(user_id, name, data.get("message", ""))
        self.registration_completed.emit(user_id, name)
        self.reset_form()

    def _on_api_duplicate(self, data: dict):
        self.status_label.setText("❌ Duplicate detected")
        self.status_label.setStyleSheet("color:#ef4444; font-size:14px; font-weight:bold;")
        self.api_status_label.setText(f"🌐 API: {_get_api_base()}")

        dlg = DuplicateUserDialog(data, self)
        dlg.exec()
        self.reset_form()

    def _on_api_failed(self, error_msg: str):
        self.status_label.setText("❌ Registration failed")
        self.status_label.setStyleSheet("color:#ef4444; font-size:14px; font-weight:bold;")
        self.api_status_label.setText(f"🌐 API: {_get_api_base()}")
        self.register_button.setEnabled(True)
        self.reset_button.setEnabled(True)

        QMessageBox.critical(self, "Registration Failed", error_msg)

    # ══════════════════════════════════════════
    #  SUCCESS DIALOG
    # ══════════════════════════════════════════

    def _show_success_dialog(self, user_id: str, name: str, message: str):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Registration Successful! 🎉")
        msg.setText(
            "<h2 style='color:#22c55e;'>✅ Face Registered Successfully!</h2>"
            f"<p style='color:#94a3b8;'>{message}</p>"
        )
        details = f"""
        <div style='background:#1a1a1a; padding:12px; border-radius:8px;'>
            <table style='width:100%;'>
                <tr>
                    <td style='color:#ffc107; font-weight:bold; width:110px;'>User ID:</td>
                    <td style='color:#fff;'>{user_id}</td>
                </tr>
                <tr>
                    <td style='color:#ffc107; font-weight:bold;'>Name:</td>
                    <td style='color:#fff;'>{name}</td>
                </tr>
                <tr>
                    <td style='color:#ffc107; font-weight:bold;'>Role:</td>
                    <td style='color:#fff;'>{self.role_combo.currentText()}</td>
                </tr>
            </table>
            <hr style='border:1px solid #333; margin:12px 0;'>
            <p style='color:#22c55e; font-weight:bold;'>✓ Registration confirmed by server</p>
        </div>
        """
        msg.setInformativeText(details)
        ok = msg.addButton("Done", QMessageBox.AcceptRole)
        ok.setStyleSheet("""
            QPushButton { background-color:#22c55e; color:#000;
                          padding:10px 30px; border-radius:6px;
                          font-weight:bold; font-size:14px; min-width:100px; }
            QPushButton:hover { background-color:#16a34a; }
        """)
        msg.exec()

    # ══════════════════════════════════════════
    #  RESET / CLEANUP
    # ══════════════════════════════════════════

    def reset_form(self):
        self.name_input.clear()
        self.email_input.clear()
        self.phone_input.clear()
        self.department_input.clear()
        self.role_combo.setCurrentIndex(0)
        self._reset_captures()
        self.register_button.setEnabled(False)
        self.reset_button.setEnabled(True)
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color:#64748b; font-size:14px;")

    def cleanup(self):
        self.stop_capture()
        if self.camera_worker:
            self.camera_worker.stop()
            self.camera_worker = None
        self.current_frame = None

    def showEvent(self, event):
        super().showEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.cleanup()