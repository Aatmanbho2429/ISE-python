"""
Benchmark: decompress PSB → save temp JPEG → load temp JPEG → delete temp JPEG
Tests the full pipeline to see total time per file.

Run: python benchmark_temp.py
"""
import time
import os
import sys
import tempfile
import struct
import io
import shutil
from PIL import Image

TEST_FOLDER = r"D:\\ImageDb\\PSB FILE\\GLOSSY"
MAX_FILES   = 10
PREVIEW_SIZE = 512


def _extract_psb_thumbnail(path: str):
    """Raw byte extraction — fast path if thumbnail exists."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"8BPS":
                return None
            f.read(2); f.read(6); f.read(2); f.read(4); f.read(4); f.read(2); f.read(2)
            f.seek(struct.unpack(">I", f.read(4))[0], 1)
            end = f.tell() + struct.unpack(">I", f.read(4))[0]
            while f.tell() < end:
                if f.read(4) != b"8BIM": break
                rid      = struct.unpack(">H", f.read(2))[0]
                name_len = struct.unpack("B", f.read(1))[0]
                pad      = name_len if name_len > 0 else 1
                f.read(pad + (pad % 2))
                rlen   = struct.unpack(">I", f.read(4))[0]
                rstart = f.tell()
                if rid in (0x0409, 0x0408):
                    fmt = struct.unpack(">I", f.read(4))[0]
                    f.read(16)
                    jpeg_size = struct.unpack(">I", f.read(4))[0]
                    f.read(4)
                    if fmt == 1:
                        data = f.read(jpeg_size)
                        return Image.open(io.BytesIO(data)).convert("RGB")
                f.seek(rstart + rlen + (rlen % 2))
    except Exception:
        pass
    return None


def process_one_psb(path: str) -> dict:
    """
    Full pipeline for one PSB:
    1. Try raw byte extract (fast)
    2. If not found — decompress with psd_tools (slow, but only once)
    3. Save to temp JPEG
    4. Load temp JPEG (this is what gets embedded)
    5. Delete temp JPEG
    Returns timing breakdown.
    """
    result = {
        "file":         os.path.basename(path),
        "size_mb":      os.path.getsize(path) / 1024 / 1024,
        "raw_ms":       0,
        "decompress_ms":0,
        "save_ms":      0,
        "load_ms":      0,
        "delete_ms":    0,
        "total_ms":     0,
        "method":       "",
        "error":        None,
        "img_size":     None,
    }

    temp_path = None
    t_total   = time.perf_counter()

    try:
        # ── Step 1: Try raw byte extraction ─────────────────────────────
        t = time.perf_counter()
        img = _extract_psb_thumbnail(path)
        result["raw_ms"] = (time.perf_counter() - t) * 1000

        if img is not None:
            result["method"] = "raw_bytes"
        else:
            # ── Step 2: Full decompress ──────────────────────────────────
            result["method"] = "psd_tools"
            t = time.perf_counter()
            from psd_tools import PSDImage
            psd = PSDImage.open(path)
            img = psd.topil()
            if img is None:
                img = psd.composite()
            if img is None:
                raise RuntimeError("No image data found")
            img = img.convert("RGB")
            result["decompress_ms"] = (time.perf_counter() - t) * 1000

        # ── Step 3: Save to temp JPEG ────────────────────────────────────
        t = time.perf_counter()
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        temp_path = tmp.name
        tmp.close()

        thumb = img.copy()
        thumb.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
        thumb.save(temp_path, "JPEG", quality=85, optimize=True)
        result["save_ms"] = (time.perf_counter() - t) * 1000

        temp_size_kb = os.path.getsize(temp_path) / 1024

        # ── Step 4: Load temp JPEG (simulates what embedder will read) ───
        t = time.perf_counter()
        loaded = Image.open(temp_path).convert("RGB")
        result["img_size"] = loaded.size
        result["load_ms"]  = (time.perf_counter() - t) * 1000

        # ── Step 5: Delete temp JPEG ─────────────────────────────────────
        t = time.perf_counter()
        os.remove(temp_path)
        temp_path = None
        result["delete_ms"] = (time.perf_counter() - t) * 1000

    except Exception as e:
        result["error"] = str(e)
    finally:
        # Safety cleanup
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    result["total_ms"] = (time.perf_counter() - t_total) * 1000
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

files = []
for root, _, fs in os.walk(TEST_FOLDER):
    for f in fs:
        if f.lower().endswith((".psb", ".psd")):
            files.append(os.path.join(root, f))
        if len(files) >= MAX_FILES:
            break
    if len(files) >= MAX_FILES:
        break

if not files:
    print(f"No PSB files found in {TEST_FOLDER}")
    sys.exit(1)

print(f"Testing {len(files)} files from {TEST_FOLDER}")
print(f"Pipeline: decompress → temp JPEG → load → delete\n")
print(f"{'File':<45} {'MB':>6}  {'method':<10} {'decomp':>8} {'save':>6} {'load':>6} {'del':>5} {'TOTAL':>8}")
print("=" * 105)

total_time = 0
success    = 0

for path in files:
    r = process_one_psb(path)

    if r["error"]:
        print(f"❌ {r['file']:<43} {r['size_mb']:>6.1f}  ERROR: {r['error']}")
        continue

    decomp = f"{r['decompress_ms']:.0f}ms" if r["method"] == "psd_tools" else f"{r['raw_ms']:.0f}ms"
    print(
        f"✅ {r['file']:<43} {r['size_mb']:>6.1f}"
        f"  {r['method']:<10}"
        f"  {decomp:>8}"
        f"  {r['save_ms']:>4.0f}ms"
        f"  {r['load_ms']:>4.0f}ms"
        f"  {r['delete_ms']:>3.0f}ms"
        f"  {r['total_ms']:>6.0f}ms"
    )
    total_time += r["total_ms"]
    success    += 1

print("=" * 105)

if success > 0:
    avg = total_time / success
    print(f"\nAverage per file:      {avg:.0f}ms  ({avg/1000:.1f}s)")
    print(f"\n10k files estimates:")
    for workers in [2, 4, 6, 8]:
        mins = 10000 * avg / workers / 1000 / 60
        print(f"  {workers} workers → {mins:.0f} min")

print(f"\nNOTE: 'decomp' is the slow step — happens once per file only.")
print(f"      After embedding, the temp file is deleted immediately.")
print(f"      No permanent files are created on disk.")