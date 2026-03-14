"""
Live Detection Page - Shows multiple camera feeds with real-time recognition
Enhanced with configuration persistence, auto-connect, and quality profile management
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QDialog, QLineEdit, QComboBox,
    QDialogButtonBox, QFileDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QCursor
from datetime import datetime
import cv2
import numpy as np
import sys
import os
from FacePose.app.predictor import FacePosePredictor



predictor = FacePosePredictor(
    model_path="models/face_side_det/logistic_model.joblib",
    label_encoder_path="models/face_side_det/label_encoder.joblib",
)


# Add the project root to the path if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AddCameraDialog(QDialog):
    """Dialog for adding a new camera"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Camera")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Camera Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Camera Name (e.g., Main Entrance)")
        layout.addWidget(QLabel("Camera Name:"))
        layout.addWidget(self.name_input)

        # Source Type
        self.source_type = QComboBox()
        self.source_type.addItems(["RTSP Stream", "Webcam", "Video File"])
        layout.addWidget(QLabel("Source Type:"))
        layout.addWidget(self.source_type)

        # Source Input
        source_layout = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("rtsp://192.168.1.X:554/...")
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_file)
        source_layout.addWidget(self.source_input)
        source_layout.addWidget(self.browse_button)
        layout.addWidget(QLabel("Source:"))
        layout.addLayout(source_layout)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.source_type.currentTextChanged.connect(self.update_source_placeholder)
        self.update_source_placeholder()

    def update_source_placeholder(self):
        source_type = self.source_type.currentText()
        if source_type == "RTSP Stream":
            self.source_input.setPlaceholderText("rtsp://192.168.1.X:554/...")
            self.browse_button.setEnabled(False)
        elif source_type == "Webcam":
            self.source_input.setPlaceholderText("0 (for default webcam)")
            self.browse_button.setEnabled(False)
        else:  # Video File
            self.source_input.setPlaceholderText("Select video file...")
            self.browse_button.setEnabled(True)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if file_path:
            self.source_input.setText(file_path)

    def get_data(self):
        name = self.name_input.text().strip()
        source_type = self.source_type.currentText()
        source = self.source_input.text().strip()

        # Convert webcam input to int
        if source_type == "Webcam":
            try:
                source = int(source) if source else 0
            except ValueError:
                source = 0

        return name, source, source_type


