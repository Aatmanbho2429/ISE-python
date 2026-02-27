import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from psd_tools import PSDImage
from app.config import NUM_WORKERS
from app.core.embedder import Embedder


def load_image_fast(path: str) -> Image.Image:
    ext = path.lower()

    # ── PSD / PSB ────────────────────────────────────────────────────────
    if ext.endswith((".psd", ".psb")):
        psd = PSDImage.open(path)
        img = psd.topil()           # pre-rendered thumbnail — fast
        if img is None:
            img = psd.composite()   # fallback: renders all layers — slow
        if img is None:
            raise RuntimeError(f"PSD/PSB load failed: {path}")
        return img.convert("RGB")

    # ── TIFF ─────────────────────────────────────────────────────────────
    if ext.endswith((".tif", ".tiff")):
        img = Image.open(path)
        # Some multi-page TIFFs embed a small thumbnail on page 1
        # Use it if it exists and is genuinely small (i.e. it's a preview)
        try:
            img.seek(1)
            if max(img.size) <= 512:
                return img.convert("RGB")
        except Exception:
            pass
        # No usable thumbnail — decompress full image
        img.seek(0)
        return img.convert("RGB")

    # ── Everything else (JPG, PNG, etc.) ─────────────────────────────────
    return Image.open(path).convert("RGB")


def preprocess_single(path: str) -> np.ndarray:
    embedder = Embedder()
    img = load_image_fast(path)
    img = img.resize((224, 224), Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = (arr - embedder.mean) / embedder.std
    arr = np.transpose(arr, (2, 0, 1))
    return arr


def preprocess_batch_parallel(paths: list) -> tuple:
    results = [None] * len(paths)

    def load_one(args):
        i, path = args
        try:
            results[i] = (preprocess_single(path), path, None)
        except Exception as e:
            results[i] = (None, path, str(e))

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        list(ex.map(load_one, enumerate(paths)))

    batch, valid_paths, failed = [], [], []
    for arr, path, err in results:
        if arr is not None:
            batch.append(arr)
            valid_paths.append(path)
        else:
            failed.append({"file": path, "reason": err})

    if not batch:
        return None, [], failed

    return np.stack(batch).astype(np.float32), valid_paths, failed