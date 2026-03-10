"""
benchmark_loader.py
────────────────────
Standalone benchmark — tests OLD vs NEW image loading for PSB and TIFF files.
Drop this file in your project root (same folder as main.py) and run:

    python benchmark_loader.py "E:/Projects/Image Db/PSB FILE/PSB FILE/GLOSSY"

It will:
  1. Find up to MAX_FILES PSB/TIFF files in the folder you pass
  2. Test OLD loading method (psd_tools.topil / plain PIL)
  3. Test NEW loading method (raw thumbnail / draft mode)
  4. Print a full timing report with per-file breakdown
  5. Show projected time for 5000 files

No changes to your actual app — just read-only testing.
"""

import os
import sys
import io
import struct
import time
import statistics
from pathlib import Path

# ── Make sure app imports work when run from project root ─────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

try:
    from psd_tools import PSDImage
    HAS_PSD_TOOLS = True
except ImportError:
    HAS_PSD_TOOLS = False
    print("[warn] psd_tools not installed — PSB old-method test will be skipped")

# ── Config ─────────────────────────────────────────────────────────────
MAX_FILES   = 20       # files to sample per type (keep small for quick run)
EXTENSIONS  = (".psb", ".psd", ".tif", ".tiff")

SEPARATOR   = "─" * 70


# ══════════════════════════════════════════════════════════════════════
# OLD METHODS (copy of your original code)
# ══════════════════════════════════════════════════════════════════════

def old_load_psb(path: str) -> Image.Image:
    psd = PSDImage.open(path)
    img = psd.topil()
    if img is None:
        img = psd.composite()
    if img is None:
        raise RuntimeError(f"PSD/PSB load failed: {path}")
    return img.convert("RGB")


def old_load_tiff(path: str) -> Image.Image:
    img = Image.open(path)
    try:
        img.seek(1)
        if max(img.size) <= 512:
            return img.convert("RGB")
    except Exception:
        pass
    img.seek(0)
    return img.convert("RGB")


# ══════════════════════════════════════════════════════════════════════
# NEW METHODS (from image_loader.py)
# ══════════════════════════════════════════════════════════════════════

def _read_psb_thumbnail(path: str):
    try:
        with open(path, "rb") as f:
            sig = f.read(4)
            if sig != b"8BPS":
                return None
            f.read(2)   # version
            f.read(6)   # reserved
            f.read(2)   # channels
            f.read(4)   # height
            f.read(4)   # width
            f.read(4)   # depth + color mode

            color_mode_len = struct.unpack(">I", f.read(4))[0]
            f.read(color_mode_len)

            resources_len = struct.unpack(">I", f.read(4))[0]
            resources_end = f.tell() + resources_len

            while f.tell() < resources_end:
                sig2 = f.read(4)
                if sig2 != b"8BIM":
                    break
                res_id   = struct.unpack(">H", f.read(2))[0]
                name_len = struct.unpack("B", f.read(1))[0]
                pad      = 1 if (name_len + 1) % 2 != 0 else 0
                f.read(name_len + pad)
                data_len = struct.unpack(">I", f.read(4))[0]
                data_pos = f.tell()

                if res_id in (1033, 1036):
                    f.read(4)   # fmt
                    f.read(24)  # rest of thumbnail header
                    jpeg_len = data_len - 28
                    if jpeg_len > 0:
                        jpeg_bytes = f.read(jpeg_len)
                        img = Image.open(io.BytesIO(jpeg_bytes))
                        return img.convert("RGB")

                f.seek(data_pos + data_len + (data_len % 2))
    except Exception:
        pass
    return None


def new_load_psb(path: str) -> Image.Image:
    img = _read_psb_thumbnail(path)
    if img is not None:
        return img
    # fallback
    if HAS_PSD_TOOLS:
        return old_load_psb(path)
    raise RuntimeError("No thumbnail and psd_tools not available")


