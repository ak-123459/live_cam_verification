import threading
import numpy as np
import logging
from queue import Queue, Empty
from app.workers.model_manager import get_shared_model, ModelManager
from dotenv import load_dotenv
import os

load_dotenv()



logger = logging.getLogger("RecognitionDispatcher")


MAX_FRAME_QUEUE = int(os.getenv("MAX_FRAME_QUEUE",2))
MAX_DETECTION = int(os.getenv("MAX_FACES",20))



class RecognitionDispatcher:
    """
    Single ONNX inference thread shared across all cameras.
    Each camera submits frames and gets results back via per-camera callbacks.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._queue   = Queue(maxsize=MAX_FRAME_QUEUE)   # max 2 cameras × 2 frames buffered
        self._running = False
        self._thread  = None
        self._app     = get_shared_model()

        logger.info("✓ RecognitionDispatcher created")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._worker, daemon=True, name="SharedRecognitionWorker"
        )
        self._thread.start()
        logger.info("✓ Shared recognition worker started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def submit(self, camera_id: str, frame: np.ndarray,
               original_frame: np.ndarray, scale: float,
               callback):
        """
        Submit a frame for recognition.
        callback(camera_id, faces, original_frame, scale) is called
        from the worker thread when results are ready.
        """
        item = {
            "camera_id":      camera_id,
            "frame":          frame,
            "original_frame": original_frame,
            "scale":          scale,
            "callback":       callback,
        }
        # Drop oldest if full — keeps latency low
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except Empty:
                pass
        self._queue.put_nowait(item)

    def _worker(self):
        logger.info("[Dispatcher] worker thread started")
        det_size = ModelManager._config['det_size']

        while self._running:
            try:
                item = self._queue.get(timeout=0.1)
            except Empty:
                continue

            try:
                faces = self._app.get(item["frame"], max_num=MAX_DETECTION)
                item["callback"](
                    item["camera_id"],
                    faces,
                    item["original_frame"],
                    item["scale"],
                )
            except Exception as e:
                logger.error(f"[Dispatcher] inference error: {e}", exc_info=True)

        logger.info("[Dispatcher] worker thread stopped")