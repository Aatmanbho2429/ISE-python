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
 
#common function start
def get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_exe_dir()

FAISS_DIR = os.path.join(BASE_DIR, "faiss")
INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH = os.path.join(FAISS_DIR, "meta.json")
LICENSE_FILE_NAME = "license.json"
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

def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, "r") as f:
            return json.load(f)
    return {"next_id": 0, "files": {}}

def load_index(dim):
    if os.path.exists(INDEX_PATH):
        return faiss.read_index(INDEX_PATH)
    return faiss.IndexIDMap(faiss.IndexFlatIP(dim))

meta = load_meta()
index = load_index(384)

def _run_command(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL
        ).decode(errors="ignore").strip()
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
    hw_uuid = _run_command(
        "ioreg -rd1 -c IOPlatformExpertDevice | "
        "awk '/IOPlatformUUID/ { print $3 }'"
    ).replace('"', "")

    serial = _run_command(
        "system_profiler SPHardwareDataType | "
        "awk '/Serial Number/ { print $4 }'"
    )

    return [
        hw_uuid or "UNKNOWN_HW_UUID",
        serial or "UNKNOWN_SERIAL",
    ]

def get_device_id():
    os_name = platform.system()
    if os_name == "Windows":
        parts = _get_windows_ids()
    elif os_name == "Darwin":
        parts = _get_macos_ids()
    else:
        parts = ["UNSUPPORTED_OS"]

    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

#validate license start
class VerifyLicenseRespone:
    status: bool
    message: str
    code: int

def get_license_path():
    return os.path.join(get_exe_dir(), LICENSE_FILE_NAME)

def validate_license():
    verifyLicenseResponse = VerifyLicenseRespone()
    license_path = get_license_path()

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

        if not payload or not signature_b64:
            verifyLicenseResponse.status = False
            verifyLicenseResponse.message = "Invalid license format"
            verifyLicenseResponse.code = 400
            return verifyLicenseResponse

        if payload.get("device_id") != get_device_id():
            verifyLicenseResponse.status = False
            verifyLicenseResponse.message = "Your license is not valid for this device. Please contact support."
            verifyLicenseResponse.code = 403
            return verifyLicenseResponse

        message = json.dumps(
            payload, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")

        signature = base64.b64decode(signature_b64)
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)

        public_key.verify(
            signature,
            message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        verifyLicenseResponse.status = True
        verifyLicenseResponse.message = "License is valid"
        verifyLicenseResponse.code = 200
        return verifyLicenseResponse

    except InvalidSignature:
        verifyLicenseResponse.status = False
        verifyLicenseResponse.message = "Invalid license signature"
        verifyLicenseResponse.code = 400
        return verifyLicenseResponse
    except Exception as e:
        verifyLicenseResponse.status = False
        verifyLicenseResponse.message = "Technical error occuured while validating license" 
        verifyLicenseResponse.code = 500
        return verifyLicenseResponse
#validate license end

#common function end

class Api:
    def selectFile(self):
        ("Select file called")
        file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.webp *.psd *.psb"), ("All files", "*.*")) 
        )
        return file_path
    
    def selectFolder(self):
        folder_path = filedialog.askdirectory(
            title="Select a folder"
        )
        
        return folder_path
        

    def get_system_info(self):
        import platform
        return {
            "os": platform.system(),
            "version": platform.version()
        }
        
    def validateLicense(self):
        print("Validate license called")
        verify_license_response = validate_license()
        print("License validation result: ", json.dumps(verify_license_response.__dict__))
        return json.dumps(verify_license_response.__dict__)

def resource_path(path):
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, path)

api = Api()

webview.create_window(
    "My App",'http://localhost:4200/',js_api=api
)

# def resource_path(path):
#     try:
#         base_path = sys._MEIPASS
#     except Exception:
#         base_path = os.path.abspath(".")

#     return os.path.join(base_path, path)


# html_path = resource_path(
#     "dist/vynce-standalone/browser/index.html"
# )

# webview.create_window(
#     "My App",
#     html_path,
#     js_api=api
# )

webview.start(gui="edgechromium",
    debug=True,
    http_server=True,
    private_mode=False,
    args=[
        "--allow-file-access-from-files",
        "--disable-web-security"
    ])