def new_load_tiff(path: str) -> Image.Image:
    img = Image.open(path)
    try:
        img.seek(1)
        if max(img.size) <= 1024:
            return img.convert("RGB")
    except Exception:
        pass
    img.seek(0)
    try:
        img.draft("RGB", (512, 512))
    except Exception:
        pass
    return img.convert("RGB")


# ══════════════════════════════════════════════════════════════════════
# Benchmark runner
# ══════════════════════════════════════════════════════════════════════

def benchmark_file(path: str, old_fn, new_fn, label: str) -> dict:
    result = {
        "path":         path,
        "filename":     os.path.basename(path),
        "size_mb":      os.path.getsize(path) / 1024 / 1024,
        "label":        label,
        "old_ms":       None,
        "new_ms":       None,
        "old_size":     None,
        "new_size":     None,
        "thumbnail_hit": False,
        "old_error":    None,
        "new_error":    None,
    }

    # ── OLD ──────────────────────────────────────────────────────────
    try:
        t0  = time.perf_counter()
        img = old_fn(path)
        result["old_ms"]   = (time.perf_counter() - t0) * 1000
        result["old_size"] = img.size
    except Exception as e:
        result["old_error"] = str(e)

    # ── NEW ──────────────────────────────────────────────────────────
    try:
        t0  = time.perf_counter()
        img = new_fn(path)
        result["new_ms"]   = (time.perf_counter() - t0) * 1000
        result["new_size"] = img.size
        # Detect if thumbnail was used (small image = thumbnail, large = full decode)
        if label in ("PSB", "PSD") and img.size[0] <= 1024:
            result["thumbnail_hit"] = True
    except Exception as e:
        result["new_error"] = str(e)

    return result


def find_files(folder: str, exts: tuple, limit: int) -> list:
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d.lower() != "__macosx"]
        for f in files:
            if f.lower().endswith(exts):
                found.append(os.path.join(root, f))
                if len(found) >= limit:
                    return found
    return found


