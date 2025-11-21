from tqdm import tqdm

from download import download_and_decrypt
from download.db import init_db

# Initialize the database
init_db()


# Progress callback using tqdm for smooth updates
def make_progress_cb(phase_name: str):
    state = {"bar": None, "last": 0, "total": 0}

    def _cb(done: int, total: int) -> None:
        # Initialize or reset bar when total changes or counter resets
        if state["bar"] is None or total != state["total"] or done < state["last"]:
            if state["bar"] is not None:
                state["bar"].close()
            state["bar"] = tqdm(total=total, unit="B", unit_scale=True, desc=phase_name, leave=True)
            state["last"] = 0
            state["total"] = total
        # Update by delta to avoid double counting
        delta = done - state["last"]
        if delta > 0:
            state["bar"].update(delta)
            state["last"] = done

    return _cb


# Download and decrypt with progress bars
firmware, decrypted = download_and_decrypt(
    model="SM-A146P",
    csc="EUX",
    device_id="352976245060954",
    resume=True,
    progress_cb=make_progress_cb("Processing"),
)

print()
print("✅ Complete!")
print(f"Version: {firmware.version_code}")
print(f"Decrypted file: {decrypted}")
