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
import tifffile as tiff

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from psd_tools import PSDImage
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

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = get_exe_dir()
FAISS_DIR = os.path.join(BASE_DIR, "faiss")
os.makedirs(FAISS_DIR, exist_ok=True)

INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH = os.path.join(FAISS_DIR, "meta.json")

IMAGE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png",
    ".tif", ".tiff",
    ".psd", ".psb"
)

IMAGE_EXTENSIONS_FOR_FILE = "*.jpg;*.jpeg;*.png;*.tiff;*.tif;*.psd;*.psb"

PSD_EXTENSIONS = (".psd", ".psb")
TIFF_EXTENSIONS = (".tif", ".tiff")

MODEL_PATH = resource_path("dinov2_vits14.onnx")
PROVIDERS = (
    ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers()
    else ["CPUExecutionProvider"]
)
ORT_SESSION = ort.InferenceSession(MODEL_PATH, providers=PROVIDERS)
ORT_INPUT = ORT_SESSION.get_inputs()[0].name
ORT_OUTPUT = ORT_SESSION.get_outputs()[0].name

def convert_tiff_to_png(file_name):
    tiff_image = Image.open(file_name)
    jpeg_image = tiff_image.convert("RGB")
    output_path = jpeg_image.save(file_name + ".png")
    print(f"Converted TIFF to PNG: {output_path}")

def convert_psd_to_png(file_name):
    try:
        psd = PSDImage.open(file_name)
        final_image = psd.composite()
        if final_image is None:
            raise RuntimeError("Failed to composite PSD")
        output_path = os.path.splitext(file_name)[0] + ".png"
        final_image.save(output_path)
    except Exception as e:
        print(f"Error converting PSD to PNG: {e}")
        traceback.print_exc()
        return None
    return output_path

