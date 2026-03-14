"""
Camera Worker - FRS Phase 1 Pipeline
=====================================
Phase 1: buffalo_sc model for fast filtering
  - Known face  (score >= threshold) → Display only, no save
  - Unknown face (score <  threshold) → Save aligned crop to captures/unknown/
  - Dedup: global cooldown + per-pool embedding similarity guard

Phase 2 (offline): Large model re-verifies captures/unknown/ for accurate attendance
"""




import cv2
import numpy as np
import faiss
import pickle
import os
import time
import threading
import logging
from datetime import datetime
from queue import Queue, Empty
from collections import deque

from PySide6.QtCore import QThread, Signal
from insightface.utils import face_align as _face_align
from dotenv import load_dotenv

from app.utils.image_utils import estimate_pose_from_kps
from app.workers.model_manager import get_shared_model
load_dotenv()

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
UNKNOWN_CAPTURES_ROOT  = os.getenv("UNKNOWN_CAPTURES_ROOT", "captures/unknown")
DEDUP_HISTORY_SIZE     = int(os.getenv("DEDUP_HISTORY_SIZE", 10))
DET_THRESH             = float(os.getenv("DET_THRESH", 0.45))
ARC_FACE_MODEL         = os.getenv("ARC_FACE_MODEL", "buffalo_s_int8")
DET_SIZE               = os.getenv("DET_SIZE", (320, 320))
FACE_CROP_SIZE         = 300
JPEG_QUALITY           = [cv2.IMWRITE_JPEG_QUALITY, 90]
FRONT_FACE_THRESH = float(os.getenv("FRONT_FACE_THRESH",0.82))




# ─────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for L2-normalised embeddings."""
    return float(np.dot(a, b))


def _pool_has_duplicate(emb: np.ndarray, pool: deque, min_sim: float) -> bool:
    """True if emb is too similar to anything already in the pool."""
    return any(_cosine_sim(emb, e) >= min_sim for e in pool)


