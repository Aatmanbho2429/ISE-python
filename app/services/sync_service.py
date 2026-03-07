import os
from concurrent.futures import ThreadPoolExecutor

from app.config import BATCH_SIZE, NUM_WORKERS
from app.core import database as db
from app.core import indexer
from app.core.progress import set_progress, get_progress,increment_errors
from app.core.embedder import Embedder
from app.utils.file_utils import fast_hash, scan_images
from app.utils.image_loader import preprocess_batch_parallel


def _is_under(path: str, folder: str) -> bool:
    """Returns True if path is inside folder (including subfolders)."""
    return os.path.normpath(path).startswith(os.path.normpath(folder) + os.sep)


def sync_folder(index, folder_path: str, response) -> None:
    folder_path     = os.path.normpath(folder_path)
    current_files   = list(scan_images(folder_path))
    seen_hashes     = set()
    needs_embedding = []

    con = db.get_connection()
    db.cleanup_missing_in_folder(con, index, folder_path)

    # ── Step 1: Hash all files in parallel ──────────────────────────────
    set_progress(done=0, total=len(current_files), current="", phase="hashing", errors=0)

    def hash_one(path):
        thread_con = db.get_connection()
        try:
            current_mtime = os.path.getmtime(path)
            existing      = db.find_by_path(thread_con, path)
            if existing and abs(existing[2] - current_mtime) < 0.001:
                return path, existing[1], None, current_mtime
            return path, fast_hash(path), None, current_mtime
        except Exception as e:
            return path, None, str(e), 0.0
        finally:
            thread_con.close()

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        hash_results = list(ex.map(hash_one, current_files))

    hashed_done = 0
    for path, h, err, mtime in hash_results:
        hashed_done += 1
        set_progress(done=hashed_done, current=os.path.basename(path))

        if err:
            increment_errors()
            response.status = False
            response.data["errors"].append({"file": path, "reason": err})
            continue

        seen_hashes.add(h)
        existing_path, existing_faiss_id = db.find_by_hash(con, h)

        if existing_faiss_id is not None:
            if existing_path == path:
                # Exact match — already indexed correctly
                response.data["success"].append(path)

            elif _is_under(existing_path, folder_path):
                # ── existing path is INSIDE current folder ───────────────
                # This means the hash already belongs to a file in this
                # folder (e.g. braided\file.jpg when scanning braided2)
                # DO NOT move it — treat current file as a new copy
                # needing its own embedding
                needs_embedding.append((path, h, mtime))

            elif not os.path.exists(existing_path):
                # ── existing path is OUTSIDE folder and gone from disk ───
                # True rename/move — safe to update path in DB
                db.move_file(con, existing_path, path)
                con.commit()
                response.data["success"].append(path)

            else:
                # ── existing path is OUTSIDE folder and still on disk ────
                # File was copied from another folder
                # Both files exist — give this one its own embedding
                needs_embedding.append((path, h, mtime))

        else:
            # Hash not in DB at all — brand new file or edited content
            existing_by_path = db.find_by_path(con, path)
            if existing_by_path:
                # Same path, different hash — file was edited
                # Remove old FAISS vector first
                indexer.remove_embeddings(index, [existing_by_path[0]])
                db.delete_file(con, path)
                con.commit()
            needs_embedding.append((path, h, mtime))

    # ── Step 2: Embed new/changed/copied files in batches ────────────────
    total    = len(needs_embedding)
    done     = 0
    embedder = Embedder()

    set_progress(done=0, total=total if total > 0 else 1, phase="embedding")

    for i in range(0, total, BATCH_SIZE):
        chunk        = needs_embedding[i:i + BATCH_SIZE]
        batch_paths  = [p        for p, _, _     in chunk]
        hash_lookup  = {p: h     for p, h, _     in chunk}
        mtime_lookup = {p: mtime for p, _, mtime in chunk}

        set_progress(current=os.path.basename(batch_paths[0]))

        batch, valid_paths, failed = preprocess_batch_parallel(batch_paths)

        for f in failed:
            increment_errors()
            response.status = False
            response.data["errors"].append(f)

        if batch is not None:
            embs = embedder.embed_batch(batch)
            for path, emb in zip(valid_paths, embs):
                faiss_id = db.get_next_faiss_id(con)
                indexer.add_embedding(index, emb, faiss_id)
                db.insert_file(con, path, hash_lookup[path], faiss_id, mtime_lookup[path])
                response.data["success"].append(path)
            con.commit()

        done += len(chunk)
        set_progress(done=done)
        print(f"[sync] {done}/{total} embedded", flush=True)

    # ── Step 3: Remove files deleted from selected folder only ───────────
    all_hashes     = db.get_folder_hashes(con, folder_path)
    deleted_hashes = all_hashes - seen_hashes

    if deleted_hashes:
        rows             = db.get_files_by_hashes(con, deleted_hashes)
        faiss_ids_to_del = []
        for path, faiss_id in rows:
            faiss_ids_to_del.append(faiss_id)
            db.delete_file(con, path)
        indexer.remove_embeddings(index, faiss_ids_to_del)
        con.commit()

    con.close()
    set_progress(done=total, current="", phase="idle")