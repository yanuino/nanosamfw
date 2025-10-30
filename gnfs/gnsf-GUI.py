#!/usr/bin/env python3
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import subprocess
import time
import webbrowser
import re
import queue
import platform
from concurrent.futures import ThreadPoolExecutor
from gnsf import (CSC_DICT, getlatestver, FUSClient, getbinaryfile, 
                 initdownload, VERSION, FirmwareUtils, 
                 AES, getv2key, getv4key, CryptoUtils, IMEIUtils)

class GNSFGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"GetNewSamsungFirmware GUI v{VERSION}")
        self.geometry("800x600")
        self.minsize(800, 600)
        self._checking = False
        self._downloading = False
        self._check_thread = None
        self._download_thread = None
        self._download_start_time = 0
        
        # Set application icon
        self._set_app_icon()
        
        self._create_widgets()
    
    def _set_app_icon(self):
        """Set the application icon for window title bar and taskbar"""
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                    "AppIcons", "128.png")
            if os.path.exists(icon_path):
                self.iconphoto(True, tk.PhotoImage(file=icon_path))

            if not os.path.exists(icon_path):
                for alt_size in ["256", "512"]:
                    alt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                          "AppIcons", f"{alt_size}.png")
                    if os.path.exists(alt_path):
                        self.iconphoto(True, tk.PhotoImage(file=alt_path))
                        break
                        
        except Exception as e:
            print(f"Error setting application icon: {e}")

    def _create_widgets(self):
        # Top frame for common inputs (above tabs)
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(top_frame, text="Model:*").grid(row=0, column=0, sticky=tk.W)
        self.model_var = tk.StringVar()
        self.model_entry = ttk.Entry(top_frame, textvariable=self.model_var, width=20)
        self.model_entry.grid(row=0, column=1)

        ttk.Label(top_frame, text="CSC:*").grid(row=0, column=2, sticky=tk.W, padx=(10,0))
        self.csc_var = tk.StringVar()
        self.csc_entry = ttk.Entry(top_frame, textvariable=self.csc_var, width=10)
        self.csc_entry.grid(row=0, column=3)
        
        # Create notebook (tabs container)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create tabs
        self.download_tab = ttk.Frame(self.notebook)
        self.check_tab = ttk.Frame(self.notebook)
        self.decrypt_tab = ttk.Frame(self.notebook)  # Add new decrypt tab
        self.info_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.download_tab, text="Download")
        self.notebook.add(self.check_tab, text="Check CSC Versions")
        self.notebook.add(self.decrypt_tab, text="Manual Decrypt")  # Add to notebook
        self.notebook.add(self.info_tab, text="Info")
        
        # Setup Download Tab
        self._create_download_tab()
        
        # Setup Check CSC Tab
        self._create_check_tab()
        
        # Setup Manual Decrypt Tab
        self._create_decrypt_tab()
        
        # Setup Info Tab
        self._create_info_tab()
        
        # Bind tab switching to prevent changing tabs during operations
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _create_download_tab(self):
        # Download options frame
        frm2 = ttk.Frame(self.download_tab)
        frm2.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(frm2, text="Firmware Version:*").grid(row=0, column=0, sticky=tk.W)
        self.ver_var = tk.StringVar()
        self.ver_entry = ttk.Entry(frm2, textvariable=self.ver_var, width=25)
        self.ver_entry.grid(row=0, column=1)
        self.ver_var.trace_add("write", self._update_firmware_info)
        
        # Question mark button to switch to check tab
        self.help_btn = ttk.Button(frm2, text="?", width=2, 
                                   command=lambda: self.notebook.select(self.check_tab))
        self.help_btn.grid(row=0, column=2, padx=5)

        ttk.Label(frm2, text="IMEI (≥8 digits):").grid(row=0, column=3, sticky=tk.W, padx=(10,0))
        self.imei_var = tk.StringVar()
        self.imei_entry = ttk.Entry(frm2, textvariable=self.imei_var, width=20)
        self.imei_entry.grid(row=0, column=4)

        ttk.Label(frm2, text="Serial Number:").grid(row=1, column=3, sticky=tk.W, padx=(10,0))
        self.serial_var = tk.StringVar()
        self.serial_entry = ttk.Entry(frm2, textvariable=self.serial_var, width=20)
        self.serial_entry.grid(row=1, column=4)

        ttk.Label(frm2, text="Out Dir:").grid(row=2, column=0, sticky=tk.W, pady=(5,0))
        
        # Get platform-specific default download directory
        default_downloads = self._get_default_downloads_dir()
        self.outdir_var = tk.StringVar(value=default_downloads)
        self.outdir_entry = ttk.Entry(frm2, textvariable=self.outdir_var, width=40)
        self.outdir_entry.grid(row=2, column=1, columnspan=3, sticky=tk.W+tk.E)
        
        self.browse_btn = ttk.Button(frm2, text="Browse", command=self._browse_out)
        self.browse_btn.grid(row=2, column=4, sticky=tk.W)

        self.nodecrypt_var = tk.BooleanVar(value=False)
        self.decrypt_check = ttk.Checkbutton(frm2, text="Skip Decrypt", variable=self.nodecrypt_var)
        self.decrypt_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5,0))
        
        ttk.Label(frm2, text="* Required: Model, CSC, Version, and either IMEI or Serial Number").grid(row=3, column=1, columnspan=3, sticky=tk.E, pady=(5,0))

        self.download_btn = ttk.Button(frm2, text="Download & Decrypt", command=self._on_download)
        self.download_btn.grid(row=3, column=4, sticky=tk.E, pady=(5,0))
        
        # Firmware info frame
        self.fw_info_frame = ttk.LabelFrame(self.download_tab, text="Firmware Information")
        self.fw_info_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.fw_info_text = scrolledtext.ScrolledText(self.fw_info_frame, height=4, wrap=tk.WORD)
        self.fw_info_text.pack(fill=tk.X, padx=5, pady=5)
        self.fw_info_text.insert(tk.END, "Enter a firmware version above to see information")
        self.fw_info_text.config(state="disabled")
        
        # Progress bar for download/decrypt
        self.dl_progress_frame = ttk.Frame(self.download_tab)
        self.dl_progress_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.dl_status_var = tk.StringVar(value="Ready")
        ttk.Label(self.dl_progress_frame, textvariable=self.dl_status_var).pack(side=tk.LEFT)
        
        self.dl_progress = ttk.Progressbar(self.dl_progress_frame, orient="horizontal", 
                                          length=100, mode="determinate")
        self.dl_progress.pack(fill=tk.X, expand=True, padx=(5, 0))

        # Log area
        self.log_frame = ttk.LabelFrame(self.download_tab, text="Log")
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log = scrolledtext.ScrolledText(self.log_frame, height=10, state="disabled")
        self.log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_check_tab(self):
        # Check control frame
        check_frame = ttk.Frame(self.check_tab)
        check_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(check_frame, text="Check versions for model:").pack(side=tk.LEFT)
        self.check_btn = ttk.Button(check_frame, text="Check Versions", command=self._on_check)
        self.check_btn.pack(side=tk.RIGHT)
        ttk.Label(check_frame, text="(empty CSC = check all regions)").pack(side=tk.LEFT, padx=(10,0))
        
        # Progress bar for checks
        self.check_progress_frame = ttk.Frame(self.check_tab)
        self.check_progress_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.check_status_var = tk.StringVar(value="Ready")
        ttk.Label(self.check_progress_frame, textvariable=self.check_status_var).pack(side=tk.LEFT)
        
        self.check_progress = ttk.Progressbar(self.check_progress_frame, orient="horizontal", 
                                             length=100, mode="determinate")
        self.check_progress.pack(fill=tk.X, expand=True, padx=(5, 0))

        # Table frame - give it weight for expansion
        table_frame = ttk.Frame(self.check_tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Firmware versions treeview
        cols = ("csc", "name", "ver")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        self.tree.heading("csc", text="CSC")
        self.tree.heading("name", text="Region Name")
        self.tree.heading("ver", text="Latest Version")
        
        # Configure columns to adjust to contents and window size - removed weight parameter
        self.tree.column("csc", width=80, minwidth=60, stretch=True)
        self.tree.column("name", width=200, minwidth=150, stretch=True)
        self.tree.column("ver", width=150, minwidth=120, stretch=True)
        
        # Store column proportions for resizing
        self._column_ratios = {"csc": 0.11, "name": 0.45, "ver": 0.44}
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Configure>", self._resize_columns)
        
        # Scrollbars for treeview
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout for table and scrollbars
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        # Configure grid weights for resizing
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
    
    def _create_decrypt_tab(self):
        """Create the Manual Decrypt tab"""
        # Main frame
        decrypt_frame = ttk.Frame(self.decrypt_tab, padding=10)
        decrypt_frame.pack(fill=tk.BOTH, expand=True)
        
        # Input file selection
        ttk.Label(decrypt_frame, text="Encrypted File:*").grid(row=0, column=0, sticky=tk.W)
        
        input_frame = ttk.Frame(decrypt_frame)
        input_frame.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)
        input_frame.columnconfigure(0, weight=1)
        
        self.enc_file_var = tk.StringVar()
        self.enc_file_entry = ttk.Entry(input_frame, textvariable=self.enc_file_var, width=50)
        self.enc_file_entry.grid(row=0, column=0, sticky=tk.EW)
        
        self.enc_browse_btn = ttk.Button(input_frame, text="Browse", command=self._browse_enc_file)
        self.enc_browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # Output file/directory
        ttk.Label(decrypt_frame, text="Output File:*").grid(row=1, column=0, sticky=tk.W)
        
        output_frame = ttk.Frame(decrypt_frame)
        output_frame.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)
        output_frame.columnconfigure(0, weight=1)
        
        self.dec_file_var = tk.StringVar()
        self.dec_file_entry = ttk.Entry(output_frame, textvariable=self.dec_file_var, width=50)
        self.dec_file_entry.grid(row=0, column=0, sticky=tk.EW)
        
        self.dec_browse_btn = ttk.Button(output_frame, text="Browse", command=self._browse_dec_file)
        self.dec_browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # Encryption type selection
        ttk.Label(decrypt_frame, text="Encryption Type:*").grid(row=2, column=0, sticky=tk.W)
        
        self.enc_type_var = tk.IntVar(value=4)  # Default to ENC4
        enc_type_frame = ttk.Frame(decrypt_frame)
        enc_type_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        self.enc2_radio = ttk.Radiobutton(enc_type_frame, text="ENC2", variable=self.enc_type_var, value=2)
        self.enc2_radio.pack(side=tk.LEFT, padx=(0, 10))
        
        self.enc4_radio = ttk.Radiobutton(enc_type_frame, text="ENC4", variable=self.enc_type_var, value=4)
        self.enc4_radio.pack(side=tk.LEFT)
        
        # Auto-detect encryption type from file extension
        self.autodetect_enc_var = tk.BooleanVar(value=True)
        self.autodetect_check = ttk.Checkbutton(
            decrypt_frame, 
            text="Auto-detect from filename", 
            variable=self.autodetect_enc_var,
            command=self._update_enc_type_state
        )
        self.autodetect_check.grid(row=2, column=2, sticky=tk.W)
        
        # Firmware version
        ttk.Label(decrypt_frame, text="Firmware Version:*").grid(row=3, column=0, sticky=tk.W)
        self.dec_ver_var = tk.StringVar()
        self.dec_ver_entry = ttk.Entry(decrypt_frame, textvariable=self.dec_ver_var, width=30)
        self.dec_ver_entry.grid(row=3, column=1, sticky=tk.W, pady=5)

        # Add IMEI field
        ttk.Label(decrypt_frame, text="IMEI (for ENC4):").grid(row=4, column=0, sticky=tk.W)
        self.dec_imei_var = tk.StringVar()
        # Link it to the main IMEI field for convenience
        self.dec_imei_var.set(self.imei_var.get())
        self.dec_imei_entry = ttk.Entry(decrypt_frame, textvariable=self.dec_imei_var, width=20)
        self.dec_imei_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Add Serial Number field  
        ttk.Label(decrypt_frame, text="Serial Number (for ENC4):").grid(row=5, column=0, sticky=tk.W)
        self.dec_serial_var = tk.StringVar()
        # Link it to the main Serial Number field for convenience
        self.dec_serial_var.set(self.serial_var.get())
        self.dec_serial_entry = ttk.Entry(decrypt_frame, textvariable=self.dec_serial_var, width=20)
        self.dec_serial_entry.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # Add help text for better UX
        ttk.Label(decrypt_frame, text="(Either IMEI or Serial Number required for ENC4)").grid(
            row=5, column=2, sticky=tk.W, padx=(5, 0), pady=5
        )
        
        # Note about required fields
        ttk.Label(decrypt_frame, text="* Required fields").grid(
            row=6, column=1, columnspan=2, sticky=tk.E, pady=(10, 0)
        )
        
        # Decrypt button
        self.decrypt_btn = ttk.Button(decrypt_frame, text="Decrypt File", command=self._on_manual_decrypt)
        self.decrypt_btn.grid(row=6, column=0, sticky=tk.W, pady=(10, 0))
        
        # Progress bar
        self.dec_progress_frame = ttk.Frame(decrypt_frame)
        self.dec_progress_frame.grid(row=7, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))
        
        self.dec_status_var = tk.StringVar(value="Ready")
        ttk.Label(self.dec_progress_frame, textvariable=self.dec_status_var).pack(side=tk.LEFT)
        
        self.dec_progress = ttk.Progressbar(
            self.dec_progress_frame, 
            orient="horizontal", 
            length=100, 
            mode="determinate"
        )
        self.dec_progress.pack(fill=tk.X, expand=True, padx=(5, 0))
        
        # Log area
        self.dec_log_frame = ttk.LabelFrame(decrypt_frame, text="Decrypt Log")
        self.dec_log_frame.grid(row=8, column=0, columnspan=3, sticky=tk.NSEW, pady=(10, 0))
        decrypt_frame.rowconfigure(8, weight=1)
        
        self.dec_log = scrolledtext.ScrolledText(self.dec_log_frame, height=10, state="disabled")
        self.dec_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Set encryption state based on autodetect option
        self._update_enc_type_state()
        
        # Set up file change tracking
        self.enc_file_var.trace_add("write", self._on_enc_file_change)
        
        # Link main IMEI and decrypt IMEI fields to keep them in sync
        self.imei_var.trace_add("write", lambda *args: self.dec_imei_var.set(self.imei_var.get()))
        
        # Link main Serial Number and decrypt Serial Number fields to keep them in sync
        self.serial_var.trace_add("write", lambda *args: self.dec_serial_var.set(self.serial_var.get()))

    def _update_enc_type_state(self):
        """Enable/disable encryption type radio buttons based on autodetect setting"""
        state = "disabled" if self.autodetect_enc_var.get() else "normal"
        self.enc2_radio.configure(state=state)
        self.enc4_radio.configure(state=state)
        
        # If autodetect is enabled, try to detect from filename
        if self.autodetect_enc_var.get():
            self._detect_enc_type_from_file()

    def _detect_enc_type_from_file(self):
        """Detect encryption type from file extension"""
        filename = self.enc_file_var.get()
        if filename.lower().endswith('.enc2'):
            self.enc_type_var.set(2)
        elif filename.lower().endswith('.enc4'):
            self.enc_type_var.set(4)
        
        # Also try to auto-generate output filename
        if filename and (filename.lower().endswith('.enc2') or filename.lower().endswith('.enc4')):
            base_filename = filename.rsplit('.', 1)[0]
            if not self.dec_file_var.get():
                self.dec_file_var.set(self._get_unique_filename(base_filename))

    def _on_enc_file_change(self, *args):
        """Handle changes to the encrypted file path"""
        if self.autodetect_enc_var.get():
            self._detect_enc_type_from_file()

    def _browse_enc_file(self):
        """Browse for encrypted input file"""
        filetypes = [
            ("Encrypted Files", "*.enc2 *.enc4"),
            ("ENC2 Files", "*.enc2"),
            ("ENC4 Files", "*.enc4"),
            ("All Files", "*.*"),
        ]
        filename = filedialog.askopenfilename(
            title="Select Encrypted File",
            filetypes=filetypes
        )
        if filename:
            self.enc_file_var.set(filename)
            # The trace on self.enc_file_var will call _on_enc_file_change

    def _browse_dec_file(self):
        """Browse for decrypted output file"""
        # Get suggested filename
        input_file = self.enc_file_var.get()
        initial_file = ""
        
        if input_file:
            # Create a default output filename
            if input_file.lower().endswith(('.enc2', '.enc4')):
                initial_file = os.path.basename(input_file.rsplit('.', 1)[0])
        
        filename = filedialog.asksaveasfilename(
            title="Save Decrypted File As",
            initialfile=initial_file
        )
        if filename:
            self.dec_file_var.set(filename)

    def _dec_log(self, msg):
        """Log to the decrypt tab log"""
        self.dec_log.configure(state="normal")
        self.dec_log.insert(tk.END, msg + "\n")
        self.dec_log.see(tk.END)
        self.dec_log.configure(state="disabled")

    def decrypt_progress_GUI(self, inf, outf, key, length, callback=None):
        """
        Decrypt an encrypted firmware stream with GUI progress reporting.
        
        :param inf: file-like input with read method
        :param outf: file-like output with write method
        :param key: AES key (16 bytes)
        :param length: total input size in bytes
        :param callback: function(percent, bytes_processed, speed) -> bool
                        Returns False to cancel operation
        :raises ValueError: if length not multiple of 16
        """
        if length % 16 != 0:
            raise ValueError("Invalid input block size (not multiple of 16)")
            
        # Create AES cipher in ECB mode
        cipher = AES.new(key, AES.MODE_ECB)
        
        # Variables for progress tracking
        chunk_size = 4096
        chunks = length // chunk_size + 1
        bytes_processed = 0
        start_time = time.time()
        last_update = start_time
        update_interval = 0.1  # Update 10 times per second
        
        # Process each chunk
        for i in range(chunks):
            block = inf.read(chunk_size)
            if not block:
                break
                
            # Decrypt block
            decblock = cipher.decrypt(block)
            
            # Handle padding in last block
            if i == chunks - 1:
                outf.write(CryptoUtils.pkcs_unpad(decblock))
            else:
                outf.write(decblock)
            
            # Update progress tracking
            bytes_processed += len(block)
            current_time = time.time()
            elapsed = current_time - start_time
            speed = bytes_processed / elapsed if elapsed > 0 else 0
            percent = (bytes_processed / length) * 100
            
            # Call the progress callback if provided
            if callback and (current_time - last_update >= update_interval):
                if not callback(percent, bytes_processed, speed):
                    # Operation cancelled
                    return False
                last_update = current_time
        
        # Successful completion
        return True

    def decrypt_file_GUI(self, version, fw_ver, model, region, device_id, encrypted, decrypted, progress_callback=None):
        """
        High-level helper to decrypt a .enc2/.enc4 file with GUI progress.
        
        :param version: encryption version (2 or 4)
        :param fw_ver: firmware version string
        :param model: device model
        :param region: CSC region
        :param device_id: device ID (IMEI or Serial Number)
        :param encrypted: path to .enc2/.enc4 file
        :param decrypted: path for output decrypted file
        :param progress_callback: function(percent, bytes_processed, speed) -> bool
        :return: 0 on success, 1 on failure
        """
        if version not in (2, 4):
            raise ValueError(f"Unknown encryption version: {version}")
        
        # Use the appropriate key generation function
        getkey = getv2key if version == 2 else getv4key
        
        # Get decryption key
        try:
            key = getkey(fw_ver, model, region, device_id)
            if not key:
                self._dec_log(f"Failed to get decryption key for {fw_ver}")
                return 1
        except Exception as e:
            self._dec_log(f"Error getting decryption key: {e}")
            return 1
        
        # Get file size
        length = os.path.getsize(encrypted)
        
        # Start decryption
        try:
            with open(encrypted, "rb") as inf, open(decrypted, "wb") as outf:
                success = self.decrypt_progress_GUI(inf, outf, key, length, progress_callback)
                return 0 if success else 1
        except Exception as e:
            self._dec_log(f"Decryption error: {e}")
            return 1

    def _on_manual_decrypt(self):
        """Handle the manual decrypt button click"""
        # Check if we're already decrypting
        if hasattr(self, '_decrypting') and self._decrypting:
            self._decrypting = False
            self.decrypt_btn.configure(text="Decrypt File")
            self._dec_log("Decryption cancelled by user")
            return
            
        # Validate fields
        enc_file = self.enc_file_var.get().strip()
        dec_file = self.dec_file_var.get().strip()
        firmware = self.dec_ver_var.get().strip()
        model = self.model_var.get().strip()
        csc = self.csc_var.get().strip().upper()
        imei = self.dec_imei_var.get().strip()
        serial = self.dec_serial_var.get().strip()
        enc_type = self.enc_type_var.get()
        
        missing = []
        if not enc_file: missing.append("Encrypted File")
        if not dec_file: missing.append("Output File")
        if not firmware: missing.append("Firmware Version")
        if not model: missing.append("Model")
        
        # For ENC4, we need CSC and either IMEI or Serial Number
        if enc_type == 4:
            if not csc: 
                missing.append("CSC")
            
            # Check if we have either IMEI or Serial Number
            has_imei = imei and imei.isdecimal() and len(imei) >= 8
            has_serial = serial and IMEIUtils.validate_serial_number(serial)
            
            if not has_imei and not has_serial:
                if not missing:  # Only show this error if there aren't other missing fields
                    messagebox.showerror("Error", "Either IMEI (≥8 digits) or Serial Number (1-35 alphanumeric) is required for ENC4")
                    return
                missing.append("IMEI or Serial Number")
            elif has_imei and has_serial:
                # If both are provided, ask user which to use
                result = messagebox.askyesnocancel(
                    "Device ID Selection", 
                    "Both IMEI and Serial Number are provided. Use IMEI? (No = use Serial Number, Cancel = abort)"
                )
                if result is None:  # Cancel
                    return
                elif result:  # Yes - use IMEI
                    serial = ""  # Clear serial to use IMEI
                else:  # No - use Serial Number
                    imei = ""  # Clear IMEI to use serial
            
            # Auto-fill IMEI if using IMEI
            if has_imei and not serial:
                if len(imei) < 15:
                    # Show warning and ask for confirmation
                    if not self._show_imei_warning(imei):
                        return  # User canceled
                        
                    filled_imei = self._fixup_imei(imei)
                    self.dec_imei_var.set(filled_imei)
                    # Also update the main IMEI
                    self.imei_var.set(filled_imei)
                    self._dec_log(f"Filled up IMEI to {filled_imei}")
                    imei = filled_imei
        
        # Determine device ID for decryption
        device_id = serial if serial else imei
        
        if missing:
            messagebox.showerror("Error", f"Required fields missing: {', '.join(missing)}")
            return
        
        # Check if input file exists
        if not os.path.exists(enc_file):
            messagebox.showerror("Error", f"Input file doesn't exist: {enc_file}")
            return
        
        # Make sure output directory exists
        out_dir = os.path.dirname(dec_file)
        if out_dir and not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except:
                messagebox.showerror("Error", f"Couldn't create output directory: {out_dir}")
                return
        
        # Start decryption
        self._decrypting = True
        self.decrypt_btn.configure(text="Cancel")
        
        # Clear log
        self.dec_log.configure(state="normal")
        self.dec_log.delete(1.0, tk.END)
        self.dec_log.configure(state="disabled")
        
        # Reset progress bar
        self.dec_progress["value"] = 0
        self.dec_status_var.set("Preparing to decrypt...")
        
        def decrypt_worker():
            try:
                self._dec_log(f"Decrypting {os.path.basename(enc_file)}")
                self._dec_log(f"Encryption type: ENC{enc_type}")
                self._dec_log(f"Firmware version: {firmware}")
                
                self.dec_status_var.set("Getting decryption key...")
                self.dec_progress["value"] = 10
                
                # Get file size for progress reporting
                file_size = os.path.getsize(enc_file)
                decrypt_start_time = time.time()
                
                def progress_callback(percent, bytes_processed, speed):
                    if not self._decrypting:
                        return False  # Cancel
                    
                    # Calculate progress (scale to 20-90%)
                    progress_value = 20 + (percent * 0.7)
                    
                    # Format speed for display
                    speed_str = self._format_size(speed) + "/s"
                    
                    # Estimate time remaining
                    if speed > 0:
                        bytes_remaining = file_size - bytes_processed
                        eta = bytes_remaining / speed
                        eta_str = f" • ETA: {self._format_time(eta)}"
                    else:
                        eta_str = ""
                    
                    # Create status message
                    status = f"Decrypting: {self._format_size(bytes_processed)}/{self._format_size(file_size)} • {speed_str}{eta_str}"
                    
                    # Update UI
                    self.dec_status_var.set(status)
                    self.dec_progress["value"] = progress_value
                    
                    # Process UI events to keep it responsive
                    self.update_idletasks()
                    
                    return True  # Continue
                
                # Call our GUI decrypt function
                result = self.decrypt_file_GUI(
                    enc_type, firmware, model, csc, device_id, 
                    enc_file, dec_file, progress_callback
                )
                
                if result == 0:
                    # Calculate and show final statistics
                    duration = time.time() - decrypt_start_time
                    avg_speed = file_size / duration if duration > 0 else 0
                    
                    self._dec_log(f"Successfully decrypted to: {dec_file}")
                    self._dec_log(f"Decryption completed in {self._format_time(duration)} at {self._format_size(avg_speed)}/s")
                    
                    self.dec_status_var.set(f"Completed ({self._format_size(avg_speed)}/s)")
                    self.dec_progress["value"] = 100
                else:
                    raise Exception("Decryption failed - check key parameters")
                
            except Exception as e:
                self._dec_log(f"Decryption error: {e}")
                self.dec_status_var.set(f"Error: {str(e)[:30]}...")
                messagebox.showerror("Decryption Error", str(e))
            finally:
                # Reset UI state
                self._decrypting = False
                self.decrypt_btn.configure(text="Decrypt File")
        
        # Start the decryption in a background thread
        threading.Thread(target=decrypt_worker, daemon=True).start()

    def _create_info_tab(self):
        # Info frame with padding
        info_frame = ttk.Frame(self.info_tab, padding=15)
        info_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_frame = ttk.Frame(info_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(title_frame, text="GetNewSamsungFirmware", 
                               font=('TkDefaultFont', 16, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        # Author & Project Link
        author_frame = ttk.Frame(info_frame)
        author_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(author_frame, text="By Keklick1337 (Vladislav Tislenko)").pack(anchor=tk.W)
        
        # GitHub link
        link_frame = ttk.Frame(info_frame)
        link_frame.pack(fill=tk.X, pady=5)
        
        link_text = "https://github.com/keklick1337/gnsf"
        link_label = ttk.Label(link_frame, text=link_text, foreground="blue", cursor="hand2")
        link_label.pack(anchor=tk.W)
        link_label.bind("<Button-1>", lambda e: webbrowser.open_new(link_text))
        
        # XDA Forums link 
        xda_frame = ttk.Frame(info_frame)
        xda_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(xda_frame, text="XDA Forums Discussion:").pack(anchor=tk.W)
        xda_link = "https://xdaforums.com/t/gnsf-get-new-samsung-firmware-software-cross-platform-open-source.4732816/"
        xda_label = ttk.Label(xda_frame, text=xda_link, foreground="blue", cursor="hand2")
        xda_label.pack(anchor=tk.W)
        xda_label.bind("<Button-1>", lambda e: webbrowser.open_new(xda_link))
        
        # Description
        desc_frame = ttk.LabelFrame(info_frame, text="About")
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=15)
        
        description = """
GetNewSamsungFirmware (GNSF) is a tool to download and decrypt Samsung firmware packages.

Key features:
• Download the latest firmware for any Samsung device model and region
• Automatically decrypt .enc2/.enc4 firmware files
• Resume interrupted downloads
• Check latest firmware versions across all regions
• Auto-fill IMEI numbers (with correct checksum) or use Serial Numbers
• Support for both IMEI and Serial Number device identification
• Parse firmware version strings for detailed information

This GUI provides an easy-to-use interface for the GNSF command line tool.
        """
        
        desc_text = scrolledtext.ScrolledText(desc_frame, wrap=tk.WORD, height=10)
        desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        desc_text.insert(tk.END, description)
        desc_text.configure(state="disabled")
        
        # Version info
        version_frame = ttk.Frame(info_frame)
        version_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(version_frame, text=f"Version: {VERSION}").pack(side=tk.LEFT)

    def _resize_columns(self, event):
        """Resize the treeview columns when the window is resized"""
        # Calculate the width available for columns
        width = event.width - 20  # Account for borders/scrollbars
        
        # Use stored proportions instead of weights
        for col, ratio in self._column_ratios.items():
            self.tree.column(col, width=int(width * ratio))

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _toggle_controls(self, enable):
        state = "normal" if enable else "disabled"
        self.model_entry.configure(state=state)
        self.csc_entry.configure(state=state)
        self.ver_entry.configure(state=state)
        self.imei_entry.configure(state=state)
        self.serial_entry.configure(state=state)
        self.outdir_entry.configure(state=state)
        self.decrypt_check.configure(state=state)
        self.browse_btn.configure(state=state)
        self.help_btn.configure(state=state)
        
        # Don't disable the download button - it's our cancel button
        # during downloads. Instead, manage its state separately.
        if not self._downloading:
            self.download_btn.configure(state=state)
        else:
            # During download, keep the button enabled
            self.download_btn.configure(state="normal")
        
        # If we're checking CSC, disable tree selection
        self.tree.configure(selectmode="browse" if not self._checking else "none")

    def _on_tab_change(self, event):
        """Handle tab changes and prevent switching during operations"""
        # Get the newly selected tab index
        new_tab = self.notebook.index("current")
        tab_name = self.notebook.tab(new_tab, "text")
        
        # If we're currently checking CSC versions, only allow staying on the Check tab
        if self._checking and tab_name != "Check CSC Versions":
            # Show warning and switch back to check tab
            messagebox.showwarning(
                "Operation in Progress",
                "Please stop the CSC check operation before switching tabs."
            )
            self.notebook.select(self.check_tab)
            return
        
        # If we're downloading, only allow staying on the Download tab
        if self._downloading and tab_name != "Download":
            messagebox.showwarning(
                "Operation in Progress",
                "Please cancel the download operation before switching tabs."
            )
            self.notebook.select(self.download_tab)
            return
        
        # If we're in manual decrypt tab and decrypting, prevent switching
        if hasattr(self, '_decrypting') and self._decrypting and tab_name != "Manual Decrypt":
            messagebox.showwarning(
                "Operation in Progress",
                "Please cancel the decryption operation before switching tabs."
            )
            self.notebook.select(self.decrypt_tab)
            return

    def _on_check(self):
        if self._checking:
            self._checking = False
            self.check_btn.configure(text="Check Versions")
            self._toggle_controls(True)
            self._log("Check cancelled by user")
            return
            
        mdl = self.model_var.get().strip()
        if not mdl:
            messagebox.showerror("Error", "Model is required")
            return
            
        self._checking = True
        self.check_btn.configure(text="Stop")
        self._toggle_controls(False)  # This will now also disable tree selection
        self.tree.delete(*self.tree.get_children())
        csc = self.csc_var.get().strip().upper()
        
        # Create a queue for thread-safe results
        results_queue = queue.Queue()
        
        def check_csc(code, name):
            if not self._checking:
                return
                
            try:
                ver = getlatestver(mdl, code)
                results_queue.put((code, name, ver, None))  # No error
            except Exception as e:
                results_queue.put((code, name, None, str(e)))  # With error
        
        def queue_processor():
            while self._checking:
                try:
                    # Process results from queue
                    result = results_queue.get(timeout=0.1)
                    if result:
                        code, name, ver, error = result
                        
                        if error:
                            self._log(f"[{code}] -> error: {error}")
                        else:
                            self._log(f"[{code}] -> {ver}")
                            self.tree.insert("", tk.END, values=(code, name, ver))
                        
                        # Update progress
                        count = len(self.tree.get_children())
                        progress = int((count / total) * 100)
                        self.check_status_var.set(f"Checked {count}/{total} regions")
                        self.check_progress["value"] = progress
                    
                    results_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    self._log(f"Error processing results: {e}")
            
        def worker():
            targets = {csc: CSC_DICT.get(csc, csc)} if csc else CSC_DICT
            nonlocal total
            total = len(targets)
            
            # Start queue processor thread
            processor_thread = threading.Thread(target=queue_processor, daemon=True)
            processor_thread.start()
            
            # Use thread pool for CSC checking
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all CSC check tasks
                futures = [executor.submit(check_csc, code, name) 
                          for code, name in targets.items()]
                
                # Wait for all tasks to complete or be cancelled
                for future in futures:
                    try:
                        future.result()
                    except Exception:
                        pass
            
            # Allow queue to process remaining results
            if self._checking:
                results_queue.join()
            
            # Reset UI state
            self._checking = False
            self.check_btn.configure(text="Check Versions")
            self._toggle_controls(True)
            self.check_status_var.set(f"Done: {len(self.tree.get_children())}/{total} regions checked")
        
        total = 0  # Define as nonlocal in worker
        self._check_thread = threading.Thread(target=worker, daemon=True)
        self._check_thread.start()

    def _on_select(self, evt):
        """Handle selection in the CSC versions tree"""
        # If we're checking, don't allow selection
        if self._checking:
            messagebox.showinfo("Operation in Progress", 
                               "Please stop the CSC check operation before selecting a version.")
            return
        
        sel = self.tree.selection()
        if not sel: 
            return
            
        code, name, ver = self.tree.item(sel[0], "values")
        self.csc_var.set(code)
        self.ver_var.set(ver)
        
        # Also update the manual decrypt tab's firmware version
        self.dec_ver_var.set(ver)
        
        # Switch to download tab
        self.notebook.select(self.download_tab)
        # This will trigger firmware info update via trace

    def _browse_out(self):
        d = filedialog.askdirectory(initialdir=self.outdir_var.get())
        if d:
            self.outdir_var.set(d)

    def _format_size(self, bytes):
        """Format bytes into human-readable form"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024
        return f"{bytes:.1f} TB"

    def _format_time(self, seconds):
        """Format seconds into human-readable form"""
        if seconds < 60:
            return f"{seconds:.0f} sec"
        elif seconds < 3600:
            return f"{seconds/60:.1f} min"
        else:
            return f"{seconds/3600:.1f} hrs"

    def _validate_imei(self, imei):
        """
        Basic validation for IMEI - must be at least 8 digits.
        Full validation and checksum generation happens during auto-fill.
        
        :param imei: IMEI string to validate
        :return: True if valid (at least 8 digits), False otherwise
        """
        if not imei or not re.match(r'^\d{8,15}$', imei):
            return False
        return True

    def _fixup_imei(self, imei):
        """
        Auto-fill IMEI to 15 digits with random numbers and add checksum.
        
        :param imei: Partial IMEI (at least 8 digits)
        :return: Complete 15-digit IMEI with valid checksum
        """
        import random
        from gnsf import IMEIUtils
        
        if not imei or not imei.isdecimal() or len(imei) < 8:
            # Needs at least 8 digits
            return imei
            
        if len(imei) >= 15:
            # Already at least 15 digits, return as is
            return imei[:15]
            
        if len(imei) == 14:
            # Exactly 14 digits, just add checksum
            return imei + str(IMEIUtils.luhn_checksum(imei))
            
        # Less than 14 digits, need to pad with random digits
        missing = 14 - len(imei)
        rnd = random.randint(0, 10**missing - 1)
        imei += f"%0{missing}d" % rnd
        
        # Add checksum digit as the 15th digit
        imei += str(IMEIUtils.luhn_checksum(imei))
        
        return imei

    def _get_unique_filename(self, base_path):
        """
        Generate a unique filename by appending (1), (2), etc. if the file exists.
        
        :param base_path: Base file path to check
        :return: Unique file path that doesn't exist
        """
        if not os.path.exists(base_path):
            return base_path
            
        directory, filename = os.path.split(base_path)
        name, ext = os.path.splitext(filename)
        
        counter = 1
        while True:
            new_path = os.path.join(directory, f"{name} ({counter}){ext}")
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def _get_default_downloads_dir(self):
        """Return the default downloads directory based on the platform"""
        DEFAULT_FOLDER = 'SamsungFirmware'
        try:
            return os.path.join(os.path.expanduser('~'), 'Downloads', DEFAULT_FOLDER)
        except Exception:
            # Fallback to current directory if we can't determine downloads dir
            return os.path.abspath('.')

    def _open_folder(self, path):
        """
        Open a folder in the system file explorer in a platform-independent way
        
        :param path: Path to the folder to open
        """
        try:
            system = platform.system()
            if system == "Windows":
                # Use subprocess for Windows to avoid os.startfile import issues
                subprocess.run(["explorer", path], check=False)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", path], check=False)
            else:  # Linux/Unix variants
                subprocess.run(["xdg-open", path], check=False)
            self._log(f"Opened folder: {path}")
        except Exception as e:
            self._log(f"Could not open folder: {e}")

    def _on_download(self):
        if self._downloading:
            self._downloading = False
            self.download_btn.configure(text="Download & Decrypt")
            self._toggle_controls(True)
            self._log("Download cancelled by user")
            return
            
        mdl = self.model_var.get().strip()
        csc = self.csc_var.get().strip().upper()
        ver = self.ver_var.get().strip()
        imei = self.imei_var.get().strip()
        serial = self.serial_var.get().strip()
        outdir = self.outdir_var.get().strip()
        
        # Validate all required fields
        missing = []
        if not mdl: missing.append("Model")
        if not csc: missing.append("CSC")
        if not ver: missing.append("Firmware Version")
        
        # Check if we have either IMEI or Serial Number
        has_imei = imei and imei.isdecimal() and len(imei) >= 8
        has_serial = serial and IMEIUtils.validate_serial_number(serial)
        
        if not has_imei and not has_serial:
            messagebox.showerror("Error", "Either IMEI (≥8 digits) or Serial Number (1-35 alphanumeric) is required")
            return
        elif has_imei and has_serial:
            # If both are provided, ask user which to use
            result = messagebox.askyesnocancel(
                "Device ID Selection", 
                "Both IMEI and Serial Number are provided. Use IMEI? (No = use Serial Number, Cancel = abort)"
            )
            if result is None:  # Cancel
                return
            elif result:  # Yes - use IMEI
                serial = ""  # Clear serial to use IMEI
            else:  # No - use Serial Number
                imei = ""  # Clear IMEI to use serial
        
        # Auto-fill IMEI if using IMEI
        if has_imei and not serial:
            if len(imei) < 15:
                # Show warning and ask for confirmation
                if not self._show_imei_warning(imei):
                    return  # User canceled
                    
                filled_imei = self._fixup_imei(imei)
                self.dec_imei_var.set(filled_imei)
                # Also update the main IMEI
                self.imei_var.set(filled_imei)
                self._log(f"Filled up IMEI to {filled_imei}")
                # Important: Update our local variable to use the filled IMEI
                imei = filled_imei  # This ensures the worker uses the complete IMEI
        
        # Determine device ID for download
        device_id = serial if serial else imei
        
        if missing:
            messagebox.showerror("Error", f"Required fields missing: {', '.join(missing)}")
            return
            
        self._downloading = True
        self.download_btn.configure(text="Cancel")
        self._toggle_controls(False)
        self.check_btn.configure(state="disabled")
        os.makedirs(outdir, exist_ok=True)
        
        # Show firmware info in log
        try:
            firmware_info = FirmwareUtils.format_firmware_info(ver)
            self._log(f"Firmware Information:\n{firmware_info}")
        except Exception as e:
            self._log(f"Could not parse firmware version: {ver}")
        
        # Store the final device ID in an instance variable to ensure it's accessible in the worker
        self._current_download_device_id = device_id
        
        def worker():
            try:
                # Use the stored device ID value
                current_device_id = self._current_download_device_id
                
                self._log("Initializing client...")
                self.dl_status_var.set("Initializing client...")
                self.dl_progress["value"] = 5
                client = FUSClient()
                
                self._log("Querying binary info...")
                self.dl_status_var.set("Querying binary info...")
                self.dl_progress["value"] = 10
                # Use the current_device_id variable instead of the closure-captured imei
                path, fname, size = getbinaryfile(client, ver, mdl, current_device_id, csc)
                
                fullpath = os.path.join(outdir, fname)
                decrypted_path = fullpath.rsplit(".", 1)[0] if fname.endswith((".enc2", ".enc4")) else None
                
                # Check if file already exists
                file_complete = False
                if os.path.exists(fullpath):
                    file_size = os.path.getsize(fullpath)
                    if file_size == size:
                        # File is complete, just need to decrypt
                        self._log(f"Download file already complete: {fname}")
                        file_complete = True
                        self.dl_progress["value"] = 50  # Skip to 50% progress
                        self.dl_status_var.set("File already downloaded")
                    else:
                        # Resume download from offset
                        offset = file_size
                        resuming = True
                        self._log(f"Resuming download from {self._format_size(offset)}")
                else:
                    offset = 0
                    resuming = False
                
                # Only download if file is not complete
                if not file_complete:
                    mode = "ab" if resuming else "wb"
                    
                    self._log(f"{'Resuming' if resuming else 'Downloading'} {fname}")
                    self.dl_status_var.set(f"{'Resuming' if resuming else 'Downloading'} {fname}")
                    self.dl_progress["value"] = 15
                    
                    initdownload(client, fname)
                    resp = client.downloadfile(path + fname, offset)
                    
                    # For download progress tracking
                    self._download_start_time = time.time()
                    speed_update_interval = 1.0  # Update speed every second
                    last_update = self._download_start_time
                    
                    with open(fullpath, mode) as f:
                        downloaded = offset
                        for chunk in resp.iter_content(0x10000):
                            if not self._downloading:
                                return
                            if not chunk: 
                                break
                                
                            f.write(chunk)
                            f.flush()
                            downloaded += len(chunk)
                            
                            # Calculate progress percentage
                            progress = int(50 + (downloaded / size) * 30)  # Scale to 50-80%
                            self.dl_progress["value"] = progress
                            
                            # Update speed and ETA every second
                            current_time = time.time()
                            if current_time - last_update >= speed_update_interval:
                                elapsed = current_time - self._download_start_time
                                speed = downloaded / elapsed if elapsed > 0 else 0
                                
                                # Calculate ETA
                                remaining_bytes = size - downloaded
                                eta = remaining_bytes / speed if speed > 0 else 0
                                
                                speed_str = self._format_size(speed) + "/s"
                                eta_str = self._format_time(eta)
                                
                                status = f"Downloading: {self._format_size(downloaded)}/{self._format_size(size)} • {speed_str} • ETA: {eta_str}"
                                self.dl_status_var.set(status)
                                last_update = current_time
                                
                            self.update_idletasks()
                    
                    self._log("Download complete")
                
                # auto‑decrypt
                if not self.nodecrypt_var.get() and fname.endswith((".enc2", ".enc4")):
                    # Base decrypted filename
                    dec_base = fullpath.rsplit(".", 1)[0]
                    
                    # Get a unique filename if the decrypted file already exists
                    dec = self._get_unique_filename(dec_base)
                    
                    try:
                        self._log("Decrypting...")
                        if dec != dec_base:
                            self._log(f"Decrypted file already exists, saving as {os.path.basename(dec)}")
                            
                        self.dl_status_var.set("Preparing to decrypt...")
                        self.dl_progress["value"] = 80
                        
                        # Check that both the source file exists and has content
                        if not os.path.exists(fullpath) or os.path.getsize(fullpath) == 0:
                            raise Exception(f"Source file {os.path.basename(fullpath)} is missing or empty")
                            
                        # Ensure the output directory exists
                        os.makedirs(os.path.dirname(dec), exist_ok=True)
                        
                        # Create decrypt progress callback
                        decrypt_start_time = time.time()
                        file_size = os.path.getsize(fullpath)
                        enc_ver = 2 if fname.endswith(".enc2") else 4
                        
                        def dl_decrypt_progress_callback(percent, bytes_processed, speed):
                            if not self._downloading:
                                return False  # Cancel

                            # Calculate progress (scale to 80-95%)
                            progress_value = 80 + (percent * 0.15)
                            
                            # Format speed for display
                            speed_str = self._format_size(speed) + "/s"
                            
                            # Create status message
                            status = f"Decrypting: {self._format_size(bytes_processed)}/{self._format_size(file_size)} • {speed_str}"
                            
                            # Update UI
                            self.dl_status_var.set(status)
                            self.dl_progress["value"] = progress_value
                            
                            # Process UI events to keep it responsive
                            self.update_idletasks()
                            
                            return True  # Continue
                        
                        # Call our GUI decrypt function
                        result = self.decrypt_file_GUI(
                            enc_ver, ver, mdl, csc, current_device_id, 
                            fullpath, dec, dl_decrypt_progress_callback
                        )
                        
                        if result == 0 and os.path.exists(dec) and os.path.getsize(dec) > 0:
                            self._log(f"Decrypted to {dec}")
                            # Include final statistics
                            decryption_time = time.time() - decrypt_start_time
                            avg_speed = file_size / decryption_time if decryption_time > 0 else 0
                            self.dl_status_var.set(f"Decrypted ({self._format_size(avg_speed)}/s)")
                            self.dl_progress["value"] = 95
                            os.remove(fullpath)
                        else:
                            raise Exception("Decryption failed or produced empty file")
                            
                    except Exception as e:
                        self._log(f"Decryption error: {e}")
                        self.dl_status_var.set(f"Decryption failed: {str(e)[:30]}...")
                        messagebox.showerror("Decryption Error", str(e))
                
                self._log("Opening folder...")
                self.dl_status_var.set("Complete - Opening folder")
                self.dl_progress["value"] = 100
                self._open_folder(outdir)  # Use our platform-specific method
                
            except Exception as e:
                self._log(f"Error: {e}")
                self.dl_status_var.set(f"Error: {str(e)[:30]}...")
                messagebox.showerror("Error", str(e))
            finally:
                # Reset UI state
                self._downloading = False
                self.download_btn.configure(text="Download & Decrypt")
                self._toggle_controls(True)
                self.check_btn.configure(state="normal")
                
        self._download_thread = threading.Thread(target=worker, daemon=True)
        self._download_thread.start()

    def _update_firmware_info(self, *args):
        """Update firmware information when version changes"""
        try:
            ver = self.ver_var.get().strip()
            
            # Clear existing text
            self.fw_info_text.configure(state="normal")
            self.fw_info_text.delete(1.0, tk.END)
            
            if not ver:
                self.fw_info_text.insert(tk.END, "Enter a firmware version to see information")
                self.fw_info_text.configure(state="disabled")
                return
                
            # Try to parse and format firmware info
            try:
                info = FirmwareUtils.format_firmware_info(ver)
                self.fw_info_text.insert(tk.END, info)
            except Exception as e:
                self.fw_info_text.insert(tk.END, f"Could not parse firmware version: {ver}\n{str(e)}")
                
        except Exception as e:
            self.fw_info_text.insert(tk.END, f"Error: {str(e)}")
            
        finally:
            self.fw_info_text.configure(state="disabled")

    def _show_imei_warning(self, partial_imei):
        """
        Show a warning when user enters a partial IMEI that will be auto-generated
        
        :param partial_imei: The partial IMEI entered by user
        :return: True if user wants to continue with auto-generation, False to cancel
        """
        message = (
            f"You've entered an incomplete IMEI ({partial_imei}).\n\n"
            "The missing part of the IMEI will be automatically generated, "
            "but this doesn't guarantee the correctness of the IMEI for firmware download "
            "and may cause issues.\n\n"
            "It's recommended to specify the complete 15-digit IMEI of your device.\n\n"
            "Continue with the automatically generated IMEI?"
        )
        return messagebox.askyesno("IMEI Warning", message)

if __name__ == "__main__":
    app = GNSFGUI()
    app.mainloop()