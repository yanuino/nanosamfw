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

## GUI Version

If you prefer a graphical interface over the command line, GNSF also comes with a GUI version:

![GNSF GUI Screenshot](https://github.com/keklick1337/gnsf/blob/main/screenshots/gui.png?raw=true)

### Pre-compiled Windows Binaries

Windows users can download ready-to-use executable files for both GUI and console versions from the [GitHub Releases](https://github.com/keklick1337/gnsf/releases) page - no Python installation required!

### GUI Requirements

- Python 3.6+
- Tkinter (included with most Python installations)

### Running the GUI

#### On Windows

```bash
# Navigate to the GNSF directory
cd gnsf

# Run the GUI
python gnsf-GUI.py
```

#### On macOS

```bash
# Navigate to the GNSF directory
cd gnsf

# Run the GUI
python3 gnsf-GUI.py
```

Or make it executable and double-click in Finder:

```bash
chmod +x gnsf-GUI.py
```

#### On Linux

```bash
# Navigate to the GNSF directory
cd gnsf

# Ensure Tkinter is installed (Ubuntu/Debian example)
sudo apt-get install python3-tk

# Run the GUI
python3 gnsf-GUI.py
```

Or make it executable:

```bash
chmod +x gnsf-GUI.py
./gnsf-GUI.py
```

### GUI Features

- Easy firmware checking across multiple regions
- Download progress with speed and ETA display
- Auto-opening of download folder when complete
- All the power of the CLI with a user-friendly interface

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

---

## Additional Resources

### Samsung Firmware Monitor

If you need to check available firmware before downloading or want to monitor the latest releases:

- 🌐 **[Samsung Firmware Monitor](https://samsung-firmware.trustcrypt.com/)** - A comprehensive online database where you can browse and monitor the latest firmware releases for any Samsung device model.

This resource complements GNSF by letting you:
- Check available firmware versions across multiple devices at once
- Monitor when new firmware gets released
- View firmware details before downloading

---