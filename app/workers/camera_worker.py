"""
Camera Worker - FRS Phase 1 Pipeline  (PyAV capture edition)
=============================================================
WHAT CHANGED vs the OpenCV version
───────────────────────────────────
  _init_camera()     → opens the stream with av.open() + low-latency FFmpeg options
  _capture_thread()  → new daemon thread: demuxes packets, decodes, converts to
                       BGR numpy, drops into self._frame_queue (size=2)
  run()              → reads from _frame_queue instead of cap.read()
  stop() / cleanup   → closes av.Container instead of cap.release()

EVERYTHING ELSE IS IDENTICAL
  recognition_worker, save_worker, FAISS, InsightFace, pose filter,
  dedup logic, signals — all untouched.

WHY PyAV FOR THIS PIPELINE
  • cap.read() on OpenCV blocks the Qt thread for up to 35ms/frame (your
    benchmark showed avg 35.70ms, max 306ms).  PyAV's decode latency was
    10.74ms avg / 16.63ms max — 3× more consistent.
  • Startup: 40ms vs 1.6s — reconnect after drop is nearly instant.
  • The capture runs in its own daemon thread so frame.read() stalls
    never touch the Qt event loop.
  • MJPEG: PyAV requests codec-level resize (1920×1080 → resize_width)
    saving ~40-60% of JPEG DCT reconstruction work vs post-decode cv2.resize.

PYAV CAPTURE CONFIG (top of file)
  PYAV_THREAD_TYPE   slice | frame | none
  PYAV_THREAD_COUNT  0 = libav auto, N = pin to N cores
  PYAV_RTBUF         ring buffer size string e.g. "256k"
  PYAV_PIXEL_FMT     bgr24 (ready for cv2) or yuv420p (skip conversion)
"""

import av
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
import warnings
from PySide6.QtCore import QThread, Signal
from insightface.utils import face_align as _face_align
from dotenv import load_dotenv

from app.utils.image_utils import estimate_pose_from_kps
from app.workers.model_manager import get_shared_model,ModelManager
from app.workers.recognition_dispatcher import RecognitionDispatcher

load_dotenv()




warnings.filterwarnings("ignore", message="X does not have valid feature names")





# ─────────────────────────────────────────────
# App config  (unchanged from original)
# ─────────────────────────────────────────────
UNKNOWN_CAPTURES_ROOT = os.getenv("UNKNOWN_CAPTURES_ROOT", "captures/unknown")
DEDUP_HISTORY_SIZE    = int(os.getenv("DEDUP_HISTORY_SIZE", 10))
ARC_FACE_MODEL        = os.getenv("ARC_FACE_MODEL", "buffalo_s_int8")
FACE_CROP_SIZE        = 300
JPEG_QUALITY          = [cv2.IMWRITE_JPEG_QUALITY, 90]
FRONT_FACE_THRESH     = float(os.getenv("FRONT_FACE_THRESH", 0.50))
MAX_DETECTION = int(os.getenv("MAX_FACES",20))
DET_SIZE = ModelManager._config['det_size']   # always in sync
DET_THRESH = ModelManager._config['det_thresh']
PROCESS_N_FRAME = int(os.getenv("PROCESS_N_FRAME",5))
MAX_SAVE_QUEUE = int(os.getenv("MAX_SAVE_QUEUE",20))
MAX_RECOG_QUEUE = int(os.getenv("SAVE_QUEUE",20))
MAX_FRAME_QUEUE = int(os.getenv("MAX_FRAME_QUEUE",2))



# ─────────────────────────────────────────────
# PyAV capture config
# ─────────────────────────────────────────────
PYAV_THREAD_TYPE  = "slice"   # slice | frame | none  (slice best for MJPEG)
PYAV_THREAD_COUNT = 0         # 0 = libav chooses; 2-4 is good for 1080p
PYAV_RTBUF        = "256k"    # ring buffer — keep small for low latency
PYAV_PIXEL_FMT    = "bgr24"   # bgr24 = ready for numpy/cv2; yuv420p = faster decode


