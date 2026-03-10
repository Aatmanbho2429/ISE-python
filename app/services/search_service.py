import os
import json
import time
import numpy as np

from app.core import database as db
from app.core import indexer
from app.core.embedder import Embedder
from app.core.progress import set_progress, reset
from app.services.sync_service import sync_folder
from app.utils.file_utils import scan_images
from app.utils.image_loader import preprocess_batch_parallel


class BaseResponse:
    def __init__(self):
        self.status  = True
        self.message = ""
        self.code    = 200
        self.data    = {"success": [], "errors": [], "results": []}


def _get_query_embedding(query_image: str, response: BaseResponse) -> np.ndarray:
    embedder = Embedder()
    batch, valid, failed = preprocess_batch_parallel([query_image])
    if not valid:
        response.message = "Failed to process query image."
        raise RuntimeError(failed[0]["reason"])
    return embedder.embed_batch(batch)[0]


def search(query_image: str, folder_path: str, top_k: int) -> str:
    response    = BaseResponse()
    folder_path = os.path.normpath(folder_path)
    index       = indexer.load_index()
    t_start     = time.time()

    if not os.path.exists(query_image):
        response.status  = False
        response.message = "Query image not found."
        response.code    = 400
        return json.dumps(response.__dict__, indent=2)

    if index == "Error loading faiss.index":
        response.status  = False
        response.message = "Failed to load index. Please sync your folders first."
        response.code    = 500
        return json.dumps(response.__dict__, indent=2)

    # ── Only sync if disk count != DB count ──────────────────────────────
    con        = db.get_connection()
    db_count   = db.get_folder_file_count(con, folder_path)
    disk_count = sum(1 for _ in scan_images(folder_path))
    con.close()

    if db_count != disk_count:
        sync_folder(index, folder_path, response)
        indexer.save_index(index)

    # ── Similarity search ─────────────────────────────────────────────────
    set_progress(phase="searching", done=0, total=1,
                 current=os.path.basename(query_image))

    con = db.get_connection()
    try:
        id_map          = db.get_folder_id_map(con, folder_path)
        query           = _get_query_embedding(query_image, response)
        scores, indices = indexer.search_index(index, query, top_k)

        for rank, (idx, score) in enumerate(zip(indices, scores)):
            if idx == -1:
                continue
            if idx in id_map:
                response.data["results"].append({
                    "rank":       rank + 1,
                    "path":       id_map[idx],
                    "similarity": float(score)
                })
    except Exception as e:
        response.status = True
        response.data["errors"].append({"file": query_image, "reason": str(e)})
    finally:
        # ── Write activity log ──────────────────────────────────────────
        try:
            db.log_search(
                con          = con,
                query_image  = query_image,
                folder       = folder_path,
                results      = response.data["results"],
                errors       = response.data["errors"],
                duration_sec = time.time() - t_start,
            )
        except Exception as e:
            print(f"[activity_log] write failed: {e}", flush=True)
        con.close()

    reset()

    if response.message == "":
        response.message = "Search completed successfully"
    response.code = 200
    return json.dumps(response.__dict__, indent=2)
