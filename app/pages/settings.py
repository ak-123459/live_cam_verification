"""
Settings Page — FRS / Surveillance System
==========================================
Matches the existing dark UI theme (#1a1a1a bg, #ffc107 accent, #222 cards).
All settings read from / written to:
  • .env          → runtime overrides (API, paths, basic flags)
  • camera_config.yaml → structured pipeline settings

Sections:
  1. Stream & Camera   — PyAV, resolution, frame skip
  2. Recognition       — thresholds, cooldown, max faces
  3. Storage           — capture paths, JPEG quality, queue sizes
  4. API / Network     — host, port, timeout, batch watcher
  5. Advanced          — dedup, embedding similarity, PyAV FFmpeg flags
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QMessageBox, QGroupBox, QGridLayout,
    QSizePolicy, QSlider,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

load_dotenv()

# ── Path to .env file ─────────────────────────────────────────────────────────
_ENV_PATH = Path(".env")



# ─────────────────────────────────────────────────────────────────────────────
# Reusable styled widgets
# ─────────────────────────────────────────────────────────────────────────────

_CARD_STYLE = """
    QFrame#card {
        background-color: #222222;
        border: 1px solid #333333;
        border-radius: 12px;
    }
"""

_GROUP_STYLE = """
    QGroupBox {
        background-color: #1e1e1e;
        border: 1px solid #333333;
        border-radius: 10px;
        margin-top: 14px;
        padding: 16px 12px 12px 12px;
        font-size: 13px;
        font-weight: bold;
        color: #ffc107;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        top: -2px;
        padding: 0 6px;
        background-color: #1e1e1e;
    }
"""

_INPUT_STYLE = """
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #2a2a2a;
        color: #ffffff;
        border: 1px solid #444444;
        border-radius: 6px;
        padding: 7px 10px;
        font-size: 13px;
        min-height: 32px;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border: 1px solid #ffc107;
    }
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        background-color: #333;
        border: none;
        width: 18px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #2a2a2a;
        color: #fff;
        selection-background-color: #ffc107;
        selection-color: #111;
    }
"""

_SLIDER_STYLE = """
    QSlider::groove:horizontal {
        height: 6px;
        background: #333;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #ffc107;
        border: none;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }
    QSlider::sub-page:horizontal {
        background: #ffc107;
        border-radius: 3px;
    }