def print_table(results: list, title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)
    print(f"  {'File':<35} {'Size':>7}  {'OLD ms':>8}  {'NEW ms':>8}  {'Speedup':>8}  {'Thumb?'}")
    print(f"  {'─'*35} {'─'*7}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*6}")

    speedups = []
    for r in results:
        name    = r["filename"][:34]
        size    = f"{r['size_mb']:.1f} MB"
        old_ms  = f"{r['old_ms']:.1f}" if r["old_ms"] is not None else "ERROR"
        new_ms  = f"{r['new_ms']:.1f}" if r["new_ms"] is not None else "ERROR"
        thumb   = "✅" if r["thumbnail_hit"] else "❌"

        if r["old_ms"] and r["new_ms"] and r["new_ms"] > 0:
            speedup = r["old_ms"] / r["new_ms"]
            speedups.append(speedup)
            sp_str = f"{speedup:.1f}x"
        else:
            sp_str = "—"

        if r["old_error"]:
            old_ms = f"ERR: {r['old_error'][:20]}"
        if r["new_error"]:
            new_ms = f"ERR: {r['new_error'][:20]}"

        print(f"  {name:<35} {size:>7}  {old_ms:>8}  {new_ms:>8}  {sp_str:>8}  {thumb}")

    print(SEPARATOR)
    if speedups:
        avg = statistics.mean(speedups)
        med = statistics.median(speedups)
        print(f"  Average speedup: {avg:.1f}x    Median: {med:.1f}x")

        old_times = [r["old_ms"] for r in results if r["old_ms"]]
        new_times = [r["new_ms"] for r in results if r["new_ms"]]
        if old_times and new_times:
            avg_old = statistics.mean(old_times)
            avg_new = statistics.mean(new_times)
            print(f"  Avg OLD: {avg_old:.1f} ms/file    Avg NEW: {avg_new:.1f} ms/file")

            for n in [100, 500, 1000, 5000]:
                old_proj = avg_old * n / 1000
                new_proj = avg_new * n / 1000
                print(f"  Projected {n:>5} files → OLD: {old_proj:>6.1f}s ({old_proj/60:.1f}m)  "
                      f"NEW: {new_proj:>6.1f}s ({new_proj/60:.1f}m)")

    thumb_hits = sum(1 for r in results if r["thumbnail_hit"])
    print(f"\n  Thumbnail extracted: {thumb_hits}/{len(results)} files")
    if thumb_hits < len(results):
        print(f"  ⚠️  {len(results)-thumb_hits} files had no embedded thumbnail → fell back to full decode")
        print(f"     These files will be slower. Save them from Photoshop with 'Maximize Compatibility' ON.")


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    folder = os.path.abspath(folder)

    if not os.path.isdir(folder):
        print(f"❌ Not a directory: {folder}")
        sys.exit(1)

    print(f"\n{'═'*70}")
    print(f"  Visara Image Loader Benchmark")
    print(f"  Folder : {folder}")
    print(f"  Samples: up to {MAX_FILES} files per type")
    print(f"{'═'*70}")

    # ── PSB / PSD ─────────────────────────────────────────────────────
    psb_files = find_files(folder, (".psb", ".psd"), MAX_FILES)
    if psb_files and HAS_PSD_TOOLS:
        print(f"\n⏳ Testing {len(psb_files)} PSB/PSD files (OLD = psd_tools.topil, NEW = raw thumbnail)...")
        psb_results = []
        for i, path in enumerate(psb_files, 1):
            ext = os.path.splitext(path)[1].upper().lstrip(".")
            print(f"   [{i:>2}/{len(psb_files)}] {os.path.basename(path)}", end="", flush=True)
            r = benchmark_file(path, old_load_psb, new_load_psb, ext)
            psb_results.append(r)
            thumb = "✅ thumb" if r["thumbnail_hit"] else "❌ full"
            old_s = f"{r['old_ms']:.0f}ms" if r["old_ms"] else "ERR"
            new_s = f"{r['new_ms']:.0f}ms" if r["new_ms"] else "ERR"
            print(f"  {old_s} → {new_s}  {thumb}")
        print_table(psb_results, "PSB / PSD Results")
    elif not psb_files:
        print(f"\n⚠️  No PSB/PSD files found in: {folder}")
    elif not HAS_PSD_TOOLS:
        print(f"\n⚠️  psd_tools not installed — skipping PSB/PSD old-method comparison")

    # ── TIFF ──────────────────────────────────────────────────────────
    tiff_files = find_files(folder, (".tif", ".tiff"), MAX_FILES)
    if tiff_files:
        print(f"\n⏳ Testing {len(tiff_files)} TIFF files (OLD = plain PIL, NEW = draft mode)...")
        tiff_results = []
        for i, path in enumerate(tiff_files, 1):
            print(f"   [{i:>2}/{len(tiff_files)}] {os.path.basename(path)}", end="", flush=True)
            r = benchmark_file(path, old_load_tiff, new_load_tiff, "TIFF")
            tiff_results.append(r)
            old_s = f"{r['old_ms']:.0f}ms" if r["old_ms"] else "ERR"
            new_s = f"{r['new_ms']:.0f}ms" if r["new_ms"] else "ERR"
            print(f"  {old_s} → {new_s}")
        print_table(tiff_results, "TIFF Results")
    else:
        print(f"\n⚠️  No TIFF files found in: {folder}")

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'═'*70}")
    print("  HOW TO READ THIS:")
    print("  • 'Thumb? ✅' = fast path worked (5–15ms)")
    print("  • 'Thumb? ❌' = fell back to full decode (slow)")
    print("  • If many ❌: open files in Photoshop → Save As → tick 'Maximize Compatibility'")
    print("  • TIFF speedup depends on file size — bigger files = bigger speedup")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    main()