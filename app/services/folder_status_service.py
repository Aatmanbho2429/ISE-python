import os
from app.core import database as db

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".psd", ".psb")


def _build_tree_recursive(folder: str, indexed_set: set) -> dict:
    if not os.path.exists(folder):
        return None

    children = []

    try:
        entries = sorted(os.listdir(folder))
    except PermissionError:
        return None

    # ── Recurse into subfolders first ───────────────────────────────────
    for entry in entries:
        full_path = os.path.join(folder, entry)
        if os.path.isdir(full_path):
            subtree = _build_tree_recursive(full_path, indexed_set)
            if subtree is not None:   # only include if it has images somewhere
                children.append(subtree)

    # ── Add image files in this folder ──────────────────────────────────
    file_nodes = []
    for entry in entries:
        full_path = os.path.normpath(os.path.join(folder, entry))
        if os.path.isfile(full_path) and entry.lower().endswith(IMAGE_EXTENSIONS):
            status = "loaded" if full_path in indexed_set else "not_loaded"
            file_nodes.append({
                "label": entry,
                "leaf":  True,
                "icon":  "pi pi-image",
                "data":  {
                    "path":   full_path,
                    "status": status
                }
            })

    # If no images anywhere in this subtree — skip entirely
    if not file_nodes and not children:
        return None

    # Files come after subfolders in children list
    all_children = children + file_nodes

    # ── Compute folder-level summary ────────────────────────────────────
    # Count recursively: all images under this folder (files + subfolders)
    total_on_disk  = _count_disk_images(folder)
    indexed_here   = _count_indexed_under(folder, indexed_set)
    not_loaded     = total_on_disk - indexed_here

    if not os.path.exists(folder):
        status = "folder_missing"
    elif not_loaded > 0:
        status = "partial"
    else:
        status = "fully_loaded"

    summary = {
        "folder":        os.path.normpath(folder),
        "indexed":       indexed_here,
        "total_on_disk": total_on_disk,
        "not_loaded":    not_loaded,
        "status":        status
    }

    return {
        "label":    os.path.normpath(folder),   # full path as label
        "icon":     "pi pi-folder",
        "expanded": False,
        "data":     summary,
        "children": all_children
    }


def _count_disk_images(folder: str) -> int:
    """Count all image files recursively on disk under folder."""
    count = 0
    try:
        for root, _, files in os.walk(folder):
            count += sum(1 for f in files if f.lower().endswith(IMAGE_EXTENSIONS))
    except PermissionError:
        pass
    return count


def _count_indexed_under(folder: str, indexed_set: set) -> int:
    """Count how many files in indexed_set are under this folder."""
    folder = os.path.normpath(folder) + os.sep
    return sum(1 for p in indexed_set if p.startswith(folder))


def get_folder_statuses() -> dict:
    """
    Returns:
      flat_list — one entry per unique TOP-LEVEL folder (for table view)
      tree      — full recursive PrimeNG TreeNode structure
    """
    con           = db.get_connection()
    indexed_paths = [r[0] for r in con.execute("SELECT path FROM files").fetchall()]
    con.close()

    # Normalize all indexed paths
    indexed_set: set = {os.path.normpath(p) for p in indexed_paths}

    # Find all unique TOP-LEVEL folders (highest common roots)
    # e.g. if DB has D:\Photos\2024\img.jpg and D:\Photos\2025\img.jpg
    # top-level roots = { D:\Photos }
    top_level_folders = _find_top_level_roots(indexed_set)

    flat_list = []
    tree      = []

    for root_folder in sorted(top_level_folders):
        node = _build_tree_recursive(root_folder, indexed_set)
        if node is None:
            continue

        tree.append(node)
        flat_list.append(node["data"])

    # Sort: partial → fully_loaded → folder_missing
    order = {"partial": 0, "fully_loaded": 1, "folder_missing": 2}
    flat_list.sort(key=lambda x: (order[x["status"]], x["folder"]))
    tree.sort(key=lambda x: (order[x["data"]["status"]], x["label"]))

    return {
        "flat_list": flat_list,
        "tree":      tree
    }


def _find_top_level_roots(indexed_set: set) -> set:
    """
    Given a set of file paths, find the minimal set of parent folders
    such that every file is under one of them.

    Example:
        D:\Photos\2024\a.jpg
        D:\Photos\2025\b.jpg
        D:\Work\assets\c.png
    → roots: { D:\Photos, D:\Work\assets }

    We walk up each path and collapse to the highest folder that
    still exists on disk and contains images.
    """
    # Get all unique parent folders
    all_folders = {os.path.dirname(p) for p in indexed_set}

    # Remove any folder that is a subfolder of another folder in the set
    # i.e. keep only the roots
    roots = set()
    for folder in all_folders:
        # Check if any other folder in the set is a parent of this one
        is_subfolder = any(
            folder != other and folder.startswith(other + os.sep)
            for other in all_folders
        )
        if not is_subfolder:
            roots.add(folder)

    return roots