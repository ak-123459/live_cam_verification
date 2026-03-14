"""
Global Quality Matcher - Apply camera quality properties
File: app/utils/quality_matcher.py
"""
import cv2
import numpy as np
from typing import Dict, Optional
import pickle
import os



class GlobalQualityMatcher:
    """
    Apply global quality properties from source camera to target frames
    - Brightness, Noise, Blur, Contrast, Saturation, Compression
    """

    def __init__(self):
        self.quality_profile = {}
        self.profile_cache_dir = 'camera_profiles'
        os.makedirs(self.profile_cache_dir, exist_ok=True)

    def extract_quality_profile(self, source_frame: np.ndarray, camera_id: str = None) -> Dict:

        """
        Extract global quality properties from source frame

        Args:
            source_frame: Source camera frame (BGR format)
            camera_id: Optional camera identifier for caching

        Returns:
            Dictionary with quality metrics
        """
        if source_frame is None or source_frame.size == 0:
            raise ValueError("Invalid source frame")

        gray = cv2.cvtColor(source_frame, cv2.COLOR_BGR2GRAY)

        # Extract quality metrics
        brightness = float(gray.mean())
        contrast = float(gray.std())
        noise_level = self._measure_noise(gray)
        # blur_amount = self._measure_blur(gray)

        hsv = cv2.cvtColor(source_frame, cv2.COLOR_BGR2HSV)
        saturation = float(hsv[:, :, 1].mean())

        compression_quality = self._estimate_compression_quality(source_frame)

        self.quality_profile = {
            'brightness': brightness,
            'contrast': contrast,
            'noise_level': noise_level,
            'saturation': saturation,
            'compression_quality': compression_quality,
            'camera_id': camera_id }

        print(f"[QUALITY] Extracted profile from {camera_id or 'source'}:")
        print(f"  Brightness: {brightness:.2f}")
        print(f"  Contrast: {contrast:.2f}")
        print(f"  Noise: {noise_level:.4f}")
        # print(f"  Blur: {blur_amount:.2f}")
        print(f"  Saturation: {saturation:.2f}")
        print(f"  Compression: {compression_quality:.0f}")

        # Auto-save if camera_id provided
        if camera_id:
            self.save_profile(camera_id)

        return self.quality_profile

    def apply_quality_to_frame(self, target_frame: np.ndarray,
                               intensity: float = 0.7) -> np.ndarray:
        """
        Apply quality properties to target frame

        Args:
            target_frame: Frame to apply quality to (BGR format)
            intensity: Application strength (0.0 to 1.0)

        Returns:
            Frame with matched quality (same resolution as input)
        """
        if not self.quality_profile:
            print("[QUALITY WARN] No profile loaded, returning original frame")
            return target_frame

        if target_frame is None or target_frame.size == 0:
            return target_frame

        result = target_frame.copy().astype(np.float32)

        # Apply quality transformations
        # result = self._apply_blur(result, intensity)
        result = self._apply_noise(result, intensity)
        result = self._match_brightness_contrast(result)
        result = self._match_saturation(result)
        result = self._apply_compression(result, intensity)

        return np.clip(result, 0, 255).astype(np.uint8)


    # ==================== Measurement Methods ====================

    def apply_quality_profile(self, image: np.ndarray, intensity: float = 0.7) -> np.ndarray:
        """Alias for apply_quality_to_frame - called by registration_page.py"""
        return self.apply_quality_to_frame(image, intensity)



    def _measure_noise(self, gray: np.ndarray) -> float:
        """Estimate noise level using median blur difference"""
        denoised = cv2.medianBlur(gray, 5)
        noise = np.abs(gray.astype(float) - denoised.astype(float))
        return float(noise.std())

    def _measure_blur(self, gray: np.ndarray) -> float:
        """Measure blur using Laplacian variance"""
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = max(0, 100 - laplacian_var / 10)
        return float(blur_score)

    def _estimate_compression_quality(self, image: np.ndarray) -> float:
        """Estimate JPEG compression quality (0-100)"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Measure high-frequency content
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)

        h, w = gray.shape
        center_h, center_w = h // 2, w // 2

        # High frequency mask
        mask = np.ones_like(magnitude)
        mask[center_h-30:center_h+30, center_w-30:center_w+30] = 0

        high_freq = (magnitude * mask).sum()
        total = magnitude.sum()

        ratio = high_freq / total if total > 0 else 0
        quality = min(100, max(10, ratio * 5000))

        return float(quality)

    # ==================== Application Methods ====================
    #
    # def _apply_blur(self, image: np.ndarray, intensity: float) -> np.ndarray:
    #     """Apply Gaussian blur"""
    #     blur_amount = self.quality_profile.get('blur_amount', 0)
    #
    #     if blur_amount > 50:
    #         kernel_size = int((blur_amount / 50) * 5 * intensity)
    #         kernel_size = max(3, min(kernel_size * 2 + 1, 15))
    #         sigma = kernel_size / 3.0
    #         return cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)
    #
    #     return image

    def _apply_noise(self, image: np.ndarray, intensity: float) -> np.ndarray:
        """Add Gaussian noise"""
        noise_std = self.quality_profile.get('noise_level', 0) * 10 * intensity

        # Luminance noise
        luma_noise = np.random.normal(0, noise_std, image.shape[:2])
        for c in range(3):
            image[:, :, c] += luma_noise

        # Color noise
        color_noise = np.random.normal(0, noise_std * 0.5, image.shape)
        image += color_noise

        return image

    def _match_brightness_contrast(self, image: np.ndarray) -> np.ndarray:
        """Match brightness and contrast"""
        gray = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_BGR2GRAY)

        current_brightness = gray.mean()
        current_contrast = gray.std()

        target_brightness = self.quality_profile.get('brightness', current_brightness)
        target_contrast = self.quality_profile.get('contrast', current_contrast)

        alpha = target_contrast / current_contrast if current_contrast > 0 else 1.0
        beta = target_brightness - current_brightness * alpha

        result = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
        return result.astype(np.float32)

    def _match_saturation(self, image: np.ndarray) -> np.ndarray:
        """Match color saturation"""
        hsv = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)

        current_saturation = hsv[:, :, 1].mean()
        target_saturation = self.quality_profile.get('saturation', current_saturation)

        if current_saturation > 0:
            saturation_ratio = target_saturation / current_saturation
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_ratio, 0, 255)

        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        return result.astype(np.float32)

    def _apply_compression(self, image: np.ndarray, intensity: float) -> np.ndarray:
        """Apply JPEG compression artifacts"""
        quality = self.quality_profile.get('compression_quality', 95)
        jpeg_quality = int(quality * (1 - intensity * 0.3))
        jpeg_quality = max(10, min(jpeg_quality, 95))

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
        _, encoded = cv2.imencode('.jpg', image.astype(np.uint8), encode_param)
        compressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

        return compressed.astype(np.float32)

    # ==================== Save/Load ====================

    def save_profile(self, camera_id: str):
        """Save quality profile to disk"""
        filename = os.path.join(self.profile_cache_dir, f'{camera_id}_profile.pkl')
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.quality_profile, f)
            print(f"[QUALITY] ✓ Saved profile for {camera_id}")
        except Exception as e:
            print(f"[QUALITY ERROR] Failed to save profile: {e}")

    def load_profile(self, camera_id: str) -> bool:
        """Load quality profile from disk"""
        filename = os.path.join(self.profile_cache_dir, f'{camera_id}_profile.pkl')

        if not os.path.exists(filename):
            print(f"[QUALITY] No saved profile found for {camera_id}")
            return False

        try:
            with open(filename, 'rb') as f:
                self.quality_profile = pickle.load(f)
            print(f"[QUALITY] ✓ Loaded profile for {camera_id}")
            return True
        except Exception as e:
            print(f"[QUALITY ERROR] Failed to load profile: {e}")
            return False

    def has_profile(self) -> bool:
        """Check if a profile is loaded"""
        return bool(self.quality_profile)

    def clear_profile(self):
        """Clear current profile"""
        self.quality_profile = {}