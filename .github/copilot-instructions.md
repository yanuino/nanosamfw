# Copilot Instructions for nanosamfw

## Project Overview
nanosamfw (NotANOtherSamsungFirmware downloader) is a Python package for programmatic access to Samsung firmware downloads. It provides:
- A backend client for Samsung Firmware Update Service (FUS)
- High-level API for firmware downloads using Model, CSC, and IMEI
- Integration capabilities for tools and workflows

## Technical Requirements
- Python 3.12 or higher (3.14+ in pyproject.toml)
- Dependencies: `pycryptodome`, `requests`, `tqdm`
- SQLite for download/IMEI tracking
- MkDocs Material for documentation

## Architecture & Data Flow

### Two-Layer Design
The codebase is split into low-level protocol (`fus/`) and high-level service (`download/`):

1. **FUS Layer** (`fus/`) - Protocol implementation
   - `FUSClient` manages session, NONCE rotation, signature generation
   - Each request to Samsung servers follows: NONCE → Sign → Request → Parse
   - NONCE is server-provided, encrypted with `KEY_1` (see `crypto.py`)
   - Signatures use client-side NONCE + logic-check algorithm
   - XML payloads built via `messages.py`, parsed via `responses.py`

2. **Download Layer** (`download/`) - Orchestration & persistence
   - `download_firmware()` is the main entry point (see `service.py`)
   - Workflow: version resolution → inform → init → download → decrypt → persist
   - Database uses repository pattern with explicit transaction management
   - Files organized as `data/downloads/model/csc/filename.enc4`

### Critical FUS Protocol Flow
```python
# 1. Client bootstrap (auto in __init__)
client = FUSClient()  # Gets initial NONCE from server

# 2. BinaryInform - query firmware metadata
xml = client.inform(build_binary_inform(version, model, csc, imei, client.nonce))
filename, path, size = get_info_from_inform(xml)

# 3. BinaryInit - authorize download (uses logic_check on last 16 chars of filename)
client.init(build_binary_init(filename, client.nonce))

# 4. Download - stream with Range support
response = client.stream(filename, start=0)  # Returns requests.Response

# 5. Decrypt (optional) - ENC4 requires logic_value from inform response
key = get_v4_key(version, model, csc, imei, client)
decrypt_file(enc_path, out_path, enc_ver=4, key=key)
```

### Key Integration Points
- **Database**: WAL mode, autocommit (isolation_level=None), explicit BEGIN/COMMIT
- **Cryptography**: 
  - `KEY_1`, `KEY_2` are hardcoded Samsung constants (in `crypto.py`)
  - ENC2 uses MD5 of `region:model:version`
  - ENC4 uses MD5 of logic_check result (requires FUS inform call)
- **File Operations**: 
  - Downloads use `.part` suffix for resume support
  - Atomic rename on completion
  - Path separators sanitized to underscores in directory names

## Development Guidelines

### Code Style (from pyproject.toml)
- **Line Length**: 100 chars max (Black + Pylint enforced)
- **Type Hints**: Required for all function parameters and return values
- **Docstrings**: Google-style for all public APIs
  - Use proper `Args:`, `Returns:`, `Raises:` sections
  - No parenthetical exception notes - use `ExceptionType: description` format
- **Import Ordering**: isort with profile "black"
  - Known first-party: `download`, `fus`
  - Use `combine_as_imports = true`
- **String Quotes**: Skip normalization (preserve original quotes)
- **Good Names**: Short names OK for:
  - Loops: `i`, `j`, `k`, `_`
  - Database: `id`, `pk`, `db`
  - Files: `fn`, `fp`
  - Exceptions: `ex`
  - Time: `ts`, `dt`

### Database Patterns
```python
# Always use explicit transactions (connection is autocommit)
with connect() as conn:
    conn.execute("BEGIN;")
    try:
        conn.execute(sql, params)
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise

# Use parameterized queries (dict or tuple)
conn.execute("INSERT INTO table (col) VALUES (:val)", {"val": value})
conn.execute("SELECT * FROM table WHERE id=?", (id,))

# Repository pattern returns dataclasses or yields them
def find_download(...) -> Optional[DownloadRecord]:
def list_downloads(...) -> Iterable[DownloadRecord]:
```

### Error Handling
- Use custom errors from `fus/errors.py`: `FUSError`, `AuthError`, `InformError`, `DownloadError`, `DecryptError`, `DeviceIdError`
- Propagate errors up - don't swallow without context
- Include server status codes in error messages (e.g., `InformError(f"status {status}")`)

### Cryptographic Operations
- **Do not modify** `KEY_1`, `KEY_2` constants - they're Samsung-specific
- **Do not change** logic_check algorithm - it's protocol-defined
- Use established pycryptodome primitives (AES.new, PKCS padding)
- ENC4 key derivation requires a live FUS inform call (can't be pre-computed)

### Testing & Validation
- No test suite currently - use `simple_client.py` for manual validation
- Test against real Samsung servers (be mindful of rate limiting)
- Verify cryptographic operations with known firmware files
- Check database integrity with `is_healthy()` before repairs

## Documentation Workflow

### Building Docs
```bash
# Local preview
mkdocs serve

# Build static site
mkdocs build -v

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### API Documentation
- Uses mkdocstrings with Python handler
- Docstring style: Google (configured in mkdocs.yml)
- Auto-generated from source docstrings
- Manual pages in `docs/` (index.md, database/schema.md)

## Common Workflows

### Adding a New FUS Endpoint
1. Add XML builder to `fus/messages.py` (follow `_hdr()` + `_body_put()` pattern)
2. Add method to `FUSClient` (use `_makereq()`, return parsed ET.Element)
3. Add response parser to `fus/responses.py` if complex data needed
4. Update docstrings with Args/Returns/Raises

### Adding Database Tables
1. Add SQL to `download/sql/*.sql` with schema + indexes
2. Update `SCHEMA_SQL` in `download/db.py`
3. Create dataclass in appropriate repository file
4. Add repository functions (find, list, upsert pattern)
5. Update `docs/database/schema.md` with table documentation

### Debugging Download Issues
- Check `data/firmware.db` for download records
- `.part` files indicate incomplete downloads
- Enable verbose logging by inspecting requests.Response objects
- Verify IMEI/Serial validation with `deviceid.py` helpers

## License and Attribution
This project is MIT licensed and builds upon GNSF (see: https://github.com/keklick1337/gnsf) by keklick1337.
- Maintain copyright notices in file headers
- Document significant changes
- Credit original authors when adapting code