class CameraWidget(QFrame):
    """Widget displaying a single camera feed with context menu"""

    delete_requested = Signal(str)  # Emits camera_id when delete is requested

    def __init__(self, camera_id, camera_name, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.first_frame_rendered = False
        self.camera_name = camera_name
        self.worker = None
        self.current_fps = 0
        self.is_running = False

        self.setObjectName("cameraWidget")
        self.setStyleSheet("""
            QFrame#cameraWidget {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 12px;
                padding: 12px;
            }
            QFrame#cameraWidget:hover {
                border: 1px solid #ffc107;
            }
        """)

        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel(camera_name)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #fff;")

        self.status_label = QLabel("●")
        self.status_label.setStyleSheet("color: #22c55e; font-size: 16px;")

        self.fps_label = QLabel("0 FPS")
        self.fps_label.setStyleSheet("color: #64748b; font-size: 12px;")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.fps_label)
        header_layout.addWidget(self.status_label)
        layout.addLayout(header_layout)

        # Video Display
        self.video_label = QLabel()
        self.video_label.setMinimumSize(400, 300)
        self.video_label.setStyleSheet("background-color: #000; border-radius: 8px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(False)


        # Show camera info when no feed
        self.video_label.setText(f"📹 {camera_name}\n\nLoading...")
        self.video_label.setStyleSheet("""
            background-color: #1a1a1a; 
            border-radius: 8px;
            color: #64748b;
            font-size: 14px;
        """)

        layout.addWidget(self.video_label)

        # Controls
        controls_layout = QHBoxLayout()

        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)

        self.delete_button = QPushButton("🗑️ Delete")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #991b1b;
            }
        """)
        self.delete_button.clicked.connect(self.request_delete)

        controls_layout.addStretch()
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.delete_button)
        layout.addLayout(controls_layout)

    def show_context_menu(self, position):
        """Show context menu on right-click"""
        menu = QMenu(self)

        # Delete action
        delete_action = menu.addAction("🗑️ Delete Camera")
        delete_action.triggered.connect(self.request_delete)

        # Stop/Start action
        if self.is_running:
            stop_action = menu.addAction("⏸️ Stop Camera")
            stop_action.triggered.connect(lambda: self.stop_button.click())

        menu.exec(self.mapToGlobal(position))

    def request_delete(self):
        """Request camera deletion with confirmation"""
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete camera '{self.camera_name}'?\n\n"
            "This will remove the camera from the configuration.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.delete_requested.emit(self.camera_id)

    def update_frame(self, frame, results):
        """Update video display with frame"""
        # 🚫 Ignore all frames after the first one
        if self.first_frame_rendered:
            return
        try:
            self.first_frame_rendered = True
            self.is_running = True

            # Draw detections on frame
            from app.workers.camera_worker import draw_detections
            frame = draw_detections(frame, results, self.current_fps)

            # Convert to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(
                frame.data, width, height, bytes_per_line, QImage.Format_RGB888
            ).rgbSwapped()

            # Scale to fit label
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.video_label.setPixmap(scaled_pixmap)
            self.video_label.setStyleSheet("background-color: #000; border-radius: 8px;")

        except Exception as e:
            print(f"[CAMERA] Frame update error: {e}")

    def update_fps(self, fps):
        """Update FPS display"""
        self.current_fps = fps
        self.fps_label.setText(f"{fps:.1f} FPS")

    def set_status(self, active):
        """Update status indicator"""
        self.is_running = active
        if active:
            self.status_label.setStyleSheet("color: #22c55e; font-size: 16px;")
            self.status_label.setToolTip("Camera Active")
        else:
            self.status_label.setStyleSheet("color: #ef4444; font-size: 16px;")
            self.status_label.setToolTip("Camera Stopped")



class LiveDetectionPage(QWidget):
    """Main page showing live camera feeds with configuration persistence and quality profiles"""

    MAX_CAMERAS = 2

    def __init__(self, attendance_manager, faiss_index_path, faiss_metadata_path, parent=None):
        super().__init__(parent)
        self.attendance_manager = attendance_manager
        self.faiss_index_path = faiss_index_path
        self.faiss_metadata_path = faiss_metadata_path
        self.camera_widgets = {}  # Dict: camera_id -> widget
        self.camera_workers = {}  # Dict: camera_id -> worker
        # Quality profile manager
        self.quality_matcher = None
        self.profiles_checked = {}  # Track which cameras have profiles

        # Initialize configuration manager
        print("[LIVE] Initializing camera configuration manager...")
        try:
            from app.utils.camera_config import CameraConfigManager
            self.config_manager = CameraConfigManager()
            print("[LIVE] ✓ Configuration manager initialized")
        except Exception as e:
            print(f"[LIVE ERROR] Failed to initialize config manager: {e}")
            import traceback
            traceback.print_exc()
            self.config_manager = None

        # Initialize quality matcher
        try:
            from app.utils.global_quality_matcher import GlobalQualityMatcher
            self.quality_matcher = GlobalQualityMatcher()
            print("[LIVE] ✓ Quality matcher initialized")
        except Exception as e:
            print(f"[LIVE ERROR] Failed to initialize quality matcher: {e}")
            import traceback
            traceback.print_exc()

        self.setup_ui()

        # Auto-connect saved cameras and check profiles
        QTimer.singleShot(500, self.auto_connect_cameras)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Live Detection")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")

        # Info label
        self.info_label = QLabel(f"0/{self.MAX_CAMERAS} cameras active")
        self.info_label.setStyleSheet("color: #64748b; font-size: 14px;")

        self.add_camera_btn = QPushButton("+ Add Camera")
        self.add_camera_btn.setObjectName("addApplicationButton")
        self.add_camera_btn.setStyleSheet("""
            QPushButton#addApplicationButton {
                background-color: #ffc107;
                color: #111;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#addApplicationButton:hover {
                background-color: #ffb300;
            }
        """)
        self.add_camera_btn.clicked.connect(self.add_camera)

        header_layout.addWidget(title)
        header_layout.addWidget(self.info_label)
        header_layout.addStretch()
        header_layout.addWidget(self.add_camera_btn)
        layout.addLayout(header_layout)

        # Camera Grid
        self.cameras_layout = QGridLayout()
        self.cameras_layout.setSpacing(16)
        layout.addLayout(self.cameras_layout)

        # Placeholder
        self.placeholder = QLabel(
            "📹 No cameras connected\n\n"
            "Click 'Add Camera' to add a new camera feed\n"
            "or cameras will auto-connect from saved configuration"
        )
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("""
            color: #64748b; 
            font-size: 16px;
            padding: 60px;
            background-color: #1a1a1a;
            border-radius: 12px;
            border: 2px dashed #333;
        """)
        layout.addWidget(self.placeholder)

        layout.addStretch()

    def check_and_create_profile(self, camera_id, camera_source):
        """
        FIXED: No longer calls cv2.VideoCapture on the main thread.
        Profile will be created lazily from live frames instead.
        """
        if not self.quality_matcher:
            return False
        # Only load existing — never create (creation blocked UI)
        if self.quality_matcher.load_profile(camera_id):
            print(f"[PROFILE] ✓ Existing profile loaded for {camera_id}")
            self.profiles_checked[camera_id] = True
            return True
        # No profile yet — that's fine, skip silently
        print(f"[PROFILE] No profile yet for {camera_id} — will create from live frames")
        self.profiles_checked[camera_id] = False
        return False  # Non-blocking: camera will still start


    def auto_connect_cameras(self):
        """Automatically connect cameras from configuration"""
        print("\n" + "="*60)
        print("[LIVE] AUTO-CONNECTING SAVED CAMERAS")
        print("="*60)

        if not self.config_manager:
            print("[LIVE ERROR] Config manager not available")
            return

        try:
            saved_cameras = self.config_manager.get_enabled_cameras()

            if not saved_cameras:
                print("[LIVE] No saved cameras found")
                return

            print(f"[LIVE] Found {len(saved_cameras)} saved camera(s)")

            for camera_config in saved_cameras:
                camera_id = camera_config['camera_id']
                name = camera_config['name']
                source = camera_config['source']
                source_type = camera_config.get('source_type', 'RTSP Stream')

                # Convert source if it's a webcam
                if source_type == 'Webcam':
                    try:
                        source = int(source)
                    except:
                        source = 0

                print(f"[LIVE] Auto-connecting: {name} ({camera_id}) - Source: {source}")

                # Check/create quality profile BEFORE starting camera
                profile_created = self.check_and_create_profile(camera_id, source)

                if profile_created:
                    print(f"[LIVE] ✓ Quality profile ready for {camera_id}")
                else:
                    print(f"[LIVE] ⚠ Warning: No quality profile for {camera_id}")

                # Start camera
                self.start_camera(camera_id, name, source)

            self.update_info_label()
            print("="*60 + "\n")

        except Exception as e:
            print(f"[LIVE ERROR] Auto-connect failed: {e}")
            import traceback
            traceback.print_exc()

    def add_camera(self):
        """Show dialog to add new camera"""
        if len(self.camera_widgets) >= self.MAX_CAMERAS:
            QMessageBox.warning(
                self, "Limit Reached",
                f"Maximum {self.MAX_CAMERAS} cameras allowed."
            )
            return

        dialog = AddCameraDialog(self)
        if dialog.exec() == QDialog.Accepted:
            name, source, source_type = dialog.get_data()

            if not name:
                QMessageBox.warning(self, "Invalid Input", "Please provide a camera name.")
                return

            if source == "" and source != 0:
                QMessageBox.warning(self, "Invalid Input", "Please provide a camera source.")
                return

            # Generate unique camera ID
            timestamp = int(datetime.now().timestamp())
            camera_id = f"cam_{len(self.camera_widgets) + 1}_{timestamp}"

            print(f"\n[LIVE] Adding new camera:")
            print(f"  ID: {camera_id}")
            print(f"  Name: {name}")
            print(f"  Source: {source}")
            print(f"  Type: {source_type}")

            # Save to configuration
            if self.config_manager:
                self.config_manager.add_camera(camera_id, name, str(source), source_type)

            # Check/create quality profile
            profile_created = self.check_and_create_profile(camera_id, source)

            if profile_created:
                print(f"[LIVE] ✓ Quality profile created for new camera")
            else:
                print(f"[LIVE] ⚠ Warning: Failed to create quality profile")

            # Start camera
            self.start_camera(camera_id, name, source)

    def start_camera(self, camera_id, camera_name, camera_source):
        """Start camera worker thread"""
        # Check if camera already running
        if camera_id in self.camera_widgets:
            print(f"[LIVE] Camera {camera_id} already running")
            return

        print(f"\n[LIVE] Starting camera: {camera_name}")

        try:
            from app.workers.camera_worker import OptimizedCameraWorker

            # Create widget
            camera_widget = CameraWidget(camera_id, camera_name)
            camera_widget.delete_requested.connect(self.delete_camera)


            # Create worker
            worker = OptimizedCameraWorker(
                camera_id,
                camera_source,
                self.faiss_index_path,
                self.faiss_metadata_path,
                .20,
                resize_width=640,
                debug_mode=False ,
                pose_predictor=predictor
            )

            # worker.watchlist_alert.connect(self.handle_watchlist_alert)

            # Connect signals
            worker.frame_ready.connect(camera_widget.update_frame)
            worker.fps_updated.connect(camera_widget.update_fps)
            worker.error_occurred.connect(
                lambda msg: self.handle_camera_error(camera_id, camera_name, msg)
            )
            # worker.attendance_marked.connect(self.handle_attendance_marked)

            camera_widget.stop_button.clicked.connect(
                lambda: self.stop_camera(camera_id)
            )

            # Add to grid layout (2 columns)
            num_cameras = len(self.camera_widgets)
            row = num_cameras // 2
            col = num_cameras % 2
            self.cameras_layout.addWidget(camera_widget, row, col)

            # Store references
            self.camera_widgets[camera_id] = camera_widget
            self.camera_workers[camera_id] = worker

            # Hide placeholder
            self.placeholder.hide()

            # Start worker
            worker.start()
            camera_widget.set_status(True)

            print(f"[LIVE] ✓ Camera started successfully: {camera_name}")
            self.update_info_label()

        except Exception as e:
            print(f"[LIVE ERROR] Failed to start camera: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "Camera Start Failed",
                f"Failed to start camera '{camera_name}':\n\n{str(e)}"
            )

    def stop_camera(self, camera_id):
        """Stop camera (but keep in configuration)"""
        if camera_id not in self.camera_widgets:
            return

        print(f"[LIVE] Stopping camera: {camera_id}")

        # Stop worker
        worker = self.camera_workers[camera_id]
        worker.stop()

        # Update widget status
        widget = self.camera_widgets[camera_id]
        widget.set_status(False)
        widget.video_label.setText(f"📹 {widget.camera_name}\n\nStopped")
        widget.video_label.setStyleSheet("""
            background-color: #1a1a1a; 
            border-radius: 8px;
            color: #64748b;
            font-size: 14px;
        """)

        print(f"[LIVE] ✓ Camera stopped: {camera_id}")
        self.update_info_label()

    def delete_camera(self, camera_id):
        """Delete camera completely (stop and remove from config)"""
        if camera_id not in self.camera_widgets:
            return

        print(f"\n[LIVE] Deleting camera: {camera_id}")

        # Stop worker
        if camera_id in self.camera_workers:
            worker = self.camera_workers[camera_id]
            worker.stop()
            worker.wait(2000)  # Wait up to 2 seconds

        # Remove widget
        widget = self.camera_widgets[camera_id]
        self.cameras_layout.removeWidget(widget)
        widget.deleteLater()

        # Remove from dictionaries
        del self.camera_widgets[camera_id]
        if camera_id in self.camera_workers:
            del self.camera_workers[camera_id]

        # Remove from profile tracking
        if camera_id in self.profiles_checked:
            del self.profiles_checked[camera_id]

        # Remove from configuration
        if self.config_manager:
            self.config_manager.remove_camera(camera_id)

        # Show placeholder if no cameras
        if len(self.camera_widgets) == 0:
            self.placeholder.show()

        print(f"[LIVE] ✓ Camera deleted: {camera_id}")
        self.update_info_label()

    def update_info_label(self):
        """Update the camera count info label"""
        active_count = sum(1 for w in self.camera_widgets.values() if w.is_running)
        total_count = len(self.camera_widgets)
        self.info_label.setText(f"{active_count}/{self.MAX_CAMERAS} cameras active ({total_count} configured)")

    def handle_camera_error(self, camera_id, camera_name, error_msg):
        """Handle camera errors"""
        print(f"[LIVE ERROR] Camera {camera_name}: {error_msg}")

        # Update widget to show error
        if camera_id in self.camera_widgets:
            widget = self.camera_widgets[camera_id]
            widget.set_status(False)
            widget.video_label.setText(f"❌ Error\n\n{error_msg[:100]}")
            widget.video_label.setStyleSheet("""
                background-color: #1a1a1a; 
                border: 2px solid #ef4444;
                border-radius: 8px;
                color: #ef4444;
                font-size: 12px;
                padding: 10px;
            """)

        QMessageBox.critical(
            self, "Camera Error",
            f"Camera '{camera_name}' encountered an error:\n\n{error_msg}"
        )

    def handle_attendance_marked(self, user_id, name, confidence):
        """Handle attendance marked event"""
        print(f"[ATTENDANCE] ✓ Marked: {name} (confidence: {confidence:.2%})")

    def cleanup(self):
        """Stop all cameras before closing"""
        print("\n[LIVE] Cleaning up cameras...")
        for camera_id, worker in list(self.camera_workers.items()):
            print(f"[LIVE] Stopping {camera_id}...")
            worker.stop()
            worker.wait(2000)
        print("[LIVE] ✓ All cameras stopped\n")

    # def handle_watchlist_alert(self, user_id, name, confidence, category):
    #     """Handle watchlist alert from camera"""
    #     print(f"\n{'🚨' * 30}")
    #     print(f"[UI] WATCHLIST ALERT!")
    #     print(f"  User: {name} ({user_id})")
    #     print(f"  Category: {category.upper()}")
    #     print(f"  Confidence: {confidence:.2%}")
    #     print(f"{'🚨' * 30}\n")
    #
    #     # Show popup alert
    #     QMessageBox.warning(
    #         self,
    #         f"⚠️ Watchlist Alert - {category.upper()}",
    #         f"Detected: {name}\n"
    #         f"Category: {category.upper()}\n"
    #         f"Confidence: {confidence:.2%}\n\n"
    #         f"Check watchlist events for details."
    #     )