import threading
import numpy as np
import onnxruntime as ort
from app.config import MODEL_PATH, CLIP_MEAN, CLIP_STD


class Embedder:
    """Singleton ONNX inference session."""
    _instance  = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._ready = False
                    cls._instance = obj
        return cls._instance

    def __init__(self):
        if self._ready:
            return
        with self._init_lock:
            if self._ready:
                return
            self._setup()
            self._ready = True

    def _setup(self):
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers()
            else ["CPUExecutionProvider"]
        )
        opts = ort.SessionOptions()
        opts.execution_mode           = ort.ExecutionMode.ORT_PARALLEL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.inter_op_num_threads     = 4
        opts.intra_op_num_threads     = 4

        self._session  = ort.InferenceSession(MODEL_PATH, opts, providers)
        self._in_name  = self._session.get_inputs()[0].name
        self._out_name = self._session.get_outputs()[0].name
        self._lock     = threading.Lock()
        self._mean     = np.array(CLIP_MEAN, dtype=np.float32)
        self._std      = np.array(CLIP_STD,  dtype=np.float32)
        # print(f"[embedder] Model loaded: {MODEL_PATH}")
        # print(f"[embedder] Input: {self._in_name}  Output: {self._out_name}")

    def embed_batch(self, batch: np.ndarray) -> np.ndarray:
        """batch: (N,3,224,224) → returns (N, EMB_DIM) L2-normalized"""
        with self._lock:
            raw = self._session.run([self._out_name], {self._in_name: batch})[0]

        # Some exported models hardcode batch=1 in output shape
        if raw.shape[0] == 1 and batch.shape[0] > 1:
            results = []
            for i in range(batch.shape[0]):
                with self._lock:
                    out = self._session.run(
                        [self._out_name], {self._in_name: batch[i:i+1]}
                    )[0]
                results.append(out[0])
            raw = np.stack(results)

        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        return (raw / norms).astype(np.float32)

    @property
    def mean(self) -> np.ndarray:
        return self._mean

    @property
    def std(self) -> np.ndarray:
        return self._std