from download import download_and_decrypt
from download.db import init_db

# Initialize the database
init_db()

# Download and decrypt in one call
firmware, decrypted = download_and_decrypt(
    model="SM-A146P",
    csc="EUX",
    device_id="352976245060954",
    resume=True,
)

print(f"Version: {firmware.version_code}")
print(f"Decrypted file: {decrypted}")