def scan_images(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            if f.startswith("._"):
                continue
            if "__MACOSX" in root:
                continue
            if f.lower().endswith(IMAGE_EXTENSIONS):
                yield os.path.join(root, f)

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
    try:
        with Image.open(path) as img:
            img = img.convert("RGB").resize((224, 224), Image.BILINEAR)
            img = np.asarray(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std
        img = img.transpose(2, 0, 1)
    except Exception:
        return None
    return img[np.newaxis, :].astype(np.float32)

def get_embedding(path):
    temp_file = None
    try:
        if path.lower().endswith(PSD_EXTENSIONS):
            temp_file = convert_psd_to_png(path)
            if temp_file is not None:
                path = temp_file
            else:
                return None
        data = preprocess(path)
        if data is None:
            return None
        emb = ORT_SESSION.run(
            [ORT_OUTPUT],
            {ORT_INPUT: data}
        )[0].flatten().astype(np.float32)
        emb /= np.linalg.norm(emb)
        return emb
    except Exception:
        return None
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

def search_img(query, index, meta, response, top_k, folder_scope):
    q = get_embedding(query)
    if q is None:
        response.data["errors"].append(f"Failed to process query image: {query}")
        return
    search_k = min(top_k * 5, len(meta["files"]))
    D, I = index.search(q.reshape(1, -1), search_k)
    id_map = {v["id"]: k for k, v in meta["files"].items()}
    folder_scope = os.path.abspath(folder_scope)
    rank = 1
    for i, idx in enumerate(I[0]):
        if idx == -1:
            continue
        path = id_map.get(idx)
        if not path:
            continue
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(folder_scope):
            continue
        response.data["results"].append({
            "rank": rank,
            "path": path,
            "similarity": float(D[0][i])
        })
        rank += 1
        if rank > top_k:
            break

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def sync_folder(index, meta, response, image_folder):
    image_folder = os.path.abspath(image_folder)
    current_files = set(os.path.abspath(p) for p in scan_images(image_folder))
    scoped_meta_paths = {
        path for path in meta["files"]
        if os.path.abspath(path).startswith(image_folder)
    }
    deleted_files = scoped_meta_paths - current_files
    for path in deleted_files:
        file_id = meta["files"][path]["id"]
        index.remove_ids(np.array([file_id]))
        del meta["files"][path]
        response.data["success"].append(f"Removed: {path}")
    for path in current_files:
        h = file_hash(path)
        if path in meta["files"] and meta["files"][path]["hash"] == h:
            continue
        emb = get_embedding(path)
        if emb is None:
            response.data["errors"].append(f"Failed to process: {path}")
            continue
        if path in meta["files"]:
            file_id = meta["files"][path]["id"]
            index.remove_ids(np.array([file_id]))
        else:
            file_id = meta["next_id"]
            meta["next_id"] += 1
        index.add_with_ids(emb.reshape(1, -1), np.array([file_id]))
        meta["files"][path] = {"id": file_id, "hash": h}
        response.data["success"].append(f"Indexed: {path}")

def save_meta(meta):
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

def search(query_image, folder_path, top_k):
    response = BaseResponse()
    meta = load_meta()
    index = load_index(384)
    sync_folder(index, meta, response, folder_path)
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    faiss.write_index(index, INDEX_PATH)
    save_meta(meta)
    search_img(query_image, index, meta, response, top_k, folder_path)
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
    PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn+L7AYEpYrDC8rfGN791
N66M4tlMgQ0+y7INQLAZMQ/yPpy5u3MQDbU2AF2lWLO+wQFjwxjUWbLTB5/fb511
3ToEF//0ovQYip29P1imK9+003nNuIuS2w0uefYFaAOK92nIRUt7LwGQZdSUkymn
kiEjLsu7JrYhcFuby5MnOXNsiS4wCTiMpbrKamYInDCxnpO3zQ78xZPI60iV3TLC
6pw58HibCsxKkB8WCngUoPbGOa8DFD3EjQ0WIU4YCoTVnOFTQJuP08n9zu7UbJT/
WvwVyCfnerFka+fPQszNX1MIGSOx9+SHfvB0MjD0wkZ+AvDSnc1FFZps03ec/ngf
ZQIDAQAB
-----END PUBLIC KEY-----"""
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
    
def get_folder_tree():
    meta = load_meta()
    files = meta.get("files", {})

    folder_map = {}

    for path, info in files.items():
        folder = os.path.dirname(path)
        if folder not in folder_map:
            folder_map[folder] = {
                "files": [],
                "exists": os.path.isdir(folder)
            }
        folder_map[folder]["files"].append({
            "name": os.path.basename(path),
            "fullPath": path,
            "id": info["id"],
            "hash": info["hash"],
            "exists": os.path.isfile(path)
        })

    def insert_into_tree(tree, parts, folder_path, folder_data):
        if not parts:
            return

        key = parts[0]
        if key not in tree:
            tree[key] = {
                "name": key,
                "fullPath": folder_path if len(parts) == 1 else "",
                "exists": True,
                "files": [],
                "subDirectories": {}
            }

        if len(parts) == 1:
            tree[key]["fullPath"] = folder_path
            tree[key]["exists"] = folder_data["exists"]
            tree[key]["files"] = folder_data["files"]
        else:
            insert_into_tree(tree[key]["subDirectories"], parts[1:], folder_path, folder_data)

    def compute_totals(node):
        total = len(node["files"])
        for sub in node["subDirectories"].values():
            total += compute_totals(sub)
        node["totalFiles"] = total
        node["totalFolders"] = len(node["subDirectories"])
        return total

    tree = {}

    for folder_path, folder_data in folder_map.items():
        normalized = folder_path.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p]
        insert_into_tree(tree, parts, folder_path, folder_data)

    root_node = {
        "name": "root",
        "fullPath": "",
        "exists": True,
        "files": [],
        "subDirectories": tree
    }

    compute_totals(root_node)

    missing_files = sum(
        1 for folder in folder_map.values()
        for f in folder["files"] if not f["exists"]
    )
    missing_folders = sum(
        1 for folder in folder_map.values() if not folder["exists"]
    )

    result = {
        "tree": root_node,
        "summary": {
            "totalIndexedFiles": len(files),
            "totalFolders": len(folder_map),
            "missingFiles": missing_files,
            "missingFolders": missing_folders
        }
    }

    return json.dumps(result)

class Api:
    def selectFile(self):
        window = webview.windows[0]
        file_types = ["Image files (*.jpg;*.jpeg;*.png;*.tiff;*.tif;*.psd;*.psb)"]
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=file_types
        )
        if result:
            return result[0]
        return ""

    def selectFolder(self):
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FOLDER_DIALOG,
            allow_multiple=False
        )
        if result:
            return result[0]
        return ""

    def validateLicense(self):
        return json.dumps(validate_license().__dict__)

    def openFilePath(self, path):
        path = os.path.abspath(path)
        folder = os.path.dirname(path)
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.run(["open", "-R", path])
            elif system == "Windows":
                subprocess.run(["explorer", "/select,", path])
            elif system == "Linux":
                subprocess.run(["xdg-open", folder])
        except Exception:
            pass
        return True

    def start_search(self, query_image, folder_path, top_k):
        return search(query_image, folder_path, top_k)
    
    def getFolderTree(self):
        return get_folder_tree()

api = Api()

base_dir = os.path.dirname(os.path.abspath(__file__))

webview.create_window("My App", "http://localhost:4200/", js_api=api)


webview.start(
    gui="edgechromium",
    debug=True,
    http_server=True,
    private_mode=False
)
