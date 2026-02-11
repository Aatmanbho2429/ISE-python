import base64
import os
import sys
import webview
import tkinter as tk
from tkinter import filedialog
import json
import hashlib
import traceback
import logging
import numpy as np
from PIL import Image
import onnxruntime as ort
import faiss
import platform
import subprocess

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
# from wand.image import Image as WandImage
import io

class BaseResponse:
    def __init__(self):
        self.status = True
        self.message = ""
        self.code = 200
        self.data = {
            "success": [],
            "errors": [],
            "results": []
        }

baseResponse = BaseResponse()

def get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def setup_imagemagick():
    base = get_exe_dir()
    im = os.path.join(base, "imagemagick")

    if os.path.exists(im):
        os.environ["MAGICK_HOME"] = im
        os.environ["PATH"] = os.path.join(im, "bin") + os.pathsep + os.environ.get("PATH", "")
        os.environ["MAGICK_CODER_MODULE_PATH"] = os.path.join(im, "modules")
        os.environ["MAGICK_CONFIGURE_PATH"] = os.path.join(im, "config")
        os.environ["DYLD_LIBRARY_PATH"] = os.path.join(im, "lib")

setup_imagemagick()

BASE_DIR = get_exe_dir()
FAISS_DIR = os.path.join(BASE_DIR, "faiss")
os.makedirs(FAISS_DIR, exist_ok=True)

INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH = os.path.join(FAISS_DIR, "meta.json")

IMAGE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".bmp", ".gif",
    ".tif", ".tiff", ".webp",
    ".psd", ".psb",
    ".pdf", ".eps",
    ".raw", ".heic"
)

CONVERSION_EXTENSIONS = (".psd", ".psb", ".pdf", ".ai", ".eps", ".tif", ".tiff")

MODEL_PATH = os.path.join(BASE_DIR, "dinov2_vits14.onnx")
PROVIDERS = (
    ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers()
    else ["CPUExecutionProvider"]
)
ORT_SESSION = ort.InferenceSession(MODEL_PATH, providers=PROVIDERS)
ORT_INPUT = ORT_SESSION.get_inputs()[0].name
ORT_OUTPUT = ORT_SESSION.get_outputs()[0].name

