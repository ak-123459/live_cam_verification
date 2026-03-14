"""
Enhanced Face Registration with Camera Quality Matching
Adds quality property extraction and application to registration flow
"""
import cv2
import numpy as np
from app.utils.global_quality_matcher import GlobalQualityMatcher


class EnhancedFaceRegistration:
    """
    Wrapper around FaceRegistration that applies source camera quality
    """

    def __init__(self, face_registration, quality_matcher=None):
        self.face_registration = face_registration
        self.quality_matcher = quality_matcher or GlobalQualityMatcher()
        self.source_camera_id = None
        self.quality_applied = False

    def set_source_camera(self, camera_id, sample_frame):
        """
        Extract and store quality profile from source camera

        Args:
            camera_id: ID of the source RTSP camera
            sample_frame: Sample frame from the camera
        """
        print(f"[ENHANCED REG] Setting source camera: {camera_id}")

        # Try to load existing profile first
        if self.quality_matcher.load_profile(camera_id):
            print(f"[ENHANCED REG] ✓ Loaded existing profile for {camera_id}")
            self.source_camera_id = camera_id
            self.quality_applied = True
            return True

        # Extract new profile from sample frame
        try:
            self.quality_matcher.extract_quality_profile(sample_frame, camera_id)
            self.source_camera_id = camera_id
            self.quality_applied = True
            print(f"[ENHANCED REG] ✓ Created new profile for {camera_id}")
            return True
        except Exception as e:
            print(f"[ENHANCED REG ERROR] Failed to extract profile: {e}")
            return False

    def apply_quality_to_frame(self, frame, intensity=0.7):
        """
        Apply source camera quality to registration frame

        Args:
            frame: Frame to process
            intensity: How much to apply (0.0-1.0)

        Returns:
            Processed frame with quality applied
        """
        if not self.quality_applied:
            print("[ENHANCED REG] No quality profile loaded, returning original")
            return frame

        return self.quality_matcher.apply_quality_to_frame(frame, intensity)

    def extract_face_from_frame(self, frame, apply_quality=True):
        """
        Extract face with optional quality matching

        Args:
            frame: Input frame
            apply_quality: Whether to apply source camera quality

        Returns:
            (success, bbox, embedding, face_crop, message)
        """
        # Apply quality if enabled
        processed_frame = frame
        if apply_quality and self.quality_applied:
            print("[ENHANCED REG] Applying source camera quality...")
            processed_frame = self.apply_quality_to_frame(frame)

        # Use original face registration method
        return self.face_registration.extract_face_from_frame(processed_frame)

    def register_face(self, user_id, embeddings_list, face_images_list):
        """
        Register face (delegates to original implementation)
        """
        return self.face_registration.register_face(
            user_id, embeddings_list, face_images_list
        )

    def clear_quality_profile(self):
        """Clear current quality profile"""
        self.quality_matcher.clear_profile()
        self.source_camera_id = None
        self.quality_applied = False
        print("[ENHANCED REG] Quality profile cleared")