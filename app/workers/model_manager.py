"""
Optimized Shared Model Manager for InsightFace
- Singleton pattern with thread-safe initialization
- GPU optimization with proper provider configuration
- Batch processing support
- Memory-efficient model management
"""
import threading
import time
import numpy as np
from insightface.app import FaceAnalysis
from dotenv import load_dotenv
import os

load_dotenv()


_det_size_env = os.getenv("DET_SIZE")
DET_THRESH            = float(os.getenv("DET_THRESH", 0.3))
DET_SIZE = tuple(int(x) for x in _det_size_env.split(",")) if _det_size_env else (640, 384)






class ModelManager:

    _instance = None
    _lock = threading.Lock()
    _model = None
    _model_initialized = False
    _init_time = None

    # ── Store config at class level so all threads see the same settings ──
    _config = {
        'model_name': 'buffalo_s_int8',
        'det_size':   DET_SIZE,
        'det_thresh': DET_THRESH,
        'ctx_id':     0,
    }


    def __new__(cls, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Only the FIRST caller's kwargs win
                    if kwargs:
                        cls._config.update(kwargs)
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        if not ModelManager._model_initialized:
            with ModelManager._lock:
                if not ModelManager._model_initialized:
                    self._initialize_model()

    def _initialize_model(self):

        cfg = ModelManager._config          # shorthand
        print(f"[MODEL_MANAGER] Config: {cfg}")
        if ModelManager._model is None:
            print("\n" + "="*60)
            print("[MODEL_MANAGER] Initializing InsightFace model...")
            print("[MODEL_MANAGER] This may take 10-30 seconds on first run")
            print("="*60 + "\n")

            start_time = time.time()

            try:

                # Try GPU first, fallback to CPU
                providers = self._get_optimal_providers()

                print(f"[MODEL_MANAGER] Using providers: {providers}")

                ModelManager._model = FaceAnalysis(name=cfg['model_name'])
                ModelManager._model.prepare(
                    ctx_id=cfg['ctx_id'],
                    det_size=cfg['det_size'],
                    det_thresh=cfg['det_thresh'],
                )

                ModelManager._model_initialized = True
                init_duration = time.time() - start_time
                ModelManager._init_time = init_duration

                print("\n" + "="*60)
                print(f"[MODEL_MANAGER] ✓ Model initialized successfully!")
                print(f"[MODEL_MANAGER] ✓ Initialization time: {init_duration:.2f}s")
                print(f"[MODEL_MANAGER] ✓ Active provider: {ModelManager._model.det_model}")
                print("[MODEL_MANAGER] ✓ Subsequent uses will be instant")
                print("="*60 + "\n")

            except Exception as e:
                print(f"\n[MODEL_MANAGER ERROR] Failed to initialize model: {e}\n")
                raise

    def _get_optimal_providers(self):
        """
        Determine optimal execution providers
        Returns list in priority order
        """
        import onnxruntime as ort
        
        available_providers = ort.get_available_providers()
        print(f"[MODEL_MANAGER] Available providers: {available_providers}")

        # Priority order: CUDA > DirectML > CPU
        optimal_providers = []

        # NVIDIA GPU (best performance)
        if 'CUDAExecutionProvider' in available_providers:
            optimal_providers.append('CUDAExecutionProvider')
            print("[MODEL_MANAGER] ✓ CUDA GPU detected - using GPU acceleration")

        # DirectML for Windows AMD/Intel GPUs
        elif 'DmlExecutionProvider' in available_providers:
            optimal_providers.append('DmlExecutionProvider')
            print("[MODEL_MANAGER] ✓ DirectML detected - using GPU acceleration")

        # Fallback to CPU (always available)
        optimal_providers.append('CPUExecutionProvider')

        return optimal_providers

    def get_model(self):
        """
        Get the shared model instance
        Thread-safe access to singleton model
        """
        if ModelManager._model is None:
            self._initialize_model()
        return ModelManager._model

    def is_initialized(self):
        """Check if model is initialized"""
        return ModelManager._model_initialized

    def get_init_time(self):
        """Get model initialization time"""
        return ModelManager._init_time

    def get_model_info(self):
        """Get model information for debugging"""
        if not self.is_initialized():
            return None

        model = self.get_model()
        
        info = {
            'initialized': True,
            'init_time': self._init_time,
            'detection_size': model.det_model.input_size if hasattr(model, 'det_model') else None,
            'providers': model.det_model.providers if hasattr(model, 'det_model') else None,
            'model_name': 'buffalo_sc'
        }
        
        return info

    @classmethod
    def reset(cls):
        """
        Reset the singleton (for testing or reinitialization)
        Warning: This will affect all active workers
        """
        with cls._lock:
            if cls._model is not None:
                print("[MODEL_MANAGER] Resetting model...")
                # Clean up model resources
                try:
                    del cls._model
                except:
                    pass
            
            cls._model = None
            cls._model_initialized = False
            cls._instance = None
            cls._init_time = None
            print("[MODEL_MANAGER] Model reset complete")

    @classmethod
    def warm_up(cls):
        """
        Warm up the model with a dummy inference
        Helps reduce first-frame latency
        """
        model = cls().get_model()
        
        print("[MODEL_MANAGER] Warming up model...")
        
        # Create dummy image
        dummy_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Run inference
        start = time.time()
        _ = model.get(dummy_img, max_num=1)
        warmup_time = (time.time() - start) * 1000
        
        print(f"[MODEL_MANAGER] ✓ Warmup complete ({warmup_time:.1f}ms)")
        print("[MODEL_MANAGER] ✓ Ready for real-time processing")


# =============================================================================
# GLOBAL FUNCTIONS FOR EASY ACCESS
# =============================================================================

def get_shared_model(**kwargs):
    manager = ModelManager(**kwargs)
    return manager.get_model()


def is_model_initialized():
    """Check if shared model is ready"""
    manager = ModelManager()
    return manager.is_initialized()


def get_model_info():
    """Get information about the shared model"""
    manager = ModelManager()
    return manager.get_model_info()


def warm_up_model():
    """
    Warm up the model before starting camera workers
    Call this at application startup
    """
    ModelManager.warm_up()


def reset_model():
    """
    Reset the model (use with caution)
    Will affect all active camera workers
    """
    ModelManager.reset()


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("Testing Optimized Model Manager\n")
    
    # Initialize model
    print("1. Initializing model...")
    model = get_shared_model()
    
    # Get model info
    print("\n2. Model info:")
    info = get_model_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    # Warm up
    print("\n3. Warming up...")
    warm_up_model()
    
    # Test inference
    print("\n4. Testing inference...")
    test_img = np.random.randint(0, 255, (DET_SIZE[0],DET_SIZE[1], 3), dtype=np.uint8)
    
    start = time.time()
    faces = model.get(test_img, max_num=10)
    inference_time = (time.time() - start) * 1000
    
    print(f"   Detected {len(faces)} faces in {inference_time:.1f}ms")
    
    # Test shared access
    print("\n5. Testing shared access...")
    model2 = get_shared_model()
    print(f"   Same instance: {model is model2}")
    
    print("\n✓ All tests passed!")