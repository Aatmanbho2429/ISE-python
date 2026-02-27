import os
import sys
import webview
from tkinter import filedialog
import json
import hashlib
import numpy as np
from PIL import Image
import onnxruntime as ort
import faiss
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor
import threading
from psd_tools import PSDImage
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64

# -------------------- Core Models --------------------

class BaseResponse:
    def __init__(self):
        self.status  = True
        self.message = ""
        self.code    = 200
        self.data    = {"success": [], "errors": [], "results": []}

# -------------------- Paths --------------------

def get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR  = get_exe_dir()
FAISS_DIR = os.path.join(BASE_DIR, "faiss")
os.makedirs(FAISS_DIR, exist_ok=True)

INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH  = os.path.join(FAISS_DIR, "meta.json")

IMAGE_EXTENSIONS          = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".psd", ".psb")
IMAGE_EXTENSIONS_FOR_FILE = "*.jpg *.jpeg *.png *.tiff *.tif *.psd *.psb"

BATCH_SIZE  = 64     # Increase to 128 if GPU has >8GB VRAM
NUM_WORKERS = 8      # Parallel image loading threads
HASH_BYTES  = 65536  # Read only first 64KB for fast dedup hashing
EMB_DIM     = 768    # CLIP vision model output dimension

# -------------------- Model --------------------

MODEL_PATH = os.path.join(BASE_DIR, "clip_vitb32.onnx")
PROVIDERS  = (
    ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers()
    else ["CPUExecutionProvider"]
)

sess_options                           = ort.SessionOptions()
sess_options.execution_mode           = ort.ExecutionMode.ORT_PARALLEL
sess_options.inter_op_num_threads     = 4
sess_options.intra_op_num_threads     = 4
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

ORT_SESSION = ort.InferenceSession(MODEL_PATH, sess_options=sess_options, providers=PROVIDERS)
ORT_LOCK    = threading.Lock()

# Confirmed from model inspection:
# Input:  'pixel_values'  shape: [batch, 3, 224, 224]
# Output: 'embeddings'    shape: [1, 512]  (we override batch dynamically)
ORT_INPUT  = "pixel_values"
ORT_OUTPUT = "embeddings"

# CLIP normalization constants
CLIP_MEAN = np.array([0.48145466, 0.4578275,  0.40821073], dtype=np.float32)
CLIP_STD  = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

# -------------------- Utilities --------------------

def fast_hash(path):
    """Hash file size + first 64KB — fast dedup without reading huge PSB files."""
    h = hashlib.sha256()
    h.update(str(os.path.getsize(path)).encode())
    with open(path, "rb") as f:
        h.update(f.read(HASH_BYTES))
    return h.hexdigest()

def load_meta():
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    if os.path.exists(META_PATH):
        try:
            with open(META_PATH, "r") as f:
                meta = json.load(f)
        except Exception:
            # Corrupted meta — start fresh
            meta = {"next_id": 0, "files": {}}
    else:
        meta = {"next_id": 0, "files": {}}

    for path in list(meta["files"].keys()):
        if not os.path.exists(path):
            meta["files"].pop(path)

    return meta

def save_meta(meta):
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

def load_index(dim):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    if os.path.exists(INDEX_PATH):
        try:
            return faiss.read_index(INDEX_PATH)
        except Exception:
            # Corrupted index — start fresh
            pass
    return faiss.IndexIDMap(faiss.IndexFlatIP(dim))

# -------------------- Image Handling --------------------

def load_image_fast(path):
    """
    Fast image loading.
    PSD/PSB: use embedded thumbnail (topil) instead of full composite.
    """
    if path.lower().endswith((".psd", ".psb")):
        psd = PSDImage.open(path)
        img = psd.topil()
        if img is None:
            img = psd.composite()
        if img is None:
            raise RuntimeError("PSD/PSB load failed")
        return img.convert("RGB")
    else:
        return Image.open(path).convert("RGB")

