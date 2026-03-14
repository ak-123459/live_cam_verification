"""
Face Registration Module - Captures and stores face embeddings
"""
import cv2
import numpy as np
import os
import pickle
import faiss
from insightface.app import FaceAnalysis
from datetime import datetime
import uuid




class FaceRegistration:
    """Handles face capture and embedding generation"""

    # Class-level shared model (for backward compatibility)
    _shared_model = None
    _model_lock = None

    def __init__(self, faiss_index_path, faiss_metadata_path, shared_model=None):
        self.faiss_index_path = faiss_index_path
        self.faiss_metadata_path = faiss_metadata_path
        self.app = None
        self.faiss_index = None
        self.faiss_ids = []

        # Use provided shared model or initialize new one
        if shared_model is not None:
            FaceRegistration._shared_model = shared_model  # ← ADD THIS LINE
            print("[REG] Using provided shared model instance")
        else:
            self._init_model()

        self._load_index()

    def _init_model(self):
        """Initialize InsightFace model (cached at class level)"""
        if FaceRegistration._shared_model is None:
            print("[REG] Initializing InsightFace model (first time)...")
            import threading
            if FaceRegistration._model_lock is None:
                FaceRegistration._model_lock = threading.Lock()

            with FaceRegistration._model_lock:
                # Double-check after acquiring lock
                if FaceRegistration._shared_model is None:
                    FaceRegistration._shared_model = FaceAnalysis(
                        name='buffalo_s',
                        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
                    )
                    FaceRegistration._shared_model.prepare(ctx_id=0, det_size=(480, 480))
                    print("[REG] Model initialized and cached")

        self.app = FaceRegistration._shared_model
        print("[REG] Using cached model instance")



    def _load_index(self):
        """Load existing FAISS index"""
        if os.path.exists(self.faiss_index_path) and os.path.exists(self.faiss_metadata_path):
            try:
                print("[REG] Loading FAISS index...")
                self.faiss_index = faiss.read_index(self.faiss_index_path)
                with open(self.faiss_metadata_path, 'rb') as f:
                    self.faiss_ids = pickle.load(f)
                print(f"[REG] Loaded FAISS index with {self.faiss_index.ntotal} faces")
            except Exception as e:
                print(f"[REG ERROR] Failed to load index: {e}")
                self.faiss_index = faiss.IndexFlatL2(512)
                self.faiss_ids = []
        else:
            # Create new index
            self.faiss_index = faiss.IndexFlatL2(512)
            self.faiss_ids = []
            os.makedirs(os.path.dirname(self.faiss_index_path), exist_ok=True)
            print("[REG] Created new FAISS index")

    def extract_face_from_frame(self, frame):
        """
        Extract face from frame and return bbox and embedding

        Returns: (success, bbox, embedding, face_crop, message)
        """
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = self.app.get(frame_rgb, max_num=1)  # Detect up to 2 to catch multiples

            if len(faces) == 0:
                return False, None, None, None, "No face detected"

            if len(faces) > 1:
                return False, None, None, None, "Multiple faces detected - only one person allowed"

            face = faces[0]

            # Get bbox and embedding
            bbox = face.bbox.astype(int)
            embedding = face.normed_embedding

            # Extract face crop
            x1, y1, x2, y2 = bbox
            face_crop = frame[y1:y2, x1:x2]

            # Validate embedding
            if not isinstance(embedding, np.ndarray) or embedding.ndim != 1:
                return False, None, None, None, "Invalid embedding"

            return True, bbox, embedding, face_crop, "Success"

        except Exception as e:
            return False, None, None, None, f"Error: {str(e)}"




    def register_face(self, user_id, embeddings_list, face_images_list):
        """
        Register face with multiple embeddings (for better accuracy)

        Args:
            user_id: Unique user identifier
            embeddings_list: List of embeddings from multiple captures
            face_images_list: List of face crop images

        Returns: (success, message)
        """
        try:
            if len(embeddings_list) == 0:
                return False, "No embeddings provided"

            # Average embeddings for robustness
            avg_embedding = np.mean(embeddings_list, axis=0).astype('float32')
            avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)  # Re-normalize

            # Check if user already exists
            if user_id in self.faiss_ids:
                return False, f"User {user_id} already registered"

            # Add to FAISS
            self.faiss_index.add(avg_embedding.reshape(1, -1))
            self.faiss_ids.append(user_id)

            # Save index
            self._save_index()

            # Save face images
            self._save_face_images(user_id, face_images_list)

            return True, f"Successfully registered {user_id}"

        except Exception as e:
            return False, f"Registration failed: {str(e)}"

    def _save_index(self):
        """Save FAISS index and metadata"""
        try:
            faiss.write_index(self.faiss_index, self.faiss_index_path)
            with open(self.faiss_metadata_path, 'wb') as f:
                pickle.dump(self.faiss_ids, f)
            print(f"[REG] Saved index with {self.faiss_index.ntotal} faces")
        except Exception as e:
            print(f"[REG ERROR] Failed to save index: {e}")

    def _save_face_images(self, user_id, face_images):
        """Save face images for reference"""
        try:
            # Create user directory
            user_dir = os.path.join('registered_faces', user_id)
            os.makedirs(user_dir, exist_ok=True)

            # Save each image
            for i, img in enumerate(face_images):
                img_path = os.path.join(user_dir, f'face_{i+1}.jpg')
                cv2.imwrite(img_path, img)

            print(f"[REG] Saved {len(face_images)} face images for {user_id}")

        except Exception as e:
            print(f"[REG ERROR] Failed to save face images: {e}")

    def update_face(self, user_id, embeddings_list, face_images_list):
        """Update existing user's face embeddings"""
        try:
            if user_id not in self.faiss_ids:
                return False, f"User {user_id} not found"

            # Find and remove old embedding
            user_index = self.faiss_ids.index(user_id)

            # Remove from FAISS (by rebuilding index)
            remaining_ids = [uid for uid in self.faiss_ids if uid != user_id]

            # Get all other embeddings
            if len(remaining_ids) > 0:
                # Rebuild index
                new_index = faiss.IndexFlatL2(512)

                # Note: FAISS doesn't support direct removal, so we rebuild
                # In production, consider using IndexIDMap for better management
                print("[REG WARN] Full index rebuild required for update")
                return False, "Update not supported. Please delete and re-register."

            # If this was the only face, just clear and add new
            self.faiss_index = faiss.IndexFlatL2(512)
            self.faiss_ids = []

            return self.register_face(user_id, embeddings_list, face_images_list)

        except Exception as e:
            return False, f"Update failed: {str(e)}"

    def delete_user(self, user_id):
        """
        Delete a user's face embeddings from FAISS index

        Args:
            user_id: The ID of the user to delete

        Returns:
            (success: bool, message: str)
        """
        try:
            print(f"[FACE REG] ==================== DELETE USER START ====================")
            print(f"[FACE REG] Deleting user: {user_id}")
            print(f"[FACE REG] Current FAISS IDs: {self.faiss_ids}")

            # Check if user exists in FAISS
            if user_id not in self.faiss_ids:
                print(f"[FACE REG] User {user_id} not found in FAISS index")
                return True, "User not in FAISS index (already removed or never registered)"

            # Get the index position
            idx = self.faiss_ids.index(user_id)
            print(f"[FACE REG] Found user at FAISS index {idx}")

            # Get total vectors
            total_vectors = self.faiss_index.ntotal
            print(f"[FACE REG] Current FAISS vectors: {total_vectors}")

            if total_vectors == 0:
                print(f"[FACE REG] FAISS index is empty")
                return False, "FAISS index is empty"

            # Reconstruct all vectors except the deleted one
            all_embeddings = []
            all_ids = []

            for i in range(total_vectors):
                if i != idx:
                    try:
                        vector = self.faiss_index.reconstruct(i)
                        all_embeddings.append(vector)
                        all_ids.append(self.faiss_ids[i])
                    except Exception as e:
                        print(f"[FACE REG] Warning: Could not reconstruct vector {i}: {e}")

            print(f"[FACE REG] Reconstructed {len(all_embeddings)} vectors (excluding deleted user)")

            # Rebuild FAISS index with remaining embeddings
            if len(all_embeddings) > 0:
                embeddings_array = np.array(all_embeddings).astype('float32')

                # Normalize embeddings
                faiss.normalize_L2(embeddings_array)

                # Create new index
                dimension = embeddings_array.shape[1]
                new_index = faiss.IndexFlatL2(dimension)
                new_index.add(embeddings_array)

                # Replace old index and IDs
                self.faiss_index = new_index
                self.faiss_ids = all_ids

                print(f"[FACE REG] ✓ Rebuilt FAISS index with {new_index.ntotal} vectors")
            else:
                # If no embeddings left, create empty index
                dimension = self.faiss_index.d
                self.faiss_index = faiss.IndexFlatL2(dimension)
                self.faiss_ids = []
                print(f"[FACE REG] ✓ Created empty FAISS index (no users remaining)")

            # Save updated FAISS index and metadata
            self.save_faiss_index()
            print(f"[FACE REG] ✓ Saved updated FAISS index")
            print(f"[FACE REG] ✓ New FAISS IDs: {self.faiss_ids}")
            print(f"[FACE REG] ==================== DELETE USER SUCCESS ====================")

            return True, "User successfully removed from FAISS index"

        except Exception as e:
            print(f"[FACE REG] ❌ Error deleting from FAISS: {e}")
            import traceback
            traceback.print_exc()
            print(f"[FACE REG] ==================== DELETE USER FAILED ====================")
            return False, f"Failed to delete user: {str(e)}"

    def save_faiss_index(self):
        """
        Save FAISS index and metadata to disk
        (Public version of _save_index for external use)
        """
        try:
            faiss.write_index(self.faiss_index, self.faiss_index_path)
            with open(self.faiss_metadata_path, 'wb') as f:
                pickle.dump(self.faiss_ids, f)
            print(f"[FACE REG] ✓ Saved FAISS index with {self.faiss_index.ntotal} faces")
            print(f"[FACE REG] ✓ Saved metadata with {len(self.faiss_ids)} IDs")
            return True
        except Exception as e:
            print(f"[FACE REG] ✗ Failed to save FAISS index: {e}")
            import traceback
            traceback.print_exc()
            return False


    def delete_face(self, user_id):
        """
        Delete user's face from system (wrapper for delete_user for backward compatibility)

        Args:
            user_id: The ID of the user to delete

        Returns:
            (success: bool, message: str)
        """
        return self.delete_user(user_id)

    def get_registered_count(self):
        """Get number of registered faces"""
        return self.faiss_index.ntotal

    def verify_face_quality(self, frame):
        """
        Verify if face in frame is suitable for registration
        Returns: (is_good, message, quality_score)
        """
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = self.app.get(frame_rgb, max_num=1)

            if len(faces) == 0:
                return False, "No face detected", 0.0

            if len(faces) > 1:
                return False, "Multiple faces detected", 0.0

            face = faces[0]

            # Check face size (should be reasonable size)
            bbox = face.bbox
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]

            if width < 80 or height < 80:
                return False, "Face too small", 0.0

            # Check detection confidence (if available)
            det_score = getattr(face, 'det_score', 1.0)

            if det_score < 0.8:
                return False, f"Low detection confidence: {det_score:.2f}", det_score

            # All checks passed
            quality_score = det_score
            return True, "Good quality", quality_score

        except Exception as e:
            return False, f"Verification error: {str(e)}", 0.0



def generate_user_id():
    """Generate unique user ID"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"USER_{timestamp}_{unique_id}"