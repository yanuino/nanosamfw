# Copilot Instructions for nanosamfw

## Project Overview
nanosamfw (NotANOtherSamsungFirmware downloader) is a Python package for programmatic access to Samsung firmware downloads. It provides:
- A backend client for Samsung Firmware Update Service
- High-level API for firmware downloads using Model, CSC, and IMEI
- Integration capabilities for tools and workflows

## Technical Requirements
- Python 3.12 or higher
- Dependencies:
  - pycryptodome
  - requests
  - tqdm

## Project Structure

### Core Components

#### FUS (Firmware Update Service) Module - `/fus`
- `client.py` - Core FUS client implementation
- `config.py` - Configuration settings for FUS
- `crypto.py` - Cryptographic operations
- `csclist.py` - CSC (Country Specific Code) handling
- `decrypt.py` - Firmware decryption utilities
- `deviceid.py` - Device identification logic 
- `errors.py` - Custom error definitions
- `firmware.py` - Firmware management
- `messages.py` - FUS protocol messages
- `responses.py` - FUS response handling

#### Download Module - `/download`
- `config.py` - Download configuration
- `db.py` - Database operations
- `imei_repository.py` - IMEI management
- `repository.py` - Download repository logic
- `service.py` - Download service implementation
- `sql/` - SQL queries and database schemas

### Data Directories
- `data/` - Application data storage
- `downloads/` - Downloaded firmware storage
- `firmwares/` - Firmware related data

### Project Files
- `simple_client.py` - Example client implementation
- `requirements.txt` - Production dependencies
- `dev-requirements.txt` - Development dependencies
- `pyproject.toml` - Project metadata and build settings

## Development Guidelines

### Code Style
- Follow PEP 8 style guide
- Use type hints for function parameters and return values
- Document public APIs with docstrings
- Keep modules focused and single-responsibility

### Error Handling
- Use custom error types from `fus/errors.py`
- Properly propagate errors up the call stack
- Include meaningful error messages

### Database Operations
- Use parameterized queries to prevent SQL injection
- Follow the repository pattern in `download/repository.py`
- Handle database connections carefully

### Cryptographic Operations
- Use established cryptographic primitives from pycryptodome
- Follow best practices for key management
- Do not modify cryptographic implementations without thorough review

### Testing Guidelines
- Write unit tests for new functionality
- Test error cases and edge conditions
- Mock external services in tests
- Verify cryptographic operations with test vectors

## License and Attribution
This project is MIT licensed. When modifying code, ensure to:
- Maintain copyright notices
- Document significant changes
- Credit original authors when adapting code
- Follow MIT license terms