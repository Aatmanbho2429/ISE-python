import os
import json
import base64
import subprocess
import hashlib
import platform
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from app.config import LICENSE_PATH


PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArN2G443C1rfFI6O7+oc1
9MAb2ugUTU3dpztq49Nc6Mv3CWLF+Bkn+qBBAoLHPzgdYnga817guPHZ/tt/s3ea
N07gPtoUczBevQrdQXY963k7TnfyWHFmop8FTZTbsypQGnOjWSA2xyNp5GKefyWs
8Wfc/k3SRUefNYjFSZaRmGyxXu3P1Tu59xC2qHrnmieLXYuXrPXILjUH+/00KtxS
hBcOTKyRLQn59Fw6paqz0QBMHgviBbBU/AYS1Fe/WCm1UBUvl48kMyAltZufx5UN
jpRZL2VJ3lQtAg4ZTNU3ZwwHx38GEynFAcKkytkCYmoxqM7ghkLsp4A4xkDc/74r
EwIDAQAB
-----END PUBLIC KEY-----"""


class LicenseResponse:
    def __init__(self):
        self.status  = False
        self.message = ""
        self.code    = 400


def _run_command(cmd: str) -> str:
    try:
        result = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.DEVNULL
        ).decode(errors="ignore").strip()
        # print(f"[license][cmd] {cmd!r} → {result!r}", flush=True)
        return result
    except Exception as e:
        # print(f"[license][cmd] {cmd!r} → FAILED: {e}", flush=True)
        return ""


def _get_windows_ids():
    # print("[license] Collecting Windows hardware IDs...", flush=True)
    uuid  = _run_command("wmic csproduct get uuid").splitlines()
    cpu   = _run_command("wmic cpu get processorid").splitlines()
    disk  = _run_command("wmic diskdrive get serialnumber").splitlines()

    uuid_val  = uuid[1].strip()  if len(uuid)  > 1 else "UNKNOWN_UUID"
    cpu_val   = cpu[1].strip()   if len(cpu)   > 1 else "UNKNOWN_CPU"
    disk_val  = disk[1].strip()  if len(disk)  > 1 else "UNKNOWN_DISK"

    # print(f"[license]   UUID : {uuid_val!r}", flush=True)
    # print(f"[license]   CPU  : {cpu_val!r}",  flush=True)
    # print(f"[license]   DISK : {disk_val!r}", flush=True)

    return [uuid_val, cpu_val, disk_val]


def _get_macos_ids():
    # print("[license] Collecting macOS hardware IDs...", flush=True)
    hw_uuid = _run_command(
        "ioreg -rd1 -c IOPlatformExpertDevice | awk '/IOPlatformUUID/ { print $3 }'"
    ).replace('"', "")
    serial = _run_command(
        "system_profiler SPHardwareDataType | awk '/Serial Number/ { print $4 }'"
    )
    # print(f"[license]   HW UUID : {hw_uuid!r}", flush=True)
    # print(f"[license]   Serial  : {serial!r}",  flush=True)
    return [
        hw_uuid or "UNKNOWN_HW_UUID",
        serial  or "UNKNOWN_SERIAL",
    ]


def get_device_id() -> str:
    os_name = platform.system()
    # print(f"[license] OS: {os_name}", flush=True)

    if os_name == "Windows":
        parts = _get_windows_ids()
    elif os_name == "Darwin":
        parts = _get_macos_ids()
    else:
        parts = ["UNSUPPORTED_OS"]
        # print(f"[license] Unsupported OS: {os_name}", flush=True)

    raw      = "|".join(parts).encode("utf-8")
    combined = "|".join(parts)
    device_id = hashlib.sha256(raw).hexdigest()

    # print(f"[license] Raw combined string : {combined!r}", flush=True)
    # print(f"[license] Final device_id     : {device_id}", flush=True)
    return device_id


def validate() -> LicenseResponse:
    resp = LicenseResponse()
    # print(f"[license] ── Validation start ──────────────────────", flush=True)
    # print(f"[license] LICENSE_PATH : {LICENSE_PATH}", flush=True)
    # print(f"[license] File exists  : {os.path.exists(LICENSE_PATH)}", flush=True)

    device_id = get_device_id()
    # print(f"[license] Device ID    : {device_id}", flush=True)

    # ── 1. License file exists ────────────────────────────────────────────
    if not os.path.exists(LICENSE_PATH):
        # print("[license] ❌ FAIL: License file not found", flush=True)
        resp.message = "License file not found. Please contact support."
        resp.code    = 404
        return resp
    # print("[license] ✅ PASS: File exists", flush=True)

    # ── 2. Parse license file ─────────────────────────────────────────────
    try:
        with open(LICENSE_PATH, "r", encoding="utf-8") as f:
            license_data = json.load(f)
        # print(f"[license] ✅ PASS: JSON parsed — keys: {list(license_data.keys())}", flush=True)
    except json.JSONDecodeError as e:
        # print(f"[license] ❌ FAIL: JSON decode error — {e}", flush=True)
        resp.message = "License file is corrupted or not valid JSON."
        resp.code    = 400
        return resp
    except Exception as e:
        # print(f"[license] ❌ FAIL: Could not read file — {e}", flush=True)
        resp.message = "License file could not be read."
        resp.code    = 400
        return resp

    # ── 3. Required fields present ────────────────────────────────────────
    if "payload" not in license_data or "signature" not in license_data:
        # print(f"[license] ❌ FAIL: Missing fields — found: {list(license_data.keys())}", flush=True)
        resp.message = "License file is missing required fields."
        resp.code    = 400
        return resp
    # print("[license] ✅ PASS: Required fields present", flush=True)

    payload = license_data["payload"]
    # print(f"[license] Payload keys : {list(payload.keys())}", flush=True)
    # print(f"[license] Payload      : {payload}", flush=True)

    if "device_id" not in payload or "customer" not in payload:
        # print(f"[license] ❌ FAIL: Payload missing device_id or customer", flush=True)
        resp.message = "License payload is incomplete."
        resp.code    = 400
        return resp
    # print("[license] ✅ PASS: Payload fields present", flush=True)

    # ── 4. Verify RSA signature ───────────────────────────────────────────
    try:
        signature     = base64.b64decode(license_data["signature"])
        public_key    = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        payload_bytes = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True
        ).encode("utf-8")

        # print(f"[license] Payload bytes for verification : {payload_bytes}", flush=True)
        # print(f"[license] Signature length               : {len(signature)} bytes", flush=True)

        public_key.verify(
            signature,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        # print("[license] ✅ PASS: Signature valid", flush=True)

    except InvalidSignature:
        # print("[license] ❌ FAIL: Signature invalid — payload may have been tampered with", flush=True)
        resp.message = "License signature is invalid. This license may have been tampered with."
        resp.code    = 403
        return resp
    except Exception as e:
        # print(f"[license] ❌ FAIL: Signature verification error — {e}", flush=True)
        resp.message = "License signature could not be verified."
        resp.code    = 400
        return resp

    # ── 5. Device ID matches ──────────────────────────────────────────────
    license_device_id = payload["device_id"]
    # print(f"[license] License device_id : {license_device_id}", flush=True)
    # print(f"[license] Current device_id : {device_id}", flush=True)
    # print(f"[license] Device ID match   : {license_device_id == device_id}", flush=True)

    if license_device_id != device_id:
        # print("[license] ❌ FAIL: Device ID mismatch", flush=True)
        resp.message = "This license is not valid for this device. Please contact support."
        resp.code    = 403
        return resp
    # print("[license] ✅ PASS: Device ID matches", flush=True)

    # ── All checks passed ─────────────────────────────────────────────────
    # print("[license] ✅ ALL CHECKS PASSED — License valid", flush=True)
    resp.status  = True
    resp.message = f"License valid — {payload['customer']}"
    resp.code    = 200
    return resp