def load_image_any_format(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in CONVERSION_EXTENSIONS:
            with WandImage(filename=f"{path}[0]", resolution=72) as img:
                blob = img.make_blob(format="png")
            return Image.open(io.BytesIO(blob)).convert("RGB")
        return Image.open(path).convert("RGB")
    except Exception:
        return None

def scan_images(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(IMAGE_EXTENSIONS):
                yield os.path.join(root, f)

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, "r") as f:
            return json.load(f)
    return {"next_id": 0, "files": {}}

def load_index(dim):
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    return faiss.IndexIDMap(faiss.IndexFlatIP(dim))

def preprocess(path):
    img = load_image_any_format(path)
    if img is None:
        return None
    img = img.resize((224, 224))
    img = np.array(img).astype(np.float32) / 255.0
    img = (img - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    img = np.transpose(img, (2, 0, 1))
    return np.expand_dims(img, axis=0)

def get_embedding(path):
    data = preprocess(path)
    if data is None:
        return None
    emb = ORT_SESSION.run([ORT_OUTPUT], {ORT_INPUT: data})[0].flatten().astype(np.float32)
    emb /= np.linalg.norm(emb)
    return emb

def sync_folder(index, meta, response):
    current = set(scan_images(IMAGE_FOLDER))

    for path in list(meta["files"].keys()):
        if path not in current:
            index.remove_ids(np.array([meta["files"][path]["id"]]))
            del meta["files"][path]

    for path in current:
        h = file_hash(path)
        if path in meta["files"] and meta["files"][path]["hash"] == h:
            continue

        emb = get_embedding(path)
        if emb is None:
            continue

        idx = meta["next_id"]
        index.add_with_ids(emb.reshape(1, -1), np.array([idx]))
        meta["files"][path] = {"id": idx, "hash": h}
        meta["next_id"] += 1

def save_meta(meta):
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

def search_img(query, index, meta, response):
    q = get_embedding(query)
    if q is None:
        return

    D, I = index.search(q.reshape(1, -1), TOP_K)
    id_map = {v["id"]: k for k, v in meta["files"].items()}

    for i, idx in enumerate(I[0]):
        if idx == -1:
            continue
        response.data["results"].append({
            "rank": i + 1,
            "path": id_map.get(idx),
            "similarity": float(D[0][i])
        })

def search(query_image, folder_path, top_k):
    response = BaseResponse()
    global IMAGE_FOLDER, TOP_K
    IMAGE_FOLDER = folder_path
    TOP_K = top_k

    meta = load_meta()
    index = load_index(384)

    sync_folder(index, meta, response)
    faiss.write_index(index, INDEX_PATH)
    save_meta(meta)
    search_img(query_image, index, meta, response)

    response.message = "Search completed"
    return json.dumps(response.__dict__)

LICENSE_FILE_NAME = "license.json"

def _run_command(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode(errors="ignore").strip()
    except Exception:
        return ""

def _get_windows_ids():
    uuid = _run_command("wmic csproduct get uuid").splitlines()
    cpu = _run_command("wmic cpu get processorid").splitlines()
    disk = _run_command("wmic diskdrive get serialnumber").splitlines()
    return [
        uuid[1].strip() if len(uuid) > 1 else "UNKNOWN_UUID",
        cpu[1].strip() if len(cpu) > 1 else "UNKNOWN_CPU",
        disk[1].strip() if len(disk) > 1 else "UNKNOWN_DISK",
    ]

def _get_macos_ids():
    hw_uuid = _run_command("ioreg -rd1 -c IOPlatformExpertDevice | awk '/IOPlatformUUID/ { print $3 }'").replace('"', "")
    serial = _run_command("system_profiler SPHardwareDataType | awk '/Serial Number/ { print $4 }'")
    return [hw_uuid or "UNKNOWN_HW_UUID", serial or "UNKNOWN_SERIAL"]

def get_device_id():
    os_name = platform.system()
    parts = _get_windows_ids() if os_name == "Windows" else _get_macos_ids() if os_name == "Darwin" else ["UNSUPPORTED_OS"]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

class VerifyLicenseRespone:
    status: bool
    message: str
    code: int

def get_license_path():
    return os.path.join(get_exe_dir(), LICENSE_FILE_NAME)

def validate_license():
    verifyLicenseResponse = VerifyLicenseRespone()
    license_path = get_license_path()
    PUBLIC_KEY_PEM = b"""
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn+L7AYEpYrDC8rfGN791
N66M4tlMgQ0+y7INQLAZMQ/yPpy5u3MQDbU2AF2lWLO+wQFjwxjUWbLTB5/fb511
3ToEF//0ovQYip29P1imK9+003nNuIuS2w0uefYFaAOK92nIRUt7LwGQZdSUkymn
kiEjLsu7JrYhcFuby5MnOXNsiS4wCTiMpbrKamYInDCxnpO3zQ78xZPI60iV3TLC
6pw58HibCsxKkB8WCngUoPbGOa8DFD3EjQ0WIU4YCoTVnOFTQJuP08n9zu7UbJT/
WvwVyCfnerFka+fPQszNX1MIGSOx9+SHfvB0MjD0wkZ+AvDSnc1FFZps03ec/ngf
ZQIDAQAB
-----END PUBLIC KEY-----
"""
    if not os.path.exists(license_path):
        verifyLicenseResponse.status = False
        verifyLicenseResponse.message = "License file not found"
        verifyLicenseResponse.code = 404
        return verifyLicenseResponse

    try:
        with open(license_path, "r", encoding="utf-8") as f:
            license_data = json.load(f)

        payload = license_data.get("payload")
        signature_b64 = license_data.get("signature")

        if payload.get("device_id") != get_device_id():
            verifyLicenseResponse.status = False
            verifyLicenseResponse.message = "Invalid device"
            verifyLicenseResponse.code = 403
            return verifyLicenseResponse

        message = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = base64.b64decode(signature_b64)
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())

        verifyLicenseResponse.status = True
        verifyLicenseResponse.message = "License is valid"
        verifyLicenseResponse.code = 200
        return verifyLicenseResponse

    except Exception:
        verifyLicenseResponse.status = False
        verifyLicenseResponse.message = "License validation failed"
        verifyLicenseResponse.code = 400
        return verifyLicenseResponse

class Api:
    def selectFile(self):
        file_path = filedialog.askopenfilename(
            title="Select a file",
            filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.webp *.psd *.psb"), ("All files", "*.*"))
        )
        return file_path

    def selectFolder(self):
        return filedialog.askdirectory(title="Select a folder")

    def validateLicense(self):
        return json.dumps(validate_license().__dict__)

    def start_search(self, query_image, folder_path, top_k):
        return search(query_image, folder_path, top_k)

api = Api()

webview.create_window("My App", "http://localhost:4200/", js_api=api)

webview.start(
    gui="edgechromium",
    debug=True,
    http_server=True,
    private_mode=False,
    args=["--allow-file-access-from-files", "--disable-web-security"]
)