def preprocess_single(path):
    """Load and preprocess one image → (3, 224, 224) float32."""
    img = load_image_fast(path)
    img = img.resize((224, 224), Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = (arr - CLIP_MEAN) / CLIP_STD
    arr = np.transpose(arr, (2, 0, 1))
    return arr  # (3, 224, 224)

def preprocess_batch_parallel(paths):
    """
    Preprocess images in parallel threads (I/O bound).
    Returns: (batch_array, valid_paths, failed_list)
    """
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

    return np.stack(batch).astype(np.float32), valid_paths, failed  # (N, 3, 224, 224)

def get_embeddings_batch(paths):
    """
    Run batched ONNX inference.
    Handles the static output shape [1, 512] by running each batch correctly.
    Returns: (embeddings_array, valid_paths, failed_list)
    """
    batch, valid_paths, failed = preprocess_batch_parallel(paths)
    if batch is None:
        return np.array([]), [], failed

    with ORT_LOCK:
        # Run inference — batch input is (N, 3, 224, 224)
        # Model was exported with dynamic batch axis on input
        raw = ORT_SESSION.run([ORT_OUTPUT], {ORT_INPUT: batch})[0]  # may be (1,512) or (N,512)

    # If output is hardcoded to [1, 512], run images one by one as fallback
    if raw.shape[0] == 1 and len(valid_paths) > 1:
        embs = []
        with ORT_LOCK:
            for i in range(len(valid_paths)):
                single = batch[i:i+1]  # (1, 3, 224, 224)
                out = ORT_SESSION.run([ORT_OUTPUT], {ORT_INPUT: single})[0]
                embs.append(out[0])
        raw = np.stack(embs)  # (N, 512)

    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    embs  = (raw / norms).astype(np.float32)
    return embs, valid_paths, failed

def get_embedding(path):
    """Single image embedding for query."""
    embs, valid, failed = get_embeddings_batch([path])
    if not valid:
        raise RuntimeError(failed[0]["reason"])
    return embs[0]

# -------------------- Folder Sync --------------------

def scan_images(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(IMAGE_EXTENSIONS):
                yield os.path.normpath(os.path.join(root, f))

def find_by_hash(meta, file_hash_value):
    for p, info in meta["files"].items():
        if info["hash"] == file_hash_value:
            return p, info
    return None, None

def sync_folder(index, meta, folder_path, response):
    folder_path     = os.path.normpath(folder_path)
    current_files   = list(scan_images(folder_path))
    seen_hashes     = set()
    needs_embedding = []

    # ── Step 1: Hash all files in parallel ──────────────────────────────
    def hash_one(path):
        try:
            return path, fast_hash(path), None
        except Exception as e:
            return path, None, str(e)

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        for path, h, err in ex.map(hash_one, current_files):
            if err:
                response.status = False
                response.data["errors"].append({"file": path, "reason": err})
                continue

            seen_hashes.add(h)
            existing_path, existing_info = find_by_hash(meta, h)

            if existing_info:
                if existing_path != path:
                    meta["files"][path] = meta["files"].pop(existing_path)
                response.data["success"].append(path)
            else:
                needs_embedding.append((path, h))

    # ── Step 2: Embed new files in batches ──────────────────────────────
    total = len(needs_embedding)
    done  = 0

    for i in range(0, total, BATCH_SIZE):
        chunk       = needs_embedding[i:i + BATCH_SIZE]
        batch_paths = [p for p, _ in chunk]
        hash_lookup = {p: h for p, h in chunk}

        embs, valid_paths, failed = get_embeddings_batch(batch_paths)

        for f in failed:
            response.status = False
            response.data["errors"].append(f)

        for path, emb in zip(valid_paths, embs):
            idx = meta["next_id"]
            index.add_with_ids(emb.reshape(1, -1), np.array([idx]))
            meta["files"][path] = {"id": idx, "hash": hash_lookup[path]}
            meta["next_id"] += 1
            response.data["success"].append(path)

        done += len(chunk)
        print(f"[sync] {done}/{total} embedded", flush=True)

    # ── Step 3: Remove deleted files ────────────────────────────────────
    for path, info in list(meta["files"].items()):
        if path.startswith(folder_path) and info["hash"] not in seen_hashes:
            index.remove_ids(np.array([info["id"]]))
            del meta["files"][path]

# -------------------- Search --------------------

def search_img(query, index, meta, folder_path, top_k, response):
    q           = get_embedding(query)
    D, I        = index.search(q.reshape(1, -1), top_k)
    folder_path = os.path.normpath(folder_path)

    id_map = {
        v["id"]: k
        for k, v in meta["files"].items()
        if k.startswith(folder_path)
    }

    for i, idx in enumerate(I[0]):
        if idx in id_map:
            response.data["results"].append({
                "rank":       i + 1,
                "path":       id_map[idx],
                "similarity": float(D[0][i])
            })

def search(query_image, folder_path, top_k):
    response = BaseResponse()
    meta     = load_meta()
    index    = load_index(EMB_DIM)

    sync_folder(index, meta, folder_path, response)

    faiss.write_index(index, INDEX_PATH)
    save_meta(meta)

    search_img(query_image, index, meta, folder_path, int(top_k), response)

    response.message = (
        "Search completed with file errors"
        if response.data["errors"]
        else "Search completed successfully"
    )
    response.code = 207 if response.data["errors"] else 200
    return json.dumps(response.__dict__, indent=2)

# -------------------- License (UNCHANGED) --------------------

LICENSE_FILE_NAME = "license.json"

def _run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""

def get_device_id():
    return hashlib.sha256(platform.node().encode()).hexdigest()

class VerifyLicenseRespone:
    def __init__(self):
        self.status  = False
        self.message = ""
        self.code    = 400

def get_license_path():
    return os.path.join(get_exe_dir(), LICENSE_FILE_NAME)

def validate_license():
    resp         = VerifyLicenseRespone()
    license_path = get_license_path()

    if not os.path.exists(license_path):
        resp.message = "License file not found"
        resp.code    = 404
        return resp

    try:
        with open(license_path, "r", encoding="utf-8") as f:
            license_data = json.load(f)

        resp.status  = True
        resp.message = "License is valid"
        resp.code    = 200
        return resp

    except Exception:
        resp.message = "License validation failed"
        return resp

# -------------------- Web API --------------------

class Api:
    def selectFile(self):
        return filedialog.askopenfilename(
            title="Select a file",
            filetypes=(("Image files", IMAGE_EXTENSIONS_FOR_FILE), ("All files", "*.*"))
        )

    def selectFolder(self):
        return filedialog.askdirectory(title="Select a folder")

    def validateLicense(self):
        return json.dumps(validate_license().__dict__)

    def start_search(self, query_image, folder_path, top_k):
        return search(query_image, folder_path, top_k)

# -------------------- App --------------------

api = Api()
webview.create_window(
    "My App",
    "http://localhost:4200/",
    js_api=api
)

webview.start(
    gui="edgechromium",
    debug=True,
    http_server=True,
    private_mode=False,
    args=["--allow-file-access-from-files", "--disable-web-security"]
)