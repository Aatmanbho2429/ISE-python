import os
import json
import hashlib
import platform
from app.config import LICENSE_PATH


class LicenseResponse:
    def __init__(self):
        self.status  = False
        self.message = ""
        self.code    = 400


def get_device_id() -> str:
    return hashlib.sha256(platform.node().encode()).hexdigest()


def validate() -> LicenseResponse:
    resp = LicenseResponse()
    print(f"[license] Looking for license at: {LICENSE_PATH}")

    if not os.path.exists(LICENSE_PATH):
        resp.message = "License file not found"
        resp.code    = 404
        return resp

    try:
        with open(LICENSE_PATH, "r", encoding="utf-8") as f:
            json.load(f)
        resp.status  = True
        resp.message = "License is valid"
        resp.code    = 200
    except Exception:
        resp.message = "License validation failed"

    return resp