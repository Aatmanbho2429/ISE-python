import base64
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
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from psd_tools import PSDImage

# -------------------- Core Models --------------------

class BaseResponse:
    def __init__(self):
        self.status = True
        self.message = ""
        self.code = 200
        self.data = {"success": [], "errors": [], "results": []}

# -------------------- Paths --------------------

def get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_exe_dir()
FAISS_DIR = os.path.join(BASE_DIR, "faiss")
os.makedirs(FAISS_DIR, exist_ok=True)

INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH = os.path.join(FAISS_DIR, "meta.json")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".psd", ".psb")
IMAGE_EXTENSIONS_FOR_FILE = "*.jpg *.jpeg *.png *.tiff *.tif *.psd *.psb"

# -------------------- Model --------------------

MODEL_PATH = os.path.join(BASE_DIR, "dinov2_vits14.onnx")
PROVIDERS = (
    ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers()
    else ["CPUExecutionProvider"]
)
ORT_SESSION = ort.InferenceSession(MODEL_PATH, providers=PROVIDERS)
ORT_INPUT = ORT_SESSION.get_inputs()[0].name
ORT_OUTPUT = ORT_SESSION.get_outputs()[0].name

# -------------------- Utilities --------------------

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, "r") as f:
            meta = json.load(f)
    else:
        meta = {"next_id": 0, "files": {}}

    # Cleanup missing files
    for path in list(meta["files"].keys()):
        if not os.path.exists(path):
            meta["files"].pop(path)

    return meta

def save_meta(meta):
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

def load_index(dim):
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    return faiss.IndexIDMap(faiss.IndexFlatIP(dim))

# -------------------- Image Handling --------------------

def load_image(path):
    if path.lower().endswith((".psd", ".psb")):
        img = PSDImage.open(path).composite()
        if img is None:
            raise RuntimeError("PSD composite failed")
    else:
        img = Image.open(path)
    return img.convert("RGB")

def preprocess(path):
    img = load_image(path)
    img = img.resize((224, 224))
    img = np.array(img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img = (img - mean) / std
    img = np.transpose(img, (2, 0, 1))
    return img[np.newaxis, ...].astype(np.float32)

def get_embedding(path):
    data = preprocess(path)
    emb = ORT_SESSION.run([ORT_OUTPUT], {ORT_INPUT: data})[0].flatten()
    emb = emb.astype(np.float32)
    emb /= np.linalg.norm(emb)
    return emb

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
    folder_path = os.path.normpath(folder_path)
    current_files = set(scan_images(folder_path))
    seen_hashes = set()

    for path in current_files:
        try:
            h = file_hash(path)
            seen_hashes.add(h)

            existing_path, existing_info = find_by_hash(meta, h)

            if existing_info:
                if existing_path != path:
                    meta["files"][path] = meta["files"].pop(existing_path)
                response.data["success"].append(path)
                continue

            emb = get_embedding(path)
            idx = meta["next_id"]
            index.add_with_ids(emb.reshape(1, -1), np.array([idx]))

            meta["files"][path] = {"id": idx, "hash": h}
            meta["next_id"] += 1
            response.data["success"].append(path)

        except Exception as e:
            response.status = False
            response.data["errors"].append({"file": path, "reason": str(e)})

    # Remove deleted files
    for path, info in list(meta["files"].items()):
        if path.startswith(folder_path) and info["hash"] not in seen_hashes:
            index.remove_ids(np.array([info["id"]]))
            del meta["files"][path]

# -------------------- Search --------------------

def search_img(query, index, meta, folder_path, top_k, response):
    q = get_embedding(query)
    D, I = index.search(q.reshape(1, -1), top_k)
    folder_path = os.path.normpath(folder_path)

    id_map = {
        v["id"]: k
        for k, v in meta["files"].items()
        if k.startswith(folder_path)
    }

    for i, idx in enumerate(I[0]):
        if idx in id_map:
            response.data["results"].append({
                "rank": i + 1,
                "path": id_map[idx],
                "similarity": float(D[0][i])
            })

def search(query_image, folder_path, top_k):
    response = BaseResponse()
    meta = load_meta()
    index = load_index(384)

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
        self.status = False
        self.message = ""
        self.code = 400

def get_license_path():
    return os.path.join(get_exe_dir(), LICENSE_FILE_NAME)

def validate_license():
    resp = VerifyLicenseRespone()
    license_path = get_license_path()

    if not os.path.exists(license_path):
        resp.message = "License file not found"
        resp.code = 404
        return resp

    try:
        with open(license_path, "r", encoding="utf-8") as f:
            license_data = json.load(f)

        resp.status = True
        resp.message = "License is valid"
        resp.code = 200
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
