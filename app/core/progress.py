import threading

_lock = threading.Lock()

_state = {
    "active":  False,
    "total":   0,
    "done":    0,
    "current": "",
    "percent": 0,
    "phase":   "idle",
    "errors":  0,
}


def set_progress(done=None, total=None, current=None, phase=None, errors=None):
    with _lock:
        if done    is not None: _state["done"]    = done
        if total   is not None: _state["total"]   = total
        if current is not None: _state["current"] = current
        if phase   is not None: _state["phase"]   = phase
        if errors  is not None: _state["errors"]  = errors
        if _state["total"] > 0:
            _state["percent"] = round(_state["done"] / _state["total"] * 100, 1)
        _state["active"] = _state["phase"] != "idle"

def increment_errors():
    with _lock:
        _state["errors"] += 1

def get_progress() -> dict:
    with _lock:
        return dict(_state)


def reset():
    with _lock:
        _state.update({
            "active": False, "total": 0, "done": 0,
            "current": "", "percent": 0, "phase": "idle", "errors": 0
        })