"""

_CHECK_STYLE = """
    QCheckBox { color: #ccc; font-size: 13px; }
    QCheckBox::indicator {
        width: 18px; height: 18px;
        border: 2px solid #444;
        border-radius: 4px;
        background: #2a2a2a;
    }
    QCheckBox::indicator:checked {
        background: #ffc107;
        border-color: #ffc107;
        image: none;
    }
"""


def _label(text: str, color="#94a3b8", bold=False, size=13) -> QLabel:
    lbl = QLabel(text)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{weight};")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #333333; background-color: #333333;")
    line.setFixedHeight(1)
    return line


def _section_header(title: str, icon: str = "") -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 4)
    lbl = QLabel(f"{icon}  {title}" if icon else title)
    lbl.setStyleSheet(
        "color: #ffc107; font-size: 15px; font-weight: bold; letter-spacing: 0.5px;"
    )
    lay.addWidget(lbl)
    lay.addStretch()
    return w


# ─────────────────────────────────────────────────────────────────────────────
# Row builder helpers
# ─────────────────────────────────────────────────────────────────────────────

class _Row(QWidget):
    """Label + widget side-by-side, with optional tooltip."""

    def __init__(self, label: str, widget: QWidget, tip: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #cccccc; font-size: 13px;")
        lbl.setMinimumWidth(220)
        if tip:
            lbl.setToolTip(tip)
            widget.setToolTip(tip)

        lay.addWidget(lbl)
        lay.addWidget(widget, 1)

    @staticmethod
    def spin(min_: int, max_: int, val: int, step: int = 1) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_, max_)
        s.setValue(val)
        s.setSingleStep(step)
        s.setStyleSheet(_INPUT_STYLE)
        return s

    @staticmethod
    def dspin(min_: float, max_: float, val: float,
              step: float = 0.01, decimals: int = 2) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_, max_)
        s.setValue(val)
        s.setSingleStep(step)
        s.setDecimals(decimals)
        s.setStyleSheet(_INPUT_STYLE)
        return s

    @staticmethod
    def line(val: str = "", placeholder: str = "") -> QLineEdit:
        e = QLineEdit(val)
        if placeholder:
            e.setPlaceholderText(placeholder)
        e.setStyleSheet(_INPUT_STYLE)
        return e

    @staticmethod
    def combo(items: list[str], current: str = "") -> QComboBox:
        c = QComboBox()
        c.addItems(items)
        idx = c.findText(current)
        if idx >= 0:
            c.setCurrentIndex(idx)
        c.setStyleSheet(_INPUT_STYLE)
        return c

    @staticmethod
    def check(checked: bool = False) -> QCheckBox:
        cb = QCheckBox()
        cb.setChecked(checked)
        cb.setStyleSheet(_CHECK_STYLE)
        return cb

    @staticmethod
    def slider(min_: int, max_: int, val: int) -> tuple[QSlider, QLabel]:
        sl = QSlider(Qt.Horizontal)
        sl.setRange(min_, max_)
        sl.setValue(val)
        sl.setStyleSheet(_SLIDER_STYLE)
        indicator = QLabel(str(val))
        indicator.setStyleSheet("color:#ffc107; font-size:13px; min-width:36px;")
        indicator.setAlignment(Qt.AlignCenter)
        sl.valueChanged.connect(lambda v: indicator.setText(str(v)))
        return sl, indicator


# ─────────────────────────────────────────────────────────────────────────────
# Settings Page
# ─────────────────────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    """
    Full settings page — matches existing dark FRS UI theme.
    Call  settings_page.settings_saved.emit()  to react to saves.
    """

    settings_saved = Signal()   # emitted after successful save

    def __init__(self, parent=None):
        super().__init__(parent)
        self._env = dotenv_values(_ENV_PATH) if _ENV_PATH.exists() else {}
        self._widgets: dict[str, QWidget] = {}   # key → widget for save
        self._setup_ui()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _env_str(self, key: str, default: str = "") -> str:
        return self._env.get(key, os.getenv(key, default))

    def _env_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._env.get(key, os.getenv(key, str(default))))
        except (ValueError, TypeError):
            return default

    def _env_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self._env.get(key, os.getenv(key, str(default))))
        except (ValueError, TypeError):
            return default

    def _env_bool(self, key: str, default: bool = False) -> bool:
        v = self._env.get(key, os.getenv(key, str(default))).lower()
        return v in ("true", "1", "yes")

    # ── UI construction ──────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        # ── Page header ───────────────────────────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("⚙  Settings")
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#fff;")
        sub = QLabel("Configure stream, recognition and storage parameters")
        sub.setStyleSheet("color:#64748b; font-size:13px;")

        save_btn = self._primary_btn("💾  Save All Changes")
        save_btn.setFixedWidth(200)
        save_btn.clicked.connect(self._save)

        reset_btn = self._secondary_btn("↺  Reset to Defaults")
        reset_btn.setFixedWidth(180)
        reset_btn.clicked.connect(self._reset_defaults)

        hdr_text = QVBoxLayout()
        hdr_text.addWidget(title)
        hdr_text.addWidget(sub)

        header_row.addLayout(hdr_text)
        header_row.addStretch()
        header_row.addWidget(reset_btn)
        header_row.addSpacing(10)
        header_row.addWidget(save_btn)
        root.addLayout(header_row)
        root.addSpacing(16)
        root.addWidget(_divider())
        root.addSpacing(16)

        # ── Scrollable content ────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { background:#1a1a1a; width:8px; border-radius:4px; }
            QScrollBar::handle:vertical { background:#444; border-radius:4px; min-height:30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 12, 0)
        content_lay.setSpacing(20)

        content_lay.addWidget(self._section_stream())
        content_lay.addWidget(self._section_recognition())
        content_lay.addWidget(self._section_storage())
        content_lay.addWidget(self._section_api())
        content_lay.addWidget(self._section_advanced())
        content_lay.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

        # ── Bottom save bar ───────────────────────────────────────────────
        root.addSpacing(12)
        root.addWidget(_divider())
        root.addSpacing(10)

        bottom = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#64748b; font-size:12px;")
        bottom.addWidget(self._status_lbl)
        bottom.addStretch()

        save2 = self._primary_btn("💾  Save All Changes")
        save2.setFixedWidth(200)
        save2.clicked.connect(self._save)
        bottom.addWidget(save2)
        root.addLayout(bottom)

    # ── Section builders ─────────────────────────────────────────────────────

    def _section_stream(self) -> QWidget:
        card = self._card()
        lay = card.layout()
        lay.addWidget(_section_header("Stream & Camera", "📹"))
        lay.addWidget(_divider())
        lay.addSpacing(8)

        # Process every N frames
        w = _Row.spin(1, 30, self._env_int("PROCESS_N_FRAME", 5))
        self._widgets["PROCESS_N_FRAME"] = w
        lay.addWidget(_Row("Process every N frames",  w,
            "1 = every frame (slow), 5 = every 5th (recommended)"))

        # Resize width
        w = _Row.spin(160, 1920, self._env_int("RESIZE_WIDTH", 640), 32)
        self._widgets["RESIZE_WIDTH"] = w
        lay.addWidget(_Row("Processing width (px)", w,
            "Frames are resized to this before detection"))

        # Max frame queue
        w = _Row.spin(1, 16, self._env_int("MAX_FRAME_QUEUE", 2))
        self._widgets["MAX_FRAME_QUEUE"] = w
        lay.addWidget(_Row("Frame queue size", w,
            "Larger = smoother but adds latency"))

        lay.addSpacing(6)
        lay.addWidget(_label("PyAV / FFmpeg", "#ffc107", bold=True))
        lay.addSpacing(4)

        # Thread type
        w = _Row.combo(["slice", "frame", "auto", "none"],
                       self._env_str("PYAV_THREAD_TYPE", "slice"))
        self._widgets["PYAV_THREAD_TYPE"] = w
        lay.addWidget(_Row("PyAV thread type", w,
            "slice = best for MJPEG, frame = best for H264"))

        # Thread count
        w = _Row.spin(0, 16, self._env_int("PYAV_THREAD_COUNT", 0))
        self._widgets["PYAV_THREAD_COUNT"] = w
        lay.addWidget(_Row("PyAV thread count (0=auto)", w))

        # Ring buffer
        w = _Row.line(self._env_str("PYAV_RTBUF", "256k"), "e.g. 256k")
        self._widgets["PYAV_RTBUF"] = w
        lay.addWidget(_Row("Ring buffer size", w,
            "Keep small for low latency"))

        # Pixel format
        w = _Row.combo(["bgr24", "yuv420p"],
                       self._env_str("PYAV_PIXEL_FMT", "bgr24"))
        self._widgets["PYAV_PIXEL_FMT"] = w
        lay.addWidget(_Row("Pixel format", w,
            "bgr24 = cv2 ready, yuv420p = faster decode"))

        # Analyze duration
        w = _Row.spin(10000, 5000000, self._env_int("PYAV_ANALYZE_DURATION", 100000), 10000)
        self._widgets["PYAV_ANALYZE_DURATION"] = w
        lay.addWidget(_Row("Analyze duration (µs)", w,
            "Lower = faster startup, less reliable detection"))

        # Probe size
        w = _Row.spin(4096, 5000000, self._env_int("PYAV_PROBE_SIZE", 32768), 4096)
        self._widgets["PYAV_PROBE_SIZE"] = w
        lay.addWidget(_Row("Probe size (bytes)", w))

        return card

    def _section_recognition(self) -> QWidget:
        card = self._card()
        lay = card.layout()
        lay.addWidget(_section_header("Face Recognition", "🎯"))
        lay.addWidget(_divider())
        lay.addSpacing(8)

        # Match threshold  (with live slider)
        thresh_val = self._env_float("FACE_THRESHOLD", 0.20)
        sl, indicator = _Row.slider(0, 100, int(thresh_val * 100))
        self._widgets["FACE_THRESHOLD"] = sl
        row_w = QWidget()
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.addWidget(sl, 1)
        row_lay.addSpacing(8)
        row_lay.addWidget(indicator)
        lay.addWidget(_Row("Match threshold", row_w,
            "Higher = stricter. Default 0.20 (shown as 20)"))

        # Front face confidence
        w = _Row.dspin(0.0, 1.0, self._env_float("FRONT_FACE_THRESH", 0.50), 0.05)
        self._widgets["FRONT_FACE_THRESH"] = w
        lay.addWidget(_Row("Front-face confidence", w,
            "Minimum pose confidence to accept a face"))

        # Max faces
        w = _Row.spin(1, 100, self._env_int("MAX_FACES", 20))
        self._widgets["MAX_FACES"] = w
        lay.addWidget(_Row("Max faces per frame", w))

        # Unknown cooldown
        w = _Row.dspin(1.0, 300.0, self._env_float("UNKNOWN_COOLDOWN_SEC", 10.0), 1.0, 1)
        self._widgets["UNKNOWN_COOLDOWN_SEC"] = w
        lay.addWidget(_Row("Unknown save cooldown (sec)", w,
            "Seconds between saving the same unknown face"))

        # Embedding min similarity
        w = _Row.dspin(0.50, 1.0, self._env_float("EMBEDDING_MIN_SIMILARITY", 0.85), 0.01)
        self._widgets["EMBEDDING_MIN_SIMILARITY"] = w
        lay.addWidget(_Row("Embedding dedup similarity", w,
            "How similar embeddings must be to count as duplicate"))

        # Recognition threshold (batch API)
        w = _Row.dspin(0.0, 1.0, self._env_float("MATCH_THRESHOLD", 0.40), 0.05)
        self._widgets["MATCH_THRESHOLD"] = w
        lay.addWidget(_Row("Batch API match threshold", w,
            "Used by the attendance batch recognition API"))

        # ArcFace model
        w = _Row.combo(
            ["buffalo_s_int8", "buffalo_sc", "buffalo_l", "antelopev2"],
            self._env_str("ARC_FACE_MODEL", "buffalo_s_int8")
        )
        self._widgets["ARC_FACE_MODEL"] = w
        lay.addWidget(_Row("ArcFace model", w,
            "Larger models are more accurate but slower"))

        return card

    def _section_storage(self) -> QWidget:
        card = self._card()
        lay = card.layout()
        lay.addWidget(_section_header("Storage & Capture", "💾"))
        lay.addWidget(_divider())
        lay.addSpacing(8)

        # Unknown captures root
        w = _Row.line(self._env_str("UNKNOWN_CAPTURES_ROOT", "captures/unknown"),
                      "path/to/folder")
        self._widgets["UNKNOWN_CAPTURES_ROOT"] = w
        lay.addWidget(_Row("Unknown captures folder", w))

        # Known captures root
        w = _Row.line(self._env_str("KNOWN_CAPTURES_ROOT", "captures/known"),
                      "path/to/folder")
        self._widgets["KNOWN_CAPTURES_ROOT"] = w
        lay.addWidget(_Row("Known captures folder", w))

        # JPEG quality  (slider)
        jpeg_val = self._env_int("JPEG_QUALITY", 90)
        sl, indicator = _Row.slider(10, 100, jpeg_val)
        self._widgets["JPEG_QUALITY"] = sl
        row_w = QWidget()
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.addWidget(sl, 1)
        row_lay.addSpacing(8)
        row_lay.addWidget(indicator)
        lay.addWidget(_Row("JPEG save quality", row_w,
            "Higher = better quality, larger files"))

        # Max save queue
        w = _Row.spin(1, 200, self._env_int("MAX_SAVE_QUEUE", 20))
        self._widgets["MAX_SAVE_QUEUE"] = w
        lay.addWidget(_Row("Save queue size", w,
            "Max pending saves before oldest is dropped"))

        # Dedup history
        w = _Row.spin(1, 100, self._env_int("DEDUP_HISTORY_SIZE", 10))
        self._widgets["DEDUP_HISTORY_SIZE"] = w
        lay.addWidget(_Row("Dedup history size", w,
            "How many last embeddings to keep per identity"))

        # FAISS paths
        lay.addSpacing(6)
        lay.addWidget(_label("FAISS Index Paths", "#ffc107", bold=True))
        lay.addSpacing(4)

        w = _Row.line(self._env_str("ATTENDANCE_FAISS_INDEX_PATH",
                      "batch_recognition_api/data/verify_face_vectors/faiss.index"))
        self._widgets["ATTENDANCE_FAISS_INDEX_PATH"] = w
        lay.addWidget(_Row("FAISS index path", w))

        w = _Row.line(self._env_str("ATTENDANCE_FAISS_META_PATH",
                      "batch_recognition_api/data/verify_face_vectors/faiss_meta.pkl"))
        self._widgets["ATTENDANCE_FAISS_META_PATH"] = w
        lay.addWidget(_Row("FAISS metadata path", w))

        return card

    def _section_api(self) -> QWidget:
        card = self._card()
        lay = card.layout()
        lay.addWidget(_section_header("API & Network", "🌐"))
        lay.addWidget(_divider())
        lay.addSpacing(8)

        # API host
        w = _Row.line(self._env_str("API_HOST", "127.0.0.1"), "127.0.0.1 or ::1")
        self._widgets["API_HOST"] = w
        lay.addWidget(_Row("API host", w))

        # API port
        w = _Row.spin(1, 65535, self._env_int("API_PORT", 8004))
        self._widgets["API_PORT"] = w
        lay.addWidget(_Row("API port", w))

        # API timeout
        w = _Row.spin(1, 300, self._env_int("API_TIMEOUT", 30))
        self._widgets["API_TIMEOUT"] = w
        lay.addWidget(_Row("API timeout (sec)", w))

        lay.addSpacing(6)
        lay.addWidget(_label("Attendance Batch Watcher", "#ffc107", bold=True))
        lay.addSpacing(4)

        # Watch dir
        w = _Row.line(self._env_str("WATCH_DIR", "./captures/unknown"), "path to watch")
        self._widgets["WATCH_DIR"] = w
        lay.addWidget(_Row("Watch directory", w))

        # Batch API URL
        w = _Row.line(self._env_str("API_URL", "http://[::1]:8004/attendance/batch"))
        self._widgets["API_URL"] = w
        lay.addWidget(_Row("Batch API URL", w))

        # Interval
        w = _Row.spin(1, 300, self._env_int("INTERVAL", 5))
        self._widgets["INTERVAL"] = w
        lay.addWidget(_Row("Watcher interval (sec)", w))

        # Max batch
        w = _Row.spin(1, 200, self._env_int("MAX_BATCH", 20))
        self._widgets["MAX_BATCH"] = w
        lay.addWidget(_Row("Max batch size", w))

        # Camera ID
        w = _Row.line(self._env_str("CAMERA_ID", "CAM_01"))
        self._widgets["CAMERA_ID"] = w
        lay.addWidget(_Row("Camera ID", w,
            "Identifier sent with batch attendance requests"))

        return card

    def _section_advanced(self) -> QWidget:
        card = self._card()
        lay = card.layout()
        lay.addWidget(_section_header("Advanced", "🔧"))
        lay.addWidget(_divider())
        lay.addSpacing(8)

        # Embedding dedup distance
        w = _Row.dspin(0.01, 1.0, self._env_float("EMBEDDING_DEDUP_DISTANCE", 0.15), 0.01)
        self._widgets["EMBEDDING_DEDUP_DISTANCE"] = w
        lay.addWidget(_Row("Embedding dedup distance", w,
            "0.15 = skip if >85% similar to last saved. Lower = stricter dedup"))

        # Detection size
        det_str = self._env_str("DET_SIZE", "640,384")
        w = _Row.line(det_str, "width,height  e.g. 640,384")
        self._widgets["DET_SIZE"] = w
        lay.addWidget(_Row("Detection size (W,H)", w,
            "InsightFace detection input size. Restart required."))

        # Detection threshold
        w = _Row.dspin(0.1, 1.0, self._env_float("DET_THRESH", 0.3), 0.05)
        self._widgets["DET_THRESH"] = w
        lay.addWidget(_Row("Detection threshold", w,
            "InsightFace face detection confidence cutoff"))

        # Max recog queue
        w = _Row.spin(1, 100, self._env_int("SAVE_QUEUE", 20))
        self._widgets["SAVE_QUEUE"] = w
        lay.addWidget(_Row("Recognition queue size", w))

        # Model path
        w = _Row.line(self._env_str("EMB_MODEL_PATH",
                      "batch_recognition_api/models/w600k_r50_int8.onnx"))
        self._widgets["EMB_MODEL_PATH"] = w
        lay.addWidget(_Row("Embedding model path", w))

        # SQL DB path
        w = _Row.line(self._env_str("ATTENDANCE_SQL_DB_PATH",
                      "database_server/face_recognition.db"))
        self._widgets["ATTENDANCE_SQL_DB_PATH"] = w
        lay.addWidget(_Row("Attendance SQL DB path", w))

        # Watchlist events root
        w = _Row.line(self._env_str("WATCHLIST_EVENTS_ROOT", "watchlist_events"))
        self._widgets["WATCHLIST_EVENTS_ROOT"] = w
        lay.addWidget(_Row("Watchlist events folder", w))

        lay.addSpacing(8)
        self._restart_note = QLabel(
            "⚠  Changes to Detection Size, Model Path, and ArcFace Model "
            "require restarting the camera worker to take effect."
        )
        self._restart_note.setWordWrap(True)
        self._restart_note.setStyleSheet(
            "color:#f59e0b; font-size:12px; "
            "background:#2a2000; border-radius:6px; padding:8px;"
        )
        lay.addWidget(self._restart_note)

        return card

    # ── Save / Reset ─────────────────────────────────────────────────────────

    def _save(self):
        if not _ENV_PATH.exists():
            _ENV_PATH.touch()

        errors = []
        saved_count = 0

        for key, widget in self._widgets.items():
            try:
                value = self._widget_value(widget)
                set_key(str(_ENV_PATH), key, str(value))
                saved_count += 1
            except Exception as e:
                errors.append(f"{key}: {e}")

        if errors:
            QMessageBox.warning(
                self, "Partial Save",
                f"Saved {saved_count} settings.\n\nFailed:\n" + "\n".join(errors)
            )
        else:
            self._status_lbl.setText(
                f"✅  {saved_count} settings saved to .env  —  "
                "Some changes require restarting camera workers."
            )
            self._status_lbl.setStyleSheet("color:#10b981; font-size:12px;")
            self.settings_saved.emit()

            # Reload .env so subsequent reads see new values
            self._env = dotenv_values(_ENV_PATH)

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "This will reset all settings to their default values.\n"
            "The .env file will NOT be overwritten — "
            "only the form values in this dialog will reset.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        defaults = {
            "PROCESS_N_FRAME": 5, "RESIZE_WIDTH": 640, "MAX_FRAME_QUEUE": 2,
            "PYAV_THREAD_TYPE": "slice", "PYAV_THREAD_COUNT": 0,
            "PYAV_RTBUF": "256k", "PYAV_PIXEL_FMT": "bgr24",
            "PYAV_ANALYZE_DURATION": 100000, "PYAV_PROBE_SIZE": 32768,
            "FACE_THRESHOLD": 20, "FRONT_FACE_THRESH": 0.50,
            "MAX_FACES": 20, "UNKNOWN_COOLDOWN_SEC": 10.0,
            "EMBEDDING_MIN_SIMILARITY": 0.85, "MATCH_THRESHOLD": 0.40,
            "ARC_FACE_MODEL": "buffalo_s_int8",
            "JPEG_QUALITY": 90, "MAX_SAVE_QUEUE": 20, "DEDUP_HISTORY_SIZE": 10,
            "API_HOST": "127.0.0.1", "API_PORT": 8004, "API_TIMEOUT": 30,
            "INTERVAL": 5, "MAX_BATCH": 20,
            "EMBEDDING_DEDUP_DISTANCE": 0.15, "DET_THRESH": 0.3,
        }
        for key, val in defaults.items():
            w = self._widgets.get(key)
            if w is None:
                continue
            if isinstance(w, QSpinBox):
                w.setValue(int(val))
            elif isinstance(w, QDoubleSpinBox):
                w.setValue(float(val))
            elif isinstance(w, QSlider):
                w.setValue(int(val))
            elif isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)

        self._status_lbl.setText("↺  Form reset to defaults — click Save to persist.")
        self._status_lbl.setStyleSheet("color:#f59e0b; font-size:12px;")

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _widget_value(w: QWidget):
        if isinstance(w, QSlider):
            # threshold slider stores value * 100
            return w.value() / 100.0 if w.maximum() == 100 else w.value()
        if isinstance(w, QSpinBox):
            return w.value()
        if isinstance(w, QDoubleSpinBox):
            return round(w.value(), 4)
        if isinstance(w, QLineEdit):
            return w.text().strip()
        if isinstance(w, QComboBox):
            return w.currentText()
        if isinstance(w, QCheckBox):
            return "true" if w.isChecked() else "false"
        return ""

    @staticmethod
    def _card() -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setStyleSheet(_CARD_STYLE)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 16, 20, 20)
        lay.setSpacing(10)
        return frame

    @staticmethod
    def _primary_btn(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(42)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #111111;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                padding: 0 20px;
            }
            QPushButton:hover { background-color: #ffca2c; }
            QPushButton:pressed { background-color: #e6ac00; }
        """)
        return btn

    @staticmethod
    def _secondary_btn(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(42)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #cccccc;
                border: 1px solid #444444;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #3d3d3d; color: #fff; }
        """)
        return btn