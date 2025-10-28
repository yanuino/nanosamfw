<!-- Copilot / AI agent instructions for the GNSF repository -->
# Quick orientation (what this repo is)
- Purpose: CLI + GUI tool to locate, download and decrypt Samsung firmware (Odin packages).
- Two user entry points: `gnsf.py` (CLI) and `gnsf-GUI.py` (Tk GUI).

# High-level architecture (fast summary)
- `gnsf.py` – main CLI logic, argument parsing, high-level workflow (check, download, decrypt).
- `gnsf-GUI.py` – thin GUI wrapper around the same functions provided by the core modules.
- `fus/` package – core protocol implementation for Samsung FUS (Firmware Update Service):
  - `fus/client.py` — `FUSClient`: handles NONCE, JSESSIONID, POST/GET and cloud streaming.
  - `fus/messages.py` — XML builders for FUS requests (inform/init).
  - `fus/crypto.py` — AES helpers and the project’s logic_check/nonce operations.
  - `fus/decrypt.py` — ENC2/ENC4 key derivation and streaming decrypt helper (`get_v2_key`, `get_v4_key`, `decrypt_file`).
  - `fus/firmware.py` — helpers for parsing and normalizing Samsung version strings.

# Important data flows and protocol notes (what an agent must know)
- Decryption keys: V2 = MD5("region:model:version"); V4 requires a FUS `inform` call and the server‑provided logic value (see `fus/decrypt.get_v4_key`).
- `FUSClient._makereq()` manages the encrypted NONCE header and signature; downloads use cloud URL with the encrypted NONCE in Authorization header (`fus/client.py`).
- Device identity: ENC4 decryption requires either IMEI (auto-pad to 15 digits if >=8 given) or Serial Number; these checks live in `gnsf.py` (IMEIUtils) and `fus/deviceid.py`.

# Developer workflows & commands (concrete)
- Install deps: `pip install -r requirements.txt` (see `requirements.txt` for `pycryptodome`, `requests`, `tqdm`).
- Run CLI (examples from README):
  - `./gnsf.py -m SM-S928B -r XSA -i 12345678 download -O ./downloads`
  - `python gnsf.py -m <MODEL> -r <CSC> check`
- Run GUI: `python gnsf-GUI.py` (requires `tkinter` on Linux / macOS).
- Quick dev sandbox: `simple_client.py` shows example usage of `FUSClient`, `get_latest_version`, and `get_v4_key` — useful when debugging FUS interactions.

# Project conventions & patterns
- Modules under `fus/` implement small focused responsibilities (client, messages, crypto, decrypt). Prefer adding helpers in the appropriate `fus/` module.
- Network interactions centralize in `FUSClient` — reuse it rather than creating ad‑hoc requests.
- Exceptions are defined in `fus/errors.py` and are raised by library functions — prefer catching and surfacing them in CLI/GUI layers.

# Where to look when modifying behavior
- To change how keys are derived or decrypted: `fus/decrypt.py` and `fus/crypto.py`.
- To change the FUS message format or parameters: `fus/messages.py` and `fus/client.py`.
- To adjust CLI behaviours, argument checks and IMEI logic: `gnsf.py` (IMEIUtils, FUSMessageBuilder, FirmwareUtils).
- For CSC lists and region mappings: `csclist.py`.

# Debugging tips specific to this repo
- To inspect FUS exchanges, add temporary prints in `fus/client.py::_makereq()` (it handles NONCE rotation and cookies).
- Use `simple_client.py` as a minimal reproducible script to call `get_v4_key` and `FUSClient.inform()` without CLI/UI overhead.
- When investigating decryption issues, confirm the key source: V2 key (MD5) vs V4 (requires successful `inform` response and `logic_value_factory`).

# Safety / constraints for agents
- Do not exfiltrate secrets (IMEI/Serial values) unless explicitly provided in the user request/test data.
- Only act on network endpoints defined in `fus/config.py` unless the user asks to change them.

# If you need more context
- Read `README.md` for usage examples and `simple_client.py` for a compact programmatic example.
- Trace call chains: CLI → `gnsf.py` → `fus.*` (client/messages/decrypt) → cloud endpoints.

---
Please review this draft. Tell me if you want more examples (small snippets showing how to call `FUSClient` or `decrypt_file`), or if there are other internal conventions I missed and should include.
