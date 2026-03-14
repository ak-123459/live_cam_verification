"""
Registration Camera Worker - Non-blocking camera for registration with quality profile support

IMPORTANT: Save this file as: app/workers/registration_camera_worker.py
"""
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
import time




class RegistrationCameraWorker(QThread):
    """
    Background thread for registration camera feed.
    Streams live frames to UI without blocking.

    face_registration is optional — if None, a lightweight OpenCV
    quality check is used instead of InsightFace verify_face_quality().
    """

    frame_ready = Signal(np.ndarray, bool, str, float)  # frame, is_good, message, quality
    error_occurred = Signal(str)

    def __init__(self, camera_source, face_registration=None, parent=None):
        super().__init__(parent)
        self.camera_source   = camera_source
        self.face_registration = face_registration   # ← now truly optional (can be None)
        self.running         = False
        self.cap             = None
        self.process_every_n_frames = 3
        self.frame_count     = 0
        self.last_verification = (True, "Ready", 1.0)

    def run(self):
        """Main camera loop in background thread"""
        try:
            self.cap = cv2.VideoCapture(self.camera_source)

            if not self.cap.isOpened():
                print(f"[CAM WORKER] ❌ Failed to open camera {self.camera_source}")
                self.error_occurred.emit(f"Failed to open camera {self.camera_source}")
                return

            print(f"[CAM WORKER] ✅ Camera {self.camera_source} opened")
            print(f"[CAM WORKER]   Width:  {self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)}")
            print(f"[CAM WORKER]   Height: {self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")

            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            self.running = True

            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                should_verify = (self.frame_count % self.process_every_n_frames == 0)

                if should_verify:
                    if self.face_registration is not None:
                        # ── Full InsightFace quality check ──────────────
                        is_good, message, quality = \
                            self.face_registration.verify_face_quality(frame)
                    else:
                        # ── Lightweight OpenCV fallback (face_registration=None) ──
                        is_good, message, quality = self._basic_quality_check(frame)

                    self.last_verification = (is_good, message, quality)
                else:
                    is_good, message, quality = self.last_verification

                frame = self._draw_feedback(frame, is_good, message, quality)
                self.frame_ready.emit(frame, is_good, message, quality)

                self.frame_count += 1
                time.sleep(0.01)

        except Exception as e:
            self.error_occurred.emit(f"Camera error: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()

    def _basic_quality_check(self, frame):
        """
        Lightweight quality check using only OpenCV — no InsightFace needed.
        Called when face_registration=None.

        Checks brightness and blur (Laplacian variance).
        Returns: (is_good, message, quality_score)
        """
        try:
            if frame is None or frame.size == 0:
                return False, "Empty frame", 0.0

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Brightness
            brightness = float(np.mean(gray))
            if brightness < 40:
                return False, "Too dark", round(brightness / 255, 2)
            if brightness > 220:
                return False, "Too bright", round(brightness / 255, 2)

            # Blur (Laplacian variance — higher = sharper)
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if blur_score < 50:
                return False, "Image too blurry", round(blur_score / 1000, 2)

            quality = min(1.0, round(blur_score / 500, 2))
            return True, "Position face in frame", quality

        except Exception as e:
            return False, f"Check error: {str(e)}", 0.0

    def _draw_feedback(self, frame, is_good, message, quality):
        """Draw feedback overlay on frame"""
        color     = (0, 255, 0) if is_good else (0, 165, 255)
        thickness = 3 if is_good else 2
        h, w      = frame.shape[:2]

        cv2.rectangle(frame, (10, 10), (w - 10, h - 10), color, thickness)

        font      = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(message, font, 0.8, 2)[0]
        cv2.rectangle(frame, (15, 25), (25 + text_size[0], 55), (0, 0, 0), -1)
        cv2.putText(frame, message, (20, 45), font, 0.8, color, 2)

        if is_good:
            cv2.putText(frame, f"Quality: {quality:.2f}", (20, 80),
                        font, 0.6, (0, 255, 255), 2)
            cv2.circle(frame, (w - 40, 40), 15, (0, 255, 0), -1)

        return frame

    def stop(self):
        """Stop the camera worker"""
        self.running = False
        self.wait()


# ─────────────────────────────────────────────────────────────
#  RegistrationCaptureWorker  (LEGACY — kept for compatibility)
#  Not used by the current registration_page.py.
#  New flow: _extract_300_crop() + _apply_quality() inline → API
# ─────────────────────────────────────────────────────────────
class RegistrationCaptureWorker(QThread):
    """
    Legacy background worker for local face embedding extraction.
    No longer called by registration_page.py — kept for backward compatibility.
    """

    capture_completed = Signal(object, object)  # embedding, face_crop
    capture_failed    = Signal(str)

    def __init__(self, frame, face_registration, quality_matcher=None,
                 profile_intensity=0.7, parent=None):
        super().__init__(parent)
        self.frame             = frame.copy()
        self.face_registration = face_registration
        self.quality_matcher   = quality_matcher
        self.profile_intensity = profile_intensity

    def run(self):
        try:
            success, bbox, embedding, face_crop, message = \
                self.face_registration.extract_face_from_frame(self.frame)

            if not success:
                self.capture_failed.emit(message)
                return

            if self.quality_matcher and self.quality_matcher.has_profile():
                try:
                    enhanced = self.quality_matcher.apply_quality_to_frame(
                        face_crop, intensity=self.profile_intensity
                    )
                    enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
                    faces = self.face_registration.app.get(enhanced_rgb)
                    if len(faces) > 0:
                        self.capture_completed.emit(faces[0].normed_embedding, enhanced)
                        return
                except Exception as e:
                    print(f"[CAPTURE WORKER] ⚠ Quality apply failed: {e}")

            self.capture_completed.emit(embedding, face_crop)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.capture_failed.emit(f"Extraction error: {str(e)}")