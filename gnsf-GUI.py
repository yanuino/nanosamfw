#!/usr/bin/env python3
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import subprocess
import time
import webbrowser
import re

from gnsf import (CSC_DICT, getlatestver, FUSClient, getbinaryfile, 
                 initdownload, decrypt_file, VERSION, FirmwareUtils, 
                 normalizevercode)

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
        self._create_widgets()

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
        self.info_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.download_tab, text="Download")
        self.notebook.add(self.check_tab, text="Check CSC Versions")
        self.notebook.add(self.info_tab, text="Info")
        
        # Setup Download Tab
        self._create_download_tab()
        
        # Setup Check CSC Tab
        self._create_check_tab()
        
        # Setup Info Tab
        self._create_info_tab()

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

        ttk.Label(frm2, text="IMEI (≥8 digits):*").grid(row=0, column=3, sticky=tk.W, padx=(10,0))
        self.imei_var = tk.StringVar()
        self.imei_entry = ttk.Entry(frm2, textvariable=self.imei_var, width=20)
        self.imei_entry.grid(row=0, column=4)

        ttk.Label(frm2, text="Out Dir:").grid(row=1, column=0, sticky=tk.W, pady=(5,0))
        
        # Get platform-specific default download directory
        default_downloads = self._get_default_downloads_dir()
        self.outdir_var = tk.StringVar(value=default_downloads)
        self.outdir_entry = ttk.Entry(frm2, textvariable=self.outdir_var, width=40)
        self.outdir_entry.grid(row=1, column=1, columnspan=3, sticky=tk.W+tk.E)
        
        self.browse_btn = ttk.Button(frm2, text="Browse", command=self._browse_out)
        self.browse_btn.grid(row=1, column=4, sticky=tk.W)

        self.nodecrypt_var = tk.BooleanVar(value=False)
        self.decrypt_check = ttk.Checkbutton(frm2, text="Skip Decrypt", variable=self.nodecrypt_var)
        self.decrypt_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5,0))
        
        ttk.Label(frm2, text="* Required fields").grid(row=2, column=1, columnspan=2, sticky=tk.E, pady=(5,0))

        self.download_btn = ttk.Button(frm2, text="Download & Decrypt", command=self._on_download)
        self.download_btn.grid(row=2, column=4, sticky=tk.E, pady=(5,0))
        
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

    def _update_firmware_info(self, *args):
        """Update firmware information when version is entered"""
        fw_version = self.ver_var.get().strip()
        
        self.fw_info_text.config(state="normal")
        self.fw_info_text.delete(1.0, tk.END)
        
        if fw_version:
            try:
                info = FirmwareUtils.format_firmware_info(fw_version)
                self.fw_info_text.insert(tk.END, info)
            except Exception as e:
                self.fw_info_text.insert(tk.END, f"Could not parse firmware version: {fw_version}")
        else:
            self.fw_info_text.insert(tk.END, "Enter a firmware version to see information")
            
        self.fw_info_text.config(state="disabled")

    def _get_default_downloads_dir(self):
        """Get the default Downloads directory based on operating system"""
        home = os.path.expanduser("~")

        return os.path.join(home, "Downloads", "SamsungFirmware")

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
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        
        # Grid layout for table and scrollbars
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        # Configure grid weights for resizing
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
    
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
• Auto-fill IMEI numbers (with correct checksum)
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
        self.outdir_entry.configure(state=state)
        self.decrypt_check.configure(state=state)
        self.download_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.help_btn.configure(state=state)

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
        self._toggle_controls(False)
        self.tree.delete(*self.tree.get_children())
        csc = self.csc_var.get().strip().upper()
        
        def worker():
            targets = {csc: CSC_DICT.get(csc, csc)} if csc else CSC_DICT
            total = len(targets)
            count = 0
            
            for code, name in targets.items():
                if not self._checking:
                    break
                    
                try:
                    # Update progress
                    count += 1
                    progress = int((count / total) * 100)
                    self.check_status_var.set(f"Checking {code} ({count}/{total})")
                    self.check_progress["value"] = progress
                    
                    ver = getlatestver(mdl, code)
                    self._log(f"[{code}] -> {ver}")
                    self.tree.insert("", tk.END, values=(code, name, ver))
                except Exception as e:
                    self._log(f"[{code}] -> error: {e}")
                    
                self.update_idletasks()
            
            # Reset UI state
            self._checking = False
            self.check_btn.configure(text="Check Versions")
            self._toggle_controls(True)
            self.check_status_var.set(f"Done: {count} regions checked")
            
        self._check_thread = threading.Thread(target=worker, daemon=True)
        self._check_thread.start()

    def _on_select(self, evt):
        sel = self.tree.selection()
        if not sel: return
        code, name, ver = self.tree.item(sel[0], "values")
        self.csc_var.set(code)
        self.ver_var.set(ver)
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
        """Validate IMEI has at least 8 digits"""
        if not imei or not re.match(r'^\d{8,15}$', imei):
            return False
        return True

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
        outdir = self.outdir_var.get().strip()
        
        # Validate all required fields
        missing = []
        if not mdl: missing.append("Model")
        if not csc: missing.append("CSC")
        if not ver: missing.append("Firmware Version")
        
        # Enhanced IMEI validation
        if not self._validate_imei(imei):
            messagebox.showerror("Error", "IMEI must contain at least 8 digits")
            return
        
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
        
        def worker():
            try:
                self._log("Initializing client...")
                self.dl_status_var.set("Initializing client...")
                self.dl_progress["value"] = 5
                client = FUSClient()
                
                self._log("Querying binary info...")
                self.dl_status_var.set("Querying binary info...")
                self.dl_progress["value"] = 10
                path, fname, size = getbinaryfile(client, ver, mdl, imei, csc)
                
                fullpath = os.path.join(outdir, fname)
                offset = os.path.getsize(fullpath) if os.path.exists(fullpath) else 0
                mode = "ab" if offset and offset < size else "wb"
                
                resuming = offset > 0 and offset < size
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
                
                # Decrypt if needed
                if not self.nodecrypt_var.get() and fname.endswith((".enc2", ".enc4")):
                    dec = fullpath.rsplit(".",1)[0]
                    self._log("Decrypting...")
                    self.dl_status_var.set("Decrypting...")
                    self.dl_progress["value"] = 80
                    
                    args = type("A", (), {})()
                    args.dev_model, args.dev_region, args.dev_imei, args.fw_ver = mdl, csc, imei, ver
                    decrypt_file(args, 2 if fname.endswith(".enc2") else 4, fullpath, dec)
                    
                    self._log(f"Decrypted to {dec}")
                    self.dl_status_var.set(f"Decrypted to {os.path.basename(dec)}")
                    self.dl_progress["value"] = 95
                    os.remove(fullpath)
                
                self._log("Opening folder...")
                self.dl_status_var.set("Complete - Opening folder")
                self.dl_progress["value"] = 100
                subprocess.run(["open", outdir], check=False)
                
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

if __name__ == "__main__":
    app = GNSFGUI()
    app.mainloop()