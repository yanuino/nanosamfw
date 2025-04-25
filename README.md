# GNSF – Get New Samsung Firmware

Hey there! 👋  
Ever needed to grab the latest Samsung firmware for **Odin** and decrypt it without jumping through hoops? That’s exactly why I built **GNSF**. It’s a simple CLI tool that helps you:

- Fetch the newest firmware for your Samsung model/region  
- Download it with resume support  
- Auto-decrypt `.enc2`/`.enc4` packages  

All in one go.

Project URL: https://github.com/keklick1337/gnsf

---

## Features

- 🔍 `check` command to list the latest firmware version  
- ⬇️ `download` command to grab and decrypt firmware  
- 🔐 `decrypt` command for manual decryption of `.enc2` / `.enc4` files  
- 🧩 Auto‑fill your IMEI (if you give 8+ digits)  
- ↪️ Resume downloads if they got interrupted  

---

## Requirements

- Python 3.6+  
- Pip dependencies (we’ve got `pycryptodome`, `requests`, `tqdm` listed in `requirements.txt`)

---

## Installation

1. Clone this repo  
   ```bash
   git clone https://github.com/keklick1337/gnsf.git
   cd gnsf
   ```

2. Install dependencies  
   ```bash
   pip install -r requirements.txt
   ```

You’re all set!

---

## Usage

Run the main script with `-m` (model) and `-r` (region), plus one of the commands below:

```bash
python gnsf.py -m <MODEL> -r <CSC> <command> [options]
# or
./gnsf.py -m <MODEL> -r <CSC> <command> [options]
```

### 1. check

See what the latest firmware is for a specific region, or loop through all known CSC codes:

```bash
# Single region
./gnsf.py -m SM-S928B -r XSA check

# All regions (will print “not found” if not available)
./gnsf.py -m SM-S928B check
```

### 2. download

Download + decrypt in one shot:

```bash
./gnsf.py \
  -m SM-S928B \
  -r XSA \
  download \
  -i 12345678 \
  -O ./downloads \
  # Replace 12345678 to your IMEI
  # optionally -v to specify a version; omit for “latest”
  # use --resume to pick up where you left off
  # add --no-decrypt to skip the auto‑decrypt step
```

### 3. decrypt

Just decrypt a file you already downloaded:

```bash
./gnsf.py \
  -m SM-S928B \
  decrypt \
  -v FULL_VERSION_NAME_HERE \
  -V 4 \
  -i firmware.enc4 \
  -o firmware.tar.md5
```

---

## Handy Tips

- If you only give the first 8 digits of your IMEI with `-i`, the tool will pad & Luhn‑check the rest for you.  
- `.enc2` files use V2 decryption, `.enc4` use V4. GNSF figures it out automatically when downloading.

---

## Contributing

Found a bug or wanna add a cool feature? PRs are welcome! Just fork, hack away, and send a pull request.  
Please keep the code style consistent, and add tests if you can.

---

## License

This project is MIT‑licensed. See the [LICENSE](LICENSE) file for details.

---

Happy flashing! 🚀  