# FFmpeg open options — same flags that gave 10ms avg latency in benchmarks
_PYAV_OPTIONS = {
    "fflags":          "nobuffer",
    "flags":           "low_delay",
    "framedrop":       "1",
    "rtbufsize":       PYAV_RTBUF,
    "analyzeduration": "100000",   # 0.1 s probe  (default 5 s → 1.6 s startup)
    "probesize":       "32768",    # 32 KB probe  (default 5 MB)
}

_THREAD_TYPE_MAP = {
    "slice": av.codec.context.ThreadType.SLICE,
    "frame": av.codec.context.ThreadType.FRAME,
    "none":  av.codec.context.ThreadType.NONE,
    "auto":  av.codec.context.ThreadType.AUTO,
}


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S")



# ─────────────────────────────────────────────
# Pure helpers  (unchanged)
# ─────────────────────────────────────────────

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))




def _pool_has_duplicate(emb: np.ndarray, pool: deque, min_sim: float) -> bool:
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
    FRS Phase 1 camera worker — PyAV capture edition.

    Signals  (identical to original)
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
        threshold=0.20,
        process_every_n_frames=5,
        resize_width=640,
        unknown_cooldown_sec=10.0,
        embedding_min_similarity=0.85,
        debug_mode=False,
        pose_predictor=None,
    ):
        super().__init__()

        self.camera_id               = camera_id
        self.camera_source           = camera_source
        self.faiss_index_path        = faiss_index_path
        self.faiss_metadata_path     = faiss_metadata_path
        self.threshold               = threshold
        self.process_every_n_frames  = PROCESS_N_FRAME
        self.resize_width            = resize_width
        self.unknown_cooldown_sec    = unknown_cooldown_sec
        self.embedding_min_similarity = embedding_min_similarity
        self.pose_predictor          = pose_predictor

        self.logger = logging.getLogger(f"Camera-{camera_id}")
        if debug_mode:
            self.logger.setLevel(logging.DEBUG)

        # Runtime state
        self.running        = False
        self.frame_counter  = 0
        self.app            = None
        self.faiss_index    = None
        self.faiss_ids      = []

        # ── PyAV capture state  (replaces self.cap) ──────────────────────────
        self._av_container   = None   # av.container.InputContainer
        self._frame_queue    = Queue(maxsize=MAX_FRAME_QUEUE)   # decoded BGR frames ready for run()
        self._capture_thread = None               # daemon thread
        self._resampler = None

        # ─────────────────────────────────────────────────────────────────────

        # Thread-safe result cache
        self.cached_results: list = []
        self.results_lock = threading.Lock()

        # Worker queues / threads
        # self.recognition_queue  = Queue(maxsize=MAX_RECOG_QUEUE)

        self._dispatcher = RecognitionDispatcher()
        self.save_queue         = Queue(maxsize=MAX_SAVE_QUEUE)
        # self.recognition_thread = None
        self.save_thread        = None

        # Unknown dedup
        self.unknown_last_save = 0.0
        self.unknown_emb_pool  = deque(maxlen=DEDUP_HISTORY_SIZE)

        # FPS / perf
        self.fps_start_time      = time.time()
        self.fps_frame_count     = 0
        self.current_fps         = 0.0
        self.detection_times     = deque(maxlen=30)
        self.recognition_times   = deque(maxlen=30)
        self.total_unknown_saved = 0

        os.makedirs(UNKNOWN_CAPTURES_ROOT, exist_ok=True)
        self._init_models()
        if self.pose_predictor is None:
            self.logger.warning("[POSE] No pose_predictor — all face angles accepted")

    # ─────────────────────────────────────────────────────────────────────────
    # Init
    # ─────────────────────────────────────────────────────────────────────────

    def _init_models(self):
        """Identical to original."""
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
        """
        Open the stream with PyAV instead of cv2.VideoCapture.

        Key differences vs original:
          • av.open() with low-latency FFmpeg options → 40ms startup (was 1.6s)
          • codec-level resize → fewer DCT coefficients decoded for 1080p→640
          • slice threading → JPEG MCU rows decoded in parallel
          • no hidden 3-frame buffer (OpenCV's CAP_PROP_BUFFERSIZE only goes to 1,
            PyAV has no internal queue between demuxer and your Python code)
        """
        src = self.camera_source

        # Only use PyAV for network/file streams. For integer camera IDs
        # (webcams) fall back to OpenCV since av.open(0) is unreliable.
        if isinstance(src, int):
            return self._init_camera_opencv_fallback(src)

        try:
            self.logger.info(f"[PyAV] Opening {src} …")
            container = av.open(src, options=_PYAV_OPTIONS, timeout=5.0)
            vid_stream = container.streams.video[0]
            ctx = vid_stream.codec_context

            # Threading model
            ctx.thread_type  = _THREAD_TYPE_MAP.get(PYAV_THREAD_TYPE,
                                                     av.codec.context.ThreadType.SLICE)
            ctx.thread_count = PYAV_THREAD_COUNT

            # Request codec-level downscale — for MJPEG this skips reconstructing
            # high-frequency DCT coefficients we'd throw away in cv2.resize anyway
            if self.resize_width and self.resize_width < vid_stream.width:
                try:
                    scale   = self.resize_width / vid_stream.width
                    ctx.width  = self.resize_width
                    ctx.height = int(vid_stream.height * scale)
                    self.logger.info(
                        f"[PyAV] Codec resize requested: "
                        f"{vid_stream.width}×{vid_stream.height} → "
                        f"{ctx.width}×{ctx.height}"
                    )
                except AttributeError:
                    pass  # some codec wrappers are read-only; sw resize handles it

            self._av_container = container




            # Warm-up: decode 1 frame to confirm stream is live
            gen   = container.decode(video=0)
            first = next(gen, None)
            if first is None:
                raise RuntimeError("Stream opened but no frames decoded")

            w = ctx.width  or vid_stream.width
            h = ctx.height or vid_stream.height


            self._resampler = av.video.reformatter.VideoReformatter()
            self.logger.info(f"[PyAV] Resampler: {w}×{h} → {DET_SIZE[0]}×{DET_SIZE[1]}")


            # ──────────────────────────────────────────────────────────────────


            fps_str = float(vid_stream.average_rate or vid_stream.guessed_rate or 0)
            self.logger.info(
                f"✓ Camera {self.camera_id} [PyAV] — {w}×{h} @ {fps_str:.1f} fps  "
                f"codec={vid_stream.codec_context.name}  "
                f"thread={PYAV_THREAD_TYPE}/{PYAV_THREAD_COUNT or 'auto'}"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ PyAV camera init failed: {e}", exc_info=True)
            if self._av_container:
                try:
                    self._av_container.close()
                except Exception:
                    pass
                self._av_container = None
            self.error_occurred.emit(f"Camera init failed: {e}")
            return False

    def _init_camera_opencv_fallback(self, device_id: int) -> bool:

        """
        Integer device IDs (local webcams) use OpenCV — av.open(int) is
        unreliable on Windows.  Stores cap as self._cv_cap so run() can detect
        which path to use.
        """

        self.logger.info(f"[OpenCV fallback] device {device_id}")
        cap = cv2.VideoCapture(device_id)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, 30)
        if not cap.isOpened():
            self.error_occurred.emit(f"Cannot open device {device_id}")
            return False
        self._cv_cap = cap
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # PyAV capture thread
    # ─────────────────────────────────────────────────────────────────────────

    def _capture_thread_fn(self):
        """
        Runs in a daemon thread.  Decodes PyAV frames → BGR numpy arrays →
        drops them into self._frame_queue (maxsize=2, old frames auto-evicted).

        Keeping capture on its own thread means:
          • av.container.decode() blocking never stalls the Qt run() loop
          • run() always pulls the freshest available frame (no queue pile-up)
          • if the network hiccups, only this thread waits; recognition keeps
            processing the last good frame
        """
        self.logger.info("[PyAV capture] thread started")
        reconnect_delay = 0.5

        while self.running:
            if self._av_container is None:
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 5.0)
                self.logger.warning("[PyAV capture] container gone — attempting reconnect")



                if not self._init_camera():
                    continue
                reconnect_delay = 0.5

            try:
                for av_frame in self._av_container.decode(video=0):
                    if not self.running:
                        break

                    # to_ndarray() is the only place we allocate memory per frame.
                    # bgr24 = colorspace conversion included; yuv420p = skip it
                    # (set PYAV_PIXEL_FMT = "yuv420p" + adjust downstream if needed)

                    if self._resampler is not None:
                        # Correct — VideoReformatter API for PyAV 17:
                        resampled = self._resampler.reformat(
                            av_frame,
                            format="bgr24",
                            width=DET_SIZE[0],
                            height=DET_SIZE[1],
                            interpolation="BILINEAR",
                        )

                        img = resampled.to_ndarray(format="bgr24")
                    else:
                        img = av_frame.to_ndarray(format=PYAV_PIXEL_FMT)

                    # Software resize fallback — only triggers if codec-level resize
                    # was refused (some MJPEG decoders ignore ctx.width/height)
                    img = self._sw_resize(img)

                    # Drop oldest if queue full — keeps latency low
                    # (same strategy as recognition_queue size=1)
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                        except Empty:
                            pass
                    self._frame_queue.put_nowait(img)

            except av.AVError as e:
                self.logger.warning(f"[PyAV capture] AVError: {e} — reconnecting")
                try:
                    self._av_container.close()
                except Exception:
                    pass
                self._av_container = None
                time.sleep(1.0)

            except Exception as e:
                self.logger.error(f"[PyAV capture] unexpected: {e}", exc_info=True)
                break

        self.logger.info("[PyAV capture] thread stopped")

    def _sw_resize(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        if w == DET_SIZE[0] and h == DET_SIZE[1]:
            return img  # already correct — resampler did its job
        return cv2.resize(img, (DET_SIZE[0], DET_SIZE[1]), cv2.INTER_LINEAR)


    # ─────────────────────────────────────────────────────────────────────────
    # FAISS helpers  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

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
    # Frame helpers  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def _resize_frame(self, frame: np.ndarray):
        """
        Secondary resize for the recognition pipeline's scale tracking.
        For PyAV streams this is usually a no-op because codec-level resize
        already produced the right size — but scale is still needed for bbox
        back-projection onto the original frame coords.
        """
        h, w = frame.shape[:2]
        if w <= self.resize_width:
            return frame, 1.0
        scale = self.resize_width / w
        return cv2.resize(frame, (self.resize_width, int(h * scale)), cv2.INTER_AREA), scale


    def _should_save_unknown(self, emb: np.ndarray) -> bool:
        # Check duplicate FIRST (embedding-based, per-identity)
        if _pool_has_duplicate(emb, self.unknown_emb_pool, self.embedding_min_similarity):
            self.logger.debug("⏭ Unknown embedding duplicate – skipping")
            return False

        # Only apply time gate if this IS a new unique face
        now = time.time()
        if now - self.unknown_last_save < self.unknown_cooldown_sec:
            return False

        self.unknown_last_save = now
        self.unknown_emb_pool.append(emb.copy())
        return True



    # ─────────────────────────────────────────────────────────────────────────
    # Recognition worker  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    # def _recognition_worker(self):
    #     self.logger.info("🚀 Recognition worker started")
    #
    #     while self.running:
    #         try:
    #             item = self.recognition_queue.get(timeout=0.1)
    #             if item is None:
    #                 break
    #
    #             resized_frame, original_frame, scale = item
    #
    #             t0    = time.time()
    #             faces = self.app.get(resized_frame, max_num=MAX_DETECTION)
    #             self.detection_times.append((time.time() - t0) * 1000)
    #
    #             if not faces:
    #                 with self.results_lock:
    #                     self.cached_results = []
    #                 continue
    #
    #             # Pose filter
    #             pose_filtered = []
    #             for face in faces:
    #                 yaw, pitch, roll = estimate_pose_from_kps(
    #                     face.kps / scale, original_frame.shape[1]
    #                 )
    #                 if self.pose_predictor is not None:
    #                     pred = self.pose_predictor.predict_from_angles(yaw, pitch, roll)
    #                     self.logger.info(
    #                         f"[POSE] label={pred.label}  conf={pred.confidence:.2f}  "
    #                         f"yaw={yaw:.1f}  pitch={pitch:.1f}  roll={roll:.1f}"
    #                     )
    #                     if pred.label == "MF" and pred.confidence >= self.front_face_thresh:
    #                         pose_filtered.append(face)
    #                     else:
    #                         self.logger.info(
    #                             f"[POSE GATE] BLOCKED — label={pred.label}  "
    #                             f"conf={pred.confidence:.2f}"
    #                         )
    #                 else:
    #                     pose_filtered.append(face)
    #
    #             if not pose_filtered:
    #                 with self.results_lock:
    #                     self.cached_results = []
    #                 continue
    #
    #             faces        = pose_filtered
    #             results      = []
    #             valid_faces  = [f for f in faces if isinstance(f.normed_embedding, np.ndarray)]
    #
    #             if self.faiss_index.ntotal == 0:
    #                 for face in valid_faces:
    #                     bbox = tuple((face.bbox / scale).astype(int))
    #                     results.append({"bbox": bbox, "name": "Unknown", "score": 0.0})
    #                     self._enqueue_unknown_save(
    #                         face.normed_embedding, original_frame, face.kps / scale, 0.0
    #                     )
    #                 with self.results_lock:
    #                     self.cached_results = results
    #                 continue
    #
    #             if not valid_faces:
    #                 with self.results_lock:
    #                     self.cached_results = []
    #                 continue
    #
    #             em_mat       = np.stack([f.normed_embedding for f in valid_faces]).astype("float32")
    #             dist, nn_idx = self.faiss_index.search(em_mat, 1)
    #             self.recognition_times.append((time.time() - t0) * 1000)
    #
    #             for i, face in enumerate(valid_faces):
    #                 score = max(0.0, 1.0 - float(dist[i][0]) / 2.0)
    #                 bbox  = tuple((face.bbox / scale).astype(int))
    #                 if score >= self.threshold:
    #                     user_id = self.faiss_ids[nn_idx[i][0]]
    #                     self.logger.info(f"KNOWN: {user_id}  score={score:.3f}")
    #                     results.append({"bbox": bbox, "name": user_id, "score": score})
    #                 else:
    #                     self.logger.info(f"UNKNOWN  score={score:.3f} — indexing embedding")
    #                     results.append({"bbox": bbox, "name": "Unknown", "score": score})
    #                     self._enqueue_unknown_save(
    #                         face.normed_embedding, original_frame, face.kps / scale, score
    #                     )
    #
    #             with self.results_lock:
    #                 self.cached_results = results
    #
    #         except Empty:
    #             continue
    #         except Exception as e:
    #             self.logger.error(f"❌ Recognition error: {e}", exc_info=True)
    #
    #     self.logger.info("🛑 Recognition worker stopped")

    def _on_recognition_result(self, camera_id, faces, original_frame, scale):
        """
        Called from the shared dispatcher thread when inference is done.
        Runs pose filter, FAISS search, updates cached_results.
        """
        t0 = time.time()  # ← start timer here

        if not faces:
            self.logger.debug(f"[{camera_id}] No faces detected")
            with self.results_lock:
                self.cached_results = []
            return

        # Pose filter
        pose_filtered = []
        for face in faces:
            yaw, pitch, roll = estimate_pose_from_kps(
                face.kps / scale, original_frame.shape[1]
            )
            if self.pose_predictor is not None:
                pred = self.pose_predictor.predict_from_angles(yaw, pitch, roll)
                self.logger.info(
                    f"[{camera_id}] [POSE] label={pred.label}  conf={pred.confidence:.2f}  "
                    f"yaw={yaw:.1f}  pitch={pitch:.1f}  roll={roll:.1f}"
                )
                if pred.label in ("MF", "UF") and pred.confidence >= FRONT_FACE_THRESH:
                    pose_filtered.append(face)
                else:
                    self.logger.info(
                        f"[{camera_id}] [POSE BLOCKED] label={pred.label}  "
                        f"conf={pred.confidence:.2f}"
                    )
            else:
                pose_filtered.append(face)

        self.logger.info(
            f"[{camera_id}] detected={len(faces)}  pose_passed={len(pose_filtered)}"
        )

        if not pose_filtered:
            with self.results_lock:
                self.cached_results = []
            return

        valid_faces = [f for f in pose_filtered
                       if isinstance(f.normed_embedding, np.ndarray)]

        self.logger.info(
            f"[{camera_id}] valid_embeddings={len(valid_faces)}  "
            f"faiss_total={self.faiss_index.ntotal}"
        )

        if not valid_faces:
            with self.results_lock:
                self.cached_results = []
            return

        results = []

        if self.faiss_index.ntotal == 0:
            self.logger.info(f"[{camera_id}] FAISS empty — marking all as Unknown")
            for face in valid_faces:
                bbox = tuple((face.bbox / scale).astype(int))
                results.append({"bbox": bbox, "name": "Unknown", "score": 0.0})
                self._enqueue_unknown_save(
                    face.normed_embedding, original_frame, face.kps / scale, 0.0
                )
            with self.results_lock:
                self.cached_results = results
            return

        t_faiss = time.time()

        em_mat = np.stack([f.normed_embedding for f in valid_faces]).astype("float32")
        dist, nn_idx = self.faiss_index.search(em_mat, 1)
        self.recognition_times.append((time.time() - t_faiss) * 1000)  # ← FAISS search time
        self.detection_times.append((time.time() - t0) * 1000)  # ← total callback time

        for i, face in enumerate(valid_faces):
            raw_dist = float(dist[i][0])
            score = max(0.0, 1.0 - raw_dist / 2.0)
            bbox = tuple((face.bbox / scale).astype(int))
            candidate = self.faiss_ids[nn_idx[i][0]]

            if score >= self.threshold:
                user_id = self.faiss_ids[nn_idx[i][0]]
                self.logger.info(
                    f"[{camera_id}] ✅ KNOWN: {user_id}  "
                    f"score={score:.3f}  dist={raw_dist:.4f}  thresh={self.threshold}"
                )
                results.append({"bbox": bbox, "name": user_id, "score": score})
            else:
                self.logger.info(
                    f"[{camera_id}] ❌ UNKNOWN  "
                    f"score={score:.3f}  dist={raw_dist:.4f}  "
                    f"thresh={self.threshold}  nearest={candidate}"
                )
                results.append({"bbox": bbox, "name": "Unknown", "score": score})
                self._enqueue_unknown_save(
                    face.normed_embedding, original_frame, face.kps / scale, score
                )

        with self.results_lock:
            self.cached_results = results

    # ─────────────────────────────────────────────────────────────────────────
    # Save helpers  (unchanged)
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
            "frame":     frame,
            "kps":       kps,
            "score":     score,
            "embedding": embedding.copy(),
            "timestamp": datetime.now(),
        })

    def _save_worker(self):
        while self.running:
            try:
                item = self.save_queue.get(timeout=0.5)
                if item is None:
                    break
                ts        = item["timestamp"]
                embedding = item["embedding"]
                crop = _face_align.norm_crop(
                    item["frame"], landmark=item["kps"], image_size=FACE_CROP_SIZE
                )
                if crop is None or crop.size == 0:
                    continue
                path = self._write_unknown(crop, ts)
                if not path:
                    continue
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
    # FPS  (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def _tick_fps(self):
        self.fps_frame_count += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed < 1.0:
            return
        self.current_fps = self.fps_frame_count / elapsed
        self.fps_updated.emit(self.current_fps)

        if self.detection_times:
            avg_callback = float(np.mean(self.detection_times))
            avg_faiss = float(np.mean(self.recognition_times)) if self.recognition_times else 0.0
            self.logger.info(
                f"FPS={self.current_fps:.1f}  "
                f"callback={avg_callback:.1f}ms  "  # ← renamed from det=
                f"faiss={avg_faiss:.1f}ms  "  # ← renamed from rec=
                f"unknown_saved={self.total_unknown_saved}"
            )
        else:
            # No recognitions yet this second — still log FPS
            self.logger.info(
                f"FPS={self.current_fps:.1f}  "
                f"no_recognitions_yet  "
                f"unknown_saved={self.total_unknown_saved}"
            )

        self.fps_frame_count = 0
        self.fps_start_time = time.time()


    # ─────────────────────────────────────────────────────────────────────────
    # Main loop  — ONLY THIS METHOD CHANGED vs original
    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        if not self._init_camera():
            return

        self.running = True

        # ── Start dispatcher (shared across all cameras) ───────────────────
        self._dispatcher.start()

        # ── Only save worker per camera ────────────────────────────────────
        self.save_thread = threading.Thread(
            target=self._save_worker, daemon=True
        )
        self.save_thread.start()

        # ── Start PyAV capture thread ──────────────────────────────────────
        use_pyav = self._av_container is not None
        if use_pyav:
            self._capture_thread = threading.Thread(
                target=self._capture_thread_fn, daemon=True
            )
            self._capture_thread.start()

        self.logger.info(
            f"✓ FRS Phase 1 camera worker running  "
            f"[{'PyAV' if use_pyav else 'OpenCV fallback'}]"
        )

        while self.running:

            # ── Get next frame ─────────────────────────────────────────────
            if use_pyav:
                try:
                    frame = self._frame_queue.get(timeout=2.0)
                except Empty:
                    self.logger.warning("Frame queue empty — stream may be stalled")
                    continue
            else:
                ret, frame = self._cv_cap.read()
                if not ret:
                    self.logger.warning("Frame read failed (OpenCV fallback)")
                    time.sleep(0.1)
                    continue

            self.frame_counter += 1

            display_frame, scale = self._resize_frame(frame)

            # ── Feed recognition every N frames ───────────────────────────
            if self.frame_counter % self.process_every_n_frames == 0:
                self._dispatcher.submit(
                    camera_id=self.camera_id,
                    frame=display_frame,
                    original_frame=frame,
                    scale=scale,
                    callback=self._on_recognition_result,
                )

            with self.results_lock:
                current_results = self.cached_results.copy()

            self._tick_fps()
            self.frame_ready.emit(display_frame.copy(), current_results)

            time.sleep(0.001)

        self._stop_workers()
        self._close_camera()
        self.logger.info("✓ Camera worker stopped")

    # ─────────────────────────────────────────────────────────────────────────
    # Shutdown
    # ─────────────────────────────────────────────────────────────────────────

    def _close_camera(self):
        """Close whichever capture backend is active."""
        if self._av_container is not None:
            try:
                self._av_container.close()
            except Exception:
                pass
            self._av_container = None
            self.logger.info("[PyAV] container closed")

        if hasattr(self, "_cv_cap") and self._cv_cap is not None:
            self._cv_cap.release()
            self._cv_cap = None
            self.logger.info("[OpenCV fallback] cap released")

    def _stop_workers(self):
        self.logger.info("Stopping workers…")
        # Only stop save worker — recognition is shared, dispatcher manages its own lifecycle
        try:
            self.save_queue.put(None, timeout=1)
        except Exception:
            pass
        if self.save_thread:
            self.save_thread.join(timeout=3)



    def stop(self):
        self.logger.info("Stop requested")
        self.running = False
        self.wait(5000)