def draw_detections(frame: np.ndarray, results: list, fps: float = 0) -> np.ndarray:
    for r in results:
        x1, y1, x2, y2 = r["bbox"]
        name  = r["name"]
        score = float(r["score"])
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{name} {score:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    if fps > 0:
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    return frame


# ─────────────────────────────────────────────
# Worker
# ─────────────────────────────────────────────

class OptimizedCameraWorker(QThread):
    """
    FRS Phase 1 camera worker.

    Signals
    -------
    frame_ready    : (frame: np.ndarray, results: list)
    fps_updated    : (fps: float)
    error_occurred : (msg: str)
    face_saved     : (unknown_id: str, label: str, score: float, path: str)
    """

    frame_ready    = Signal(np.ndarray, list)
    fps_updated    = Signal(float)
    error_occurred = Signal(str)
    face_saved     = Signal(str, str, float, str)

    def __init__(
        self,
        camera_id,
        camera_source,
        faiss_index_path,
        faiss_metadata_path,
        threshold=0.45,
        process_every_n_frames=5,
        resize_width=640,
        unknown_cooldown_sec=10.0,
        embedding_min_similarity=0.85,
        debug_mode=False,
        pose_predictor=None
    ):
        super().__init__()

        self.camera_id              = camera_id
        self.camera_source          = camera_source
        self.faiss_index_path       = faiss_index_path
        self.faiss_metadata_path    = faiss_metadata_path
        self.threshold              = threshold               # FIX: was hardcoded 0.2
        self.process_every_n_frames = process_every_n_frames  # FIX: was hardcoded 5
        self.resize_width           = resize_width
        self.unknown_cooldown_sec   = unknown_cooldown_sec
        self.embedding_min_similarity = embedding_min_similarity
        self.pose_predictor = pose_predictor

        self.logger = logging.getLogger(f"Camera-{camera_id}")
        if debug_mode:
            self.logger.setLevel(logging.DEBUG)

        # Runtime state
        self.running       = False
        self.cap           = None
        self.app           = None
        self.faiss_index   = None
        self.faiss_ids     = []
        self.frame_counter = 0

        # Thread-safe result cache for the display loop
        self.cached_results: list = []
        self.results_lock = threading.Lock()

        # Workers
        self.recognition_queue  = Queue(maxsize=1)   # size=1 auto-drops stale frames
        self.save_queue         = Queue(maxsize=30)
        self.recognition_thread = None
        self.save_thread        = None

        # ── Unknown dedup ────────────────────────────────────────────────────
        # WHY a shared pool instead of per-identity keys:
        #   We don't know who the person is, so we can't assign stable keys.
        #   Original bug used one "_unknown_" key → the first unknown's cooldown
        #   timer blocked ALL other unknown faces for the full window.
        #   A shared embedding pool correctly handles multiple simultaneous
        #   strangers: each new face is checked against recently-saved embeddings,
        #   so different people pass while the same face is deduplicated.
        self.unknown_last_save = 0.0
        self.unknown_emb_pool  = deque(maxlen=DEDUP_HISTORY_SIZE)

        # FPS / perf
        self.fps_start_time    = time.time()
        self.fps_frame_count   = 0
        self.current_fps       = 0.0
        self.detection_times   = deque(maxlen=30)
        self.recognition_times = deque(maxlen=30)
        self.total_unknown_saved = 0
        self.front_face_thresh = float(os.getenv("FRONT_FACE_THRESH", 0.70))
        os.makedirs(UNKNOWN_CAPTURES_ROOT, exist_ok=True)
        self._init_models()
        if self.pose_predictor is None:
            self.logger.warning("[POSE] No pose_predictor — all face angles accepted")

    # ─────────────────────────────────────────────────────────────────────────
    # Init
    # ─────────────────────────────────────────────────────────────────────────

    def _init_models(self):
        try:
            self.app = get_shared_model(
                model_name=ARC_FACE_MODEL,
                det_size=DET_SIZE,
                det_thresh=DET_THRESH,
                ctx_id=0,
            )
            self.logger.info("✓ InsightFace model loaded")

            if os.path.exists(self.faiss_index_path):
                self.faiss_index = faiss.read_index(self.faiss_index_path)
                with open(self.faiss_metadata_path, "rb") as f:
                    self.faiss_ids = pickle.load(f)
                self.logger.info(
                    f"✓ FAISS index: {self.faiss_index.ntotal} vectors, "
                    f"{len(self.faiss_ids)} IDs"
                )
            else:
                self.logger.warning("No FAISS index found – starting empty")
                self.faiss_index = faiss.IndexFlatL2(512)
                self.faiss_ids   = []

        except Exception as e:
            self.logger.error(f"❌ Model init failed: {e}", exc_info=True)
            self.error_occurred.emit(f"Model init failed: {e}")

    def _init_camera(self) -> bool:
        try:
            src = self.camera_source

            cap_flags = (cv2.CAP_FFMPEG
                         if isinstance(src, str) and src.startswith(("rtsp", "http"))
                         else 0)

            self.cap = cv2.VideoCapture(src, cap_flags)

            # ── CRITICAL: set timeouts BEFORE isOpened() check ──
            # Without these, VideoCapture blocks the thread for 30+ seconds
            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 4000)  # 4s open
            self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 4000)  # 4s read
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot open: {src}")

            # Quick read test — confirms stream is actually delivering frames
            for _ in range(3):
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    break
            else:
                raise RuntimeError(f"Stream opened but no frames received: {src}")

            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            self.logger.info(f"✓ Camera {self.camera_id} – {w}×{h} @ {fps}fps")
            return True

        except Exception as e:
            self.logger.error(f"❌ Camera init failed: {e}", exc_info=True)
            if self.cap:
                self.cap.release()
                self.cap = None
            self.error_occurred.emit(f"Camera init failed: {e}")
            return False

    def _add_to_faiss(self, embedding: np.ndarray, uid: str):
        try:
            vec = embedding.astype("float32").reshape(1, -1)
            self.faiss_index.add(vec)
            self.faiss_ids.append(uid)

            dir_name = os.path.dirname(self.faiss_index_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            faiss.write_index(self.faiss_index, self.faiss_index_path)
            with open(self.faiss_metadata_path, "wb") as f:
                pickle.dump(self.faiss_ids, f)
            self.logger.info(f"FAISS total: {self.faiss_index.ntotal}")
        except Exception as e:
            self.logger.error(f"FAISS write failed: {e}", exc_info=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _resize_frame(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        if w <= self.resize_width:
            return frame, 1.0
        scale = self.resize_width / w
        return cv2.resize(frame, (self.resize_width, int(h * scale)), cv2.INTER_AREA), scale

    def _should_save_unknown(self, emb: np.ndarray) -> bool:
        """
        Two-layer dedup gate for unknown faces.
          1. Global cooldown  – enforce minimum gap between any unknown save.
          2. Embedding pool   – reject if too similar to a recently saved face.
        Updates state and returns True only when both layers pass.
        """
        now = time.time()
        if now - self.unknown_last_save < self.unknown_cooldown_sec:
            return False
        if _pool_has_duplicate(emb, self.unknown_emb_pool, self.embedding_min_similarity):
            self.logger.debug("⏭ Unknown embedding duplicate – skipping")
            return False
        self.unknown_last_save = now
        self.unknown_emb_pool.append(emb.copy())
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Recognition worker
    # ─────────────────────────────────────────────────────────────────────────

    def _recognition_worker(self):
        self.logger.info("🚀 Recognition worker started")

        while self.running:
            try:
                item = self.recognition_queue.get(timeout=0.1)
                if item is None:
                    break

                resized_frame, original_frame, scale = item

                t0    = time.time()
                faces = self.app.get(resized_frame, max_num=5)
                self.detection_times.append((time.time() - t0) * 1000)

                # FIX: no faces → clear display, skip all recognition logic
                if not faces:
                    with self.results_lock:
                        self.cached_results = []
                    continue

                # ── Pose filter: drop bad-angle faces before ANY embedding work ──────
                # ── Pose filter ──────────────────────────────────────────────
                pose_filtered = []
                for face in faces:
                    yaw, pitch, roll = estimate_pose_from_kps(
                        face.kps / scale, original_frame.shape[1]
                    )

                    if self.pose_predictor is not None:
                        pred = self.pose_predictor.predict_from_angles(yaw, pitch, roll)
                        self.logger.info(
                            f"[POSE] label={pred.label}  conf={pred.confidence:.2f}  "
                            f"yaw={yaw:.1f}  pitch={pitch:.1f}  roll={roll:.1f}"
                        )

                        # ── Gate: only allow MF (middle/front) with confidence >= 0.82 ──
                        if pred.label == "MF" and pred.confidence >= self.front_face_thresh:
                            pose_filtered.append(face)
                        else:
                            self.logger.info(
                                f"[POSE GATE] BLOCKED — label={pred.label}  conf={pred.confidence:.2f}")


                # Nothing left after pose filter → clear display, skip
                if not pose_filtered:
                    with self.results_lock:
                        self.cached_results = []
                    continue

                faces = pose_filtered  # replace with clean list
                # ─────────────────────────────────────────────────────────────────────

                results      = []
                valid_faces  = [f for f in faces if isinstance(f.normed_embedding, np.ndarray)]

                # ── Empty FAISS: every face is unknown ───────────────────────
                if self.faiss_index.ntotal == 0:
                    for face in valid_faces:
                        bbox = tuple((face.bbox / scale).astype(int))
                        results.append({"bbox": bbox, "name": "Unknown", "score": 0.0})

                        self._enqueue_unknown_save(face.normed_embedding, original_frame, face.kps / scale, 0.0)

                    with self.results_lock:
                        self.cached_results = results
                    continue

                # ── Batch FAISS search ───────────────────────────────────────
                if not valid_faces:
                    with self.results_lock:
                        self.cached_results = []
                    continue

                em_mat       = np.stack([f.normed_embedding for f in valid_faces]).astype("float32")
                dist, nn_idx = self.faiss_index.search(em_mat, 1)
                self.recognition_times.append((time.time() - t0) * 1000)

                for i, face in enumerate(valid_faces):
                    score = max(0.0, 1.0 - float(dist[i][0]) / 2.0)
                    bbox = tuple((face.bbox / scale).astype(int))

                    if score >= self.threshold:
                        # KNOWN — display only, nothing saved
                        user_id = self.faiss_ids[nn_idx[i][0]]
                        self.logger.info(f"KNOWN: {user_id}  score={score:.3f}")
                        results.append({"bbox": bbox, "name": user_id, "score": score})
                    else:
                        # UNKNOWN — add embedding to FAISS directly, no image save
                        self.logger.info(f"UNKNOWN  score={score:.3f} — indexing embedding")
                        results.append({"bbox": bbox, "name": "Unknown", "score": score})
                        self._enqueue_unknown_save(face.normed_embedding, original_frame, face.kps / scale, score)

                with self.results_lock:
                    self.cached_results = results

            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ Recognition error: {e}", exc_info=True)

        self.logger.info("🛑 Recognition worker stopped")

    # ─────────────────────────────────────────────────────────────────────────
    # Save helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _enqueue_unknown_save(
            self, embedding: np.ndarray, frame: np.ndarray, kps: np.ndarray, score: float
    ):
        if not self._should_save_unknown(embedding):
            return
        if self.save_queue.full():
            try:
                self.save_queue.get_nowait()
            except Empty:
                pass
        self.save_queue.put_nowait({
            "frame": frame,
            "kps": kps,
            "score": score,
            "embedding": embedding.copy(),  # ← add this
            "timestamp": datetime.now()
        })

    def _save_worker(self):
        while self.running:
            try:
                item = self.save_queue.get(timeout=0.5)
                if item is None:
                    break

                ts = item["timestamp"]
                embedding = item["embedding"]

                # ── 1. Save 300×300 crop for Phase 2 ─────────────────────────
                crop = _face_align.norm_crop(
                    item["frame"], landmark=item["kps"], image_size=FACE_CROP_SIZE
                )
                if crop is None or crop.size == 0:
                    continue

                path = self._write_unknown(crop, ts)
                if not path:
                    continue

                # ── 2. Add embedding to FAISS for Phase 1 matching ───────────
                uid = f"unknown_{ts.strftime('%Y%m%d_%H%M%S_%f')}"
                self._add_to_faiss(embedding, uid)

                self.total_unknown_saved += 1
                self.logger.info(f"Saved + indexed → {uid}  path={path}")
                self.face_saved.emit(uid, "Unknown", float(item["score"]), path)

            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Save worker error: {e}", exc_info=True)

    def _write_unknown(self, crop: np.ndarray, ts: datetime) -> str | None:
        """Write aligned crop to captures/unknown/{YYYYMMDD}/{timestamp}.jpg"""
        try:
            dir_path = os.path.join(UNKNOWN_CAPTURES_ROOT, ts.strftime("%Y%m%d"))
            os.makedirs(dir_path, exist_ok=True)
            path = os.path.join(dir_path, f"{ts.strftime('%Y%m%d_%H%M%S_%f')}.jpg")
            cv2.imwrite(path, crop, JPEG_QUALITY)
            return path
        except Exception as e:
            self.logger.error(f"❌ Disk write failed: {e}", exc_info=True)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # FPS
    # ─────────────────────────────────────────────────────────────────────────

    def _tick_fps(self):
        self.fps_frame_count += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed < 1.0:
            return
        self.current_fps = self.fps_frame_count / elapsed
        self.fps_updated.emit(self.current_fps)
        if self.detection_times:
            avg_det = float(np.mean(self.detection_times))
            avg_rec = float(np.mean(self.recognition_times)) if self.recognition_times else 0.0
            self.logger.info(
                f"FPS={self.current_fps:.1f}  det={avg_det:.1f}ms  rec={avg_rec:.1f}ms  "
                f"unknown_saved={self.total_unknown_saved}"
            )
        self.fps_frame_count = 0
        self.fps_start_time  = time.time()

    # ─────────────────────────────────────────────────────────────────────────
    # Main loop
    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        if not self._init_camera():
            return

        self.running = True
        self.recognition_thread = threading.Thread(target=self._recognition_worker, daemon=True)
        self.save_thread        = threading.Thread(target=self._save_worker, daemon=True)
        self.recognition_thread.start()
        self.save_thread.start()
        self.logger.info("✓ FRS Phase 1 camera worker running")

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.logger.warning("Frame read failed – reconnecting…")
                self.cap.release()
                time.sleep(1)
                if not self._init_camera():
                    break
                continue

            self.frame_counter += 1
            display_frame, scale = self._resize_frame(frame)

            if self.frame_counter % self.process_every_n_frames == 0:
                if self.recognition_queue.full():
                    try:
                        self.recognition_queue.get_nowait()
                    except Empty:
                        pass
                self.recognition_queue.put_nowait((display_frame, frame, scale))

            with self.results_lock:
                current_results = self.cached_results.copy()

            self._tick_fps()
            self.frame_ready.emit(display_frame.copy(), current_results)
            time.sleep(0.001)

        self._stop_workers()
        if self.cap:
            self.cap.release()
        self.logger.info("✓ Camera worker stopped")

    # ─────────────────────────────────────────────────────────────────────────
    # Shutdown
    # ─────────────────────────────────────────────────────────────────────────

    def _stop_workers(self):
        self.logger.info("Stopping workers…")
        for q in (self.recognition_queue, self.save_queue):
            try:
                q.put(None, timeout=1)
            except Exception:
                pass
        for t in (self.recognition_thread, self.save_thread):
            if t:
                t.join(timeout=3)

    def stop(self):
        self.logger.info("Stop requested")
        self.running = False
        self.wait(5000)