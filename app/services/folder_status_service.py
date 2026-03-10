import os
from app.core import database as db

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".psd", ".psb")


def _build_tree_recursive(folder: str, indexed_set: set, disk_set: set) -> dict:
    """
    indexed_set — paths currently in DB
    disk_set    — paths currently on disk (pre-scanned, passed in)
    """
    if not os.path.exists(folder):
        return None

    try:
        entries = sorted(os.listdir(folder))
    except PermissionError:
        return None

    children   = []
    file_nodes = []

    # ── Recurse into subfolders first ───────────────────────────────────
    # for entry in entries:
    #     full_path = os.path.join(folder, entry)
    #     if os.path.isdir(full_path):
    #         subtree = _build_tree_recursive(full_path, indexed_set, disk_set)
    #         if subtree is not None:
    #             children.append(subtree)
    for entry in entries:
        if entry.lower() in _SKIP_FOLDERS:
            continue
        full_path = os.path.join(folder, entry)
        if os.path.isdir(full_path):
            subtree = _build_tree_recursive(full_path, indexed_set, disk_set)
            if subtree is not None:
                children.append(subtree)

    # ── Add image files in this folder ──────────────────────────────────
    # Only show files that exist on disk RIGHT NOW
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

    if not file_nodes and not children:
        return None

    all_children = children + file_nodes

    # ── Folder summary — based on disk_set (truth) vs indexed_set ───────
    # Files on disk under this folder
    folder_norm    = os.path.normpath(folder) + os.sep
    on_disk        = {p for p in disk_set    if p.startswith(folder_norm)}
    indexed_here   = {p for p in indexed_set if p.startswith(folder_norm)}

    total_on_disk  = len(on_disk)
    total_indexed  = len(indexed_here & on_disk)   # indexed AND on disk
    not_loaded     = len(on_disk - indexed_here)    # on disk but NOT indexed

    if not_loaded > 0:
        status = "partial"
    elif total_on_disk == 0:
        status = "folder_missing"
    else:
        status = "fully_loaded"

    summary = {
        "folder":        os.path.normpath(folder),
        "indexed":       total_indexed,    # files both on disk AND in DB
        "total_on_disk": total_on_disk,    # files actually on disk right now
        "not_loaded":    not_loaded,       # files on disk but missing from DB
        "stale":         len(indexed_here - on_disk),  # in DB but deleted from disk
        "status":        status
    }

    return {
        "label":    os.path.normpath(folder),
        "icon":     "pi pi-folder",
        "expanded": False,
        "data":     summary,
        "children": all_children
    }

_SKIP_FOLDERS = {"__macosx"}

# def _scan_disk_images(folder: str) -> set:
#     """Return set of all image paths currently on disk under folder."""
#     result = set()
#     try:
#         for root, _, files in os.walk(folder):
#             for f in files:
#                 if f.lower().endswith(IMAGE_EXTENSIONS):
#                     result.add(os.path.normpath(os.path.join(root, f)))
#     except PermissionError:
#         pass
#     return result

def _scan_disk_images(folder: str) -> set:
    """Return set of all image paths currently on disk under folder."""
    result = set()
    try:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d.lower() not in _SKIP_FOLDERS]
            for f in files:
                if f.lower().endswith(IMAGE_EXTENSIONS):
                    result.add(os.path.normpath(os.path.join(root, f)))
    except PermissionError:
        pass
    return result


def get_folder_statuses() -> dict:
    con           = db.get_connection()
    indexed_paths = [r[0] for r in con.execute("SELECT path FROM files").fetchall()]
    con.close()

    indexed_set: set = {os.path.normpath(p) for p in indexed_paths}
    top_level_folders = _find_top_level_roots(indexed_set)

    disk_set: set = set()
    for root_folder in top_level_folders:
        disk_set |= _scan_disk_images(root_folder)

    flat_list = []
    tree      = []

    for root_folder in sorted(top_level_folders):
        node = _build_tree_recursive(root_folder, indexed_set, disk_set)
        if node is None:
            continue
        tree.append(node)
        flat_list.append(node["data"])

    order = {"partial": 0, "fully_loaded": 1, "folder_missing": 2}
    flat_list.sort(key=lambda x: (order[x["status"]], x["folder"]))
    tree.sort(key=lambda x: (order[x["data"]["status"]], x["label"]))

    return {
        "flat_list": flat_list,
        "tree":      tree
    }


def _find_top_level_roots(indexed_set: set) -> set:
    all_folders = {os.path.dirname(p) for p in indexed_set}
    roots = set()
    for folder in all_folders:
        is_subfolder = any(
            folder != other and folder.startswith(other + os.sep)
            for other in all_folders
        )
        if not is_subfolder:
            roots.add(folder)
    return roots