import os
import hashlib
from app.config import IMAGE_EXTENSIONS, HASH_BYTES


def fast_hash(path: str) -> str:
    h = hashlib.sha256()
    h.update(str(os.path.getsize(path)).encode())
    with open(path, "rb") as f:
        h.update(f.read(HASH_BYTES))
    return h.hexdigest()


def scan_images(folder: str):
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(IMAGE_EXTENSIONS):
                yield os.path.normpath(os.path.join(root, f))