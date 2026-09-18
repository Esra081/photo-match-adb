import os
import re
import shutil
import subprocess
import tempfile
import threading
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk


# ============================================================
#  Phone Photo Backup Pro
#  Gerekenler:
#    pip install customtkinter pillow
#  ADB:
#    Put adb_tools/adb.exe next to this file or add adb to PATH.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
EMBEDDED_ADB = BASE_DIR / "adb_tools" / "adb.exe"
ADB_PATH = str(EMBEDDED_ADB) if EMBEDDED_ADB.exists() else "adb"

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".dng")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".3gp", ".3gpp", ".avi", ".m4v", ".webm", ".mts", ".m2ts", ".ts")
MEDIA_EXTS = IMAGE_EXTS + VIDEO_EXTS

MAX_THUMBNAILS_PER_BATCH = 120
THUMB_SIZE = (118, 118)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG = "#0B0F16"
PANEL = "#141922"
PANEL_2 = "#1D2430"
PANEL_3 = "#222A37"
BORDER = "#303846"
TEXT = "#F4F7FB"
MUTED = "#9AA6B2"
ACCENT = "#FF4D9D"
ACCENT_2 = "#D93682"
DANGER = "#F04444"
OK = "#22C55E"

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUB = ("Segoe UI", 13, "bold")
FONT_TEXT = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)


def button_style(kind: str = "secondary") -> dict:
    base = {
        "corner_radius": 8,
        "font": FONT_SUB,
        "text_color": TEXT,
    }
    if kind == "primary":
        return {
            **base,
            "fg_color": BG,
            "hover_color": PANEL_2,
            "border_width": 2,
            "border_color": ACCENT,
        }
    if kind == "danger":
        return {
            **base,
            "fg_color": BG,
            "hover_color": PANEL_2,
            "border_width": 2,
            "border_color": DANGER,
            "text_color": "#FFD6D6",
        }
    return {
        **base,
        "fg_color": PANEL_2,
        "hover_color": PANEL_3,
        "border_width": 1,
        "border_color": BORDER,
    }


@dataclass
class MediaItem:
    remote_path: str
    rel_path: str
    file_name: str
    folder: str
    size: int | None
    kind: str
    exists_locally: bool = False


def creation_flags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def shell_quote(path: str) -> str:
    # Safely pass paths with spaces or parentheses to adb shell.
    return "'" + path.replace("'", "'\"'\"'") + "'"


class PhoneBackupPro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PhotoMatch | Android -> Disk Backup")
        self.geometry("1220x760")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)

        self.source_path = ctk.StringVar(value="/sdcard")
        self.target_path = ctk.StringVar(value="")
        self.search_text = ctk.StringVar(value="")
        today = datetime.now()
        self.cleanup_year = ctk.StringVar(value=str(today.year))
        self.cleanup_month = ctk.StringVar(value=f"{today.month:02d}")
        self.cleanup_day = ctk.StringVar(value=f"{today.day:02d}")

        self.media_items: list[MediaItem] = []
        self.filtered_items: list[MediaItem] = []
        self.sync_plan: dict[str, list[MediaItem]] = {}
        self.folder_vars: dict[str, ctk.BooleanVar] = {}
        self.phone_cleanup_candidates: list[MediaItem] = []
        self.disk_index_cache: dict[str, set[str]] | None = None
        self.disk_index_target = ""

        self.thumb_refs: dict[str, ImageTk.PhotoImage] = {}
        self.thumb_cache: dict[str, Path] = {}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="photomatch_preview_"))

        self.is_busy = False
        self.active_operation = ""
        self.active_operation_is_risky = False
        self.stop_requested = False
        self.gallery_offset = 0
        self.preview_photo_ref = None

        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI ----------------

    def build_ui(self):
        header = ctk.CTkFrame(self, fg_color=BG)
        header.pack(fill="x", padx=18, pady=(14, 8))

        ctk.CTkLabel(
            header,
            text="PhotoMatch Backup",
            font=("Segoe UI", 26, "bold"),
            text_color=TEXT,
        ).pack(side="left")

        self.status_badge = ctk.CTkLabel(
            header,
            text="Ready",
            font=FONT_SUB,
            text_color=TEXT,
            fg_color=PANEL_2,
            corner_radius=8,
            padx=14,
            pady=8,
        )
        self.status_badge.pack(side="right")

        self.tabs = ctk.CTkTabview(
            self,
            fg_color=PANEL,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_2,
            segmented_button_unselected_color=PANEL_2,
            segmented_button_unselected_hover_color=PANEL_3,
        )
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.tab_analyze = self.tabs.add("1  Scan & Gallery")
        self.tab_backup = self.tabs.add("2  Backup")
        self.tab_clean = self.tabs.add("3  Duplicate Cleanup")
        self.tab_phone_clean = self.tabs.add("4  Phone Cleanup")

        self.build_analyze_tab()
        self.build_backup_tab()
        self.build_clean_tab()
        self.build_phone_cleanup_tab()

    def build_analyze_tab(self):
        top = ctk.CTkFrame(self.tab_analyze, fg_color=PANEL)
        top.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(top, text="Phone folder", font=FONT_SUB, text_color=ACCENT).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self.entry_source = ctk.CTkEntry(top, textvariable=self.source_path, width=360, fg_color=BG, text_color=TEXT)
        self.entry_source.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        ctk.CTkLabel(top, text="Backup folder on disk", font=FONT_SUB, text_color=ACCENT).grid(row=0, column=1, sticky="w", padx=8, pady=(8, 4))
        self.entry_target = ctk.CTkEntry(top, textvariable=self.target_path, width=420, fg_color=BG, text_color=TEXT)
        self.entry_target.grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))

        ctk.CTkButton(top, text="Choose Disk", width=110, command=self.select_target, **button_style("secondary")).grid(row=1, column=2, padx=8, pady=(0, 8))
        ctk.CTkButton(top, text="Test Device", width=110, command=self.test_device, **button_style("secondary")).grid(row=1, column=3, padx=8, pady=(0, 8))
        self.btn_scan = ctk.CTkButton(top, text="Scan & Show Gallery", width=210, command=self.trigger_scan, **button_style("primary"))
        self.btn_scan.grid(row=1, column=4, padx=8, pady=(0, 8))

        top.grid_columnconfigure(1, weight=1)

        body = ctk.CTkFrame(self.tab_analyze, fg_color=PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        left_header = ctk.CTkFrame(body, fg_color=PANEL)
        left_header.grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=(8, 4))
        ctk.CTkLabel(left_header, text="Folders to Back Up", font=FONT_TITLE, text_color=TEXT).pack(anchor="w")

        self.folder_scroll = ctk.CTkScrollableFrame(body, width=340, fg_color=BG, corner_radius=8)
        self.folder_scroll.grid(row=1, column=0, sticky="nsw", padx=(8, 6), pady=(0, 8))

        right_header = ctk.CTkFrame(body, fg_color=PANEL)
        right_header.grid(row=0, column=1, sticky="ew", padx=(6, 8), pady=(8, 4))
        right_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(right_header, text="Phone Gallery Preview", font=FONT_TITLE, text_color=TEXT).grid(row=0, column=0, sticky="w")
        self.entry_search = ctk.CTkEntry(right_header, textvariable=self.search_text, placeholder_text="Search: DCIM, WhatsApp, IMG_...", width=260, fg_color=BG)
        self.entry_search.grid(row=0, column=1, sticky="e", padx=8)
        self.entry_search.bind("<KeyRelease>", lambda _e: self.apply_filter())
        ctk.CTkButton(right_header, text="Filter", width=80, command=self.apply_filter, **button_style("secondary")).grid(row=0, column=2, sticky="e")

        self.summary_label = ctk.CTkLabel(
            right_header,
            text="After scanning, photos and videos from your phone appear here.",
            font=FONT_TEXT,
            text_color=MUTED,
        )
        self.summary_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.scan_progress = ctk.CTkProgressBar(right_header, height=10, fg_color=BG, progress_color=ACCENT)
        self.scan_progress.set(0)
        self.scan_progress.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        self.stats_frame = ctk.CTkFrame(right_header, fg_color=PANEL)
        self.stats_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        for i in range(3):
            self.stats_frame.grid_columnconfigure(i, weight=1)
        self.new_count_label = self.create_stat_tile(self.stats_frame, "New", "0", OK, 0)
        self.existing_count_label = self.create_stat_tile(self.stats_frame, "Already on Disk", "0", MUTED, 1)
        self.total_count_label = self.create_stat_tile(self.stats_frame, "Total Media", "0", ACCENT, 2)

        self.gallery_scroll = ctk.CTkScrollableFrame(body, fg_color=BG, corner_radius=8)
        self.gallery_scroll.grid(row=1, column=1, sticky="nsew", padx=(6, 8), pady=(0, 8))

        self.preview_panel = ctk.CTkFrame(body, fg_color=BG, corner_radius=8, height=120)
        self.preview_panel.grid(row=2, column=1, sticky="ew", padx=(6, 8), pady=(0, 8))
        self.preview_panel.grid_propagate(False)
        self.preview_panel.grid_columnconfigure(1, weight=1)
        self.preview_image_label = ctk.CTkLabel(self.preview_panel, text="Select a photo name to preview it here.", font=FONT_TEXT, text_color=MUTED, width=136, height=96, fg_color=PANEL_2, corner_radius=8)
        self.preview_image_label.grid(row=0, column=0, padx=10, pady=10)
        self.preview_meta_label = ctk.CTkLabel(self.preview_panel, text="No file selected", font=FONT_SUB, text_color=TEXT, anchor="w", justify="left")
        self.preview_meta_label.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)

        self.gallery_actions = ctk.CTkFrame(body, fg_color=PANEL)
        self.gallery_actions.grid(row=3, column=1, sticky="ew", padx=(6, 8), pady=(0, 8))

        self.btn_load_more = ctk.CTkButton(self.gallery_actions, text="Load More Previews", command=self.load_more_gallery, state="disabled", **button_style("secondary"))
        self.btn_load_more.pack(side="left")

        self.btn_go_backup = ctk.CTkButton(self.gallery_actions, text="Back Up Selected Folders", command=self.go_backup, state="disabled", **button_style("primary"))
        self.btn_go_backup.pack(side="right")

    def create_stat_tile(self, parent, title: str, value: str, color: str, column: int):
        tile = ctk.CTkFrame(parent, fg_color=BG, corner_radius=8)
        tile.grid(row=0, column=column, sticky="ew", padx=4)
        value_label = ctk.CTkLabel(tile, text=value, font=("Segoe UI", 24, "bold"), text_color=color)
        value_label.pack(anchor="w", padx=12, pady=(8, 0))
        ctk.CTkLabel(tile, text=title, font=FONT_SMALL, text_color=MUTED).pack(anchor="w", padx=12, pady=(0, 8))
        return value_label

    def build_backup_tab(self):
        wrap = ctk.CTkFrame(self.tab_backup, fg_color=PANEL)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        self.backup_info = ctk.CTkLabel(wrap, text="Scan your phone first in Scan & Gallery.", font=FONT_TITLE, text_color=MUTED)
        self.backup_info.pack(pady=(60, 20))

        self.progress = ctk.CTkProgressBar(wrap, width=760, height=14, fg_color=BG, progress_color=ACCENT)
        self.progress.set(0)
        self.progress.pack(pady=20)

        self.backup_status = ctk.CTkLabel(wrap, text="Backup engine is ready.", font=FONT_SUB, text_color=TEXT)
        self.backup_status.pack(pady=8)

        buttons = ctk.CTkFrame(wrap, fg_color=PANEL)
        buttons.pack(pady=35)

        self.btn_start_backup = ctk.CTkButton(buttons, text="Start Backup", width=250, height=44, command=self.trigger_backup, state="disabled", **button_style("primary"))
        self.btn_start_backup.pack(side="left", padx=12)

        self.btn_stop = ctk.CTkButton(buttons, text="Stop Safely", width=250, height=44, command=self.request_stop, state="disabled", **button_style("danger"))
        self.btn_stop.pack(side="left", padx=12)

    def build_clean_tab(self):
        wrap = ctk.CTkFrame(self.tab_clean, fg_color=PANEL)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            wrap,
            text="Duplicate cleanup finds files on the target disk with the same relative path and file size.",
            font=FONT_TITLE,
            text_color=TEXT,
        ).pack(pady=(60, 12))

        ctk.CTkLabel(
            wrap,
            text="Note: Deleting files is risky. The app asks for confirmation first, then removes duplicates directly.",
            font=FONT_TEXT,
            text_color=MUTED,
        ).pack(pady=(0, 25))

        self.clean_status = ctk.CTkLabel(wrap, text="Cleanup is ready.", font=FONT_SUB, text_color=MUTED)
        self.clean_status.pack(pady=12)

        self.clean_progress = ctk.CTkProgressBar(wrap, width=760, height=14, fg_color=BG, progress_color=ACCENT)
        self.clean_progress.set(0)
        self.clean_progress.pack(pady=18)

        self.btn_clean = ctk.CTkButton(wrap, text="Find & Delete Disk Duplicates", width=300, height=44, command=self.trigger_clean, **button_style("danger"))
        self.btn_clean.pack(pady=24)

    def build_phone_cleanup_tab(self):
        wrap = ctk.CTkFrame(self.tab_phone_clean, fg_color=PANEL)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            wrap,
            text="Delete Backed-Up Media From Phone",
            font=FONT_TITLE,
            text_color=TEXT,
        ).pack(anchor="w", padx=10, pady=(10, 6))

        ctk.CTkLabel(
            wrap,
            text="Only media that already exists in the selected disk backup will be eligible. Choose a cutoff date; files saved on or before that date can be deleted from the phone.",
            font=FONT_TEXT,
            text_color=MUTED,
            wraplength=980,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 16))

        controls = ctk.CTkFrame(wrap, fg_color=PANEL)
        controls.pack(fill="x", padx=10, pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(controls, text="Cutoff date", font=FONT_SUB, text_color=ACCENT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        date_picker = ctk.CTkFrame(controls, fg_color=PANEL)
        date_picker.grid(row=1, column=0, sticky="w", padx=(0, 12), pady=(4, 0))

        current_year = datetime.now().year
        year_values = [str(year) for year in range(current_year, current_year - 16, -1)]
        month_values = [f"{month:02d}" for month in range(1, 13)]
        day_values = [f"{day:02d}" for day in range(1, 32)]

        self.cleanup_year_menu = ctk.CTkOptionMenu(
            date_picker,
            values=year_values,
            variable=self.cleanup_year,
            width=92,
            fg_color=BG,
            button_color=PANEL_2,
            button_hover_color=ACCENT_2,
            command=lambda _value: self.update_cleanup_days(),
        )
        self.cleanup_year_menu.pack(side="left", padx=(0, 6))

        self.cleanup_month_menu = ctk.CTkOptionMenu(
            date_picker,
            values=month_values,
            variable=self.cleanup_month,
            width=74,
            fg_color=BG,
            button_color=PANEL_2,
            button_hover_color=ACCENT_2,
            command=lambda _value: self.update_cleanup_days(),
        )
        self.cleanup_month_menu.pack(side="left", padx=(0, 6))

        self.cleanup_day_menu = ctk.CTkOptionMenu(
            date_picker,
            values=day_values,
            variable=self.cleanup_day,
            width=74,
            fg_color=BG,
            button_color=PANEL_2,
            button_hover_color=ACCENT_2,
        )
        self.cleanup_day_menu.pack(side="left")
        self.update_cleanup_days()

        ctk.CTkLabel(controls, text="Phone folder and backup folder are taken from tab 1.", font=FONT_TEXT, text_color=MUTED).grid(row=1, column=1, sticky="w", pady=(4, 0))

        self.phone_cleanup_status = ctk.CTkLabel(wrap, text="Ready to check phone cleanup candidates.", font=FONT_SUB, text_color=MUTED)
        self.phone_cleanup_status.pack(anchor="w", padx=10, pady=(4, 8))

        self.phone_cleanup_progress = ctk.CTkProgressBar(wrap, width=760, height=14, fg_color=BG, progress_color=ACCENT)
        self.phone_cleanup_progress.set(0)
        self.phone_cleanup_progress.pack(anchor="w", padx=10, pady=(0, 14))

        self.phone_cleanup_list = ctk.CTkScrollableFrame(wrap, fg_color=BG, corner_radius=8, height=300)
        self.phone_cleanup_list.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        buttons = ctk.CTkFrame(wrap, fg_color=PANEL)
        buttons.pack(anchor="e", padx=10)

        self.btn_find_phone_cleanup = ctk.CTkButton(
            buttons,
            text="Find Deletable Files",
            width=220,
            height=42,
            command=self.trigger_phone_cleanup_scan,
            **button_style("primary"),
        )
        self.btn_find_phone_cleanup.pack(side="left", padx=(0, 10))

        self.btn_delete_phone_cleanup = ctk.CTkButton(
            buttons,
            text="Delete From Phone",
            width=220,
            height=42,
            command=self.trigger_phone_cleanup_delete,
            state="disabled",
            **button_style("danger"),
        )
        self.btn_delete_phone_cleanup.pack(side="left")

    # ---------------- Helpers ----------------

    def set_status(self, text, color=PANEL_2):
        self.status_badge.configure(text=text, fg_color=color)

    def lock_ui(self, operation: str = "operation", risky: bool = False):
        self.is_busy = True
        self.active_operation = operation
        self.active_operation_is_risky = risky
        self.btn_scan.configure(state="disabled")
        self.btn_start_backup.configure(state="disabled")
        self.btn_clean.configure(state="disabled")
        self.btn_go_backup.configure(state="disabled")
        self.btn_load_more.configure(state="disabled")
        self.btn_find_phone_cleanup.configure(state="disabled")
        self.btn_delete_phone_cleanup.configure(state="disabled")

    def unlock_ui(self):
        self.is_busy = False
        self.active_operation = ""
        self.active_operation_is_risky = False
        self.btn_scan.configure(state="normal")
        self.btn_clean.configure(state="normal")
        self.btn_find_phone_cleanup.configure(state="normal")
        if self.phone_cleanup_candidates:
            self.btn_delete_phone_cleanup.configure(state="normal")
        if self.media_items:
            self.btn_go_backup.configure(state="normal")
            self.btn_start_backup.configure(state="normal")
            if self.gallery_offset < len(self.filtered_items):
                self.btn_load_more.configure(state="normal")

    def run_adb(self, args, timeout=None, text=True):
        return subprocess.run(
            [ADB_PATH, *args],
            capture_output=True,
            text=text,
            encoding="utf-8" if text else None,
            errors="ignore" if text else None,
            timeout=timeout,
            creationflags=creation_flags(),
        )

    def select_target(self):
        path = filedialog.askdirectory(title="Choose backup folder")
        if path:
            self.target_path.set(path)
            self.disk_index_cache = None
            self.disk_index_target = ""

    def selected_cleanup_date_text(self) -> str:
        return f"{self.cleanup_year.get()}-{self.cleanup_month.get()}-{self.cleanup_day.get()}"

    def update_cleanup_days(self):
        try:
            year = int(self.cleanup_year.get())
            month = int(self.cleanup_month.get())
        except ValueError:
            return

        max_day = calendar.monthrange(year, month)[1]
        values = [f"{day:02d}" for day in range(1, max_day + 1)]
        current_day = self.cleanup_day.get()
        self.cleanup_day_menu.configure(values=values)
        if current_day not in values:
            self.cleanup_day.set(values[-1])

    def test_device(self):
        try:
            result = self.run_adb(["devices"], timeout=10)
            lines = [x.strip() for x in result.stdout.splitlines() if x.strip()]
            devices = [x for x in lines[1:] if "\tdevice" in x]
            if devices:
                messagebox.showinfo("Device Connected", f"ADB device is ready:\n{devices[0]}")
            else:
                messagebox.showwarning("Device Not Found", "Connect your phone with USB, enable USB debugging, and approve the permission prompt on the phone.")
        except FileNotFoundError:
            messagebox.showerror("ADB Missing", "adb_tools/adb.exe was not found and adb is not available in PATH.")
        except Exception as e:
            messagebox.showerror("ADB Error", str(e))

    def normalize_remote_path(self, remote_path: str, source: str) -> str:
        remote_path = remote_path.strip()
        source = source.rstrip("/")
        prefixes = [
            source + "/",
            source.replace("/sdcard", "/storage/emulated/0").rstrip("/") + "/",
            "/storage/emulated/0/",
            "/sdcard/",
        ]
        for prefix in prefixes:
            if remote_path.startswith(prefix):
                return remote_path[len(prefix):].lstrip("/")
        return remote_path.split("/")[-1]

    def local_index(self, target: str) -> dict[str, set[str]]:
        target_path = Path(target)
        index = {"names": set(), "paths": set()}
        if not target_path.exists():
            return index

        for root, _dirs, files in os.walk(target_path):
            for name in files:
                try:
                    full = Path(root) / name
                    rel = full.relative_to(target_path).as_posix().lower()
                    index["names"].add(name.lower())
                    index["paths"].add(rel)
                except OSError:
                    index["names"].add(name.lower())
        return index

    def cached_local_index(self, target: str) -> dict[str, set[str]]:
        normalized = str(Path(target).resolve()).lower()
        if self.disk_index_cache is not None and self.disk_index_target == normalized:
            return self.disk_index_cache

        index = self.local_index(target)
        self.disk_index_cache = index
        self.disk_index_target = normalized
        return index

    # ---------------- Scan ----------------

    def trigger_scan(self):
        if self.is_busy:
            return

        source = self.source_path.get().strip().rstrip("/")
        target = self.target_path.get().strip()

        if not source:
            messagebox.showwarning("Missing Information", "Phone folder cannot be empty. Example: /sdcard")
            return
        if not target:
            messagebox.showwarning("Missing Information", "Choose the disk folder for the backup first.")
            return

        self.clear_analysis_ui()
        self.lock_ui("phone scan", risky=False)
        self.set_status("Scanning...", ACCENT_2)
        self.btn_scan.configure(text="Scanning...")
        self.scan_progress.set(0.08)
        threading.Thread(target=self.scan_worker, args=(source, target), daemon=True).start()

    def clear_analysis_ui(self):
        for frame in (self.folder_scroll, self.gallery_scroll):
            for child in frame.winfo_children():
                child.destroy()
        self.media_items.clear()
        self.filtered_items.clear()
        self.sync_plan.clear()
        self.folder_vars.clear()
        self.thumb_refs.clear()
        self.thumb_cache.clear()
        self.gallery_offset = 0
        self.progress.set(0)
        self.scan_progress.set(0)
        self.summary_label.configure(text="Scanning phone...")
        self.new_count_label.configure(text="0")
        self.existing_count_label.configure(text="0")
        self.total_count_label.configure(text="0")
        self.preview_photo_ref = None
        self.preview_image_label.configure(image=None, text="Select a photo name to preview it here.")
        self.preview_meta_label.configure(text="No file selected")

    def scan_worker(self, source: str, target: str):
        try:
            self.after(0, lambda: (self.summary_label.configure(text="Indexing target disk..."), self.scan_progress.set(0.22)))
            existing = self.cached_local_index(target)

            self.after(0, lambda: (self.summary_label.configure(text="Finding media files on the phone..."), self.scan_progress.set(0.55)))
            items = self.get_phone_media(source, existing)

            if not items:
                self.after(0, lambda: self.scan_failed("No photos or videos were found under this phone folder. Try /sdcard as the source path."))
                return

            plan: dict[str, list[MediaItem]] = {}
            for item in items:
                if not item.exists_locally:
                    plan.setdefault(item.folder, []).append(item)

            self.after(0, lambda: self.scan_progress.set(0.82))
            self.after(0, lambda: self.scan_finished(items, plan))
        except FileNotFoundError:
            self.after(0, lambda: self.scan_failed("ADB was not found. Put adb_tools/adb.exe next to this app or add adb to PATH."))
        except Exception as e:
            self.after(0, lambda: self.scan_failed(f"Scan error:\n{e}"))

    def get_phone_media(self, source: str, existing: dict[str, set[str]]) -> list[MediaItem]:
        # Try MediaStore first. It is faster on some Android versions.
        rows = self.query_mediastore(source)
        if not rows:
            # Fall back to find if MediaStore has no permission/data.
            rows = self.query_find(source)

        seen = set()
        items: list[MediaItem] = []

        for remote_path, size in rows:
            lower = remote_path.lower()
            if lower in seen or not lower.endswith(MEDIA_EXTS):
                continue
            seen.add(lower)

            rel = self.normalize_remote_path(remote_path, source)
            name = remote_path.split("/")[-1]
            folder = os.path.dirname(rel).replace("\\", "/") or "Root"
            kind = "image" if lower.endswith(IMAGE_EXTS) else "video"

            if kind == "video":
                exists = rel.lower() in existing["paths"]
            else:
                exists = rel.lower() in existing["paths"] or name.lower() in existing["names"]

            items.append(MediaItem(
                remote_path=remote_path,
                rel_path=rel,
                file_name=name,
                folder=folder,
                size=size,
                kind=kind,
                exists_locally=exists,
            ))

        items.sort(key=lambda x: (x.folder.lower(), x.file_name.lower()))
        return items

    def query_mediastore(self, source: str) -> list[tuple[str, int | None]]:
        projection = "_data"
        cmd = ["shell", "content", "query", "--uri", "content://media/external/file", "--projection", projection]
        result = self.run_adb(cmd, timeout=45)
        if result.returncode != 0 or not result.stdout.strip():
            return []

        search_filter = source.replace("/sdcard", "/storage/emulated/0").rstrip("/")
        rows: list[tuple[str, int | None]] = []

        for line in result.stdout.splitlines():
            if "_data=" not in line:
                continue
            path = line.split("_data=")[-1].strip()
            if not path.startswith(search_filter):
                continue
            rows.append((path, None))

        return rows

    def query_find(self, source: str) -> list[tuple[str, int | None]]:
        # Keep line-based output because it is easier to parse on Windows.
        patterns = " -o ".join([f"-iname '*{ext}'" for ext in MEDIA_EXTS])
        cmd = f"find {shell_quote(source)} -type f \\( {patterns} \\) 2>/dev/null"
        result = self.run_adb(["shell", cmd], timeout=75)
        if result.returncode != 0 and not result.stdout.strip():
            return []
        return [(line.strip(), None) for line in result.stdout.splitlines() if line.strip()]

    def scan_finished(self, items: list[MediaItem], plan: dict[str, list[MediaItem]]):
        self.media_items = items
        self.sync_plan = plan
        self.filtered_items = list(items)
        self.render_folder_list()
        self.render_gallery(reset=True)

        total = len(items)
        images = sum(1 for x in items if x.kind == "image")
        videos = total - images
        new_files = sum(1 for x in items if not x.exists_locally)
        existing = total - new_files

        self.new_count_label.configure(text=str(new_files))
        self.existing_count_label.configure(text=str(existing))
        self.total_count_label.configure(text=str(total))
        self.summary_label.configure(
            text=f"Found {images} photos and {videos} videos on the phone."
        )
        self.scan_progress.set(1)
        self.backup_info.configure(text=f"Ready to back up: {new_files} new files can be selected.", text_color=TEXT)
        self.btn_scan.configure(text="Scan Again")
        self.set_status("Scan complete", OK)
        self.unlock_ui()

    def scan_failed(self, message: str):
        self.btn_scan.configure(text="Scan & Show Gallery")
        self.scan_progress.set(0)
        self.set_status("Error", DANGER)
        self.unlock_ui()
        messagebox.showerror("Scan Error", message)

    # ---------------- Render folders & gallery ----------------

    def render_folder_list(self):
        for child in self.folder_scroll.winfo_children():
            child.destroy()

        if not self.sync_plan:
            ctk.CTkLabel(
                self.folder_scroll,
                text="No new files found.\nThe gallery is still available on the right.",
                font=FONT_TEXT,
                text_color=MUTED,
                justify="left",
            ).pack(anchor="w", padx=12, pady=12)
            return

        for folder, files in sorted(self.sync_plan.items(), key=lambda x: x[0].lower()):
            var = ctk.BooleanVar(value=True)
            self.folder_vars[folder] = var

            row = ctk.CTkFrame(self.folder_scroll, fg_color=PANEL_2, corner_radius=8)
            row.pack(fill="x", padx=8, pady=5)
            row.grid_columnconfigure(1, weight=1)

            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                font=FONT_TEXT,
                text_color=TEXT,
                hover_color=ACCENT,
                fg_color=ACCENT,
                width=28,
            )
            cb.grid(row=0, column=0, rowspan=2, padx=(10, 4), pady=10)

            folder_button = ctk.CTkButton(
                row,
                text=self.truncate_middle(folder, 34),
                fg_color="transparent",
                hover_color=ACCENT_2,
                text_color=TEXT,
                anchor="w",
                font=FONT_TEXT,
                command=lambda f=folder: self.filter_folder(f),
            )
            folder_button.grid(row=0, column=1, sticky="ew", padx=(2, 10), pady=(8, 0))

            ctk.CTkLabel(
                row,
                text=f"{len(files)} new files",
                font=("Segoe UI", 18, "bold"),
                text_color=OK,
            ).grid(row=1, column=1, sticky="w", padx=(8, 10), pady=(0, 8))

    def truncate_middle(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        keep = max_len - 3
        left = max(keep // 2, 1)
        right = max(keep - left, 1)
        return f"{text[:left]}...{text[-right:]}"

    def apply_filter(self):
        q = self.search_text.get().strip().lower()
        if not q:
            self.filtered_items = list(self.media_items)
        else:
            self.filtered_items = [
                item for item in self.media_items
                if q in item.file_name.lower() or q in item.folder.lower() or q in item.rel_path.lower()
            ]
        self.render_gallery(reset=True)

    def filter_folder(self, folder: str):
        self.search_text.set(folder)
        self.apply_filter()

    def render_gallery(self, reset=False):
        if reset:
            for child in self.gallery_scroll.winfo_children():
                child.destroy()
            self.gallery_offset = 0
            self.thumb_refs.clear()

        if not self.filtered_items:
            ctk.CTkLabel(self.gallery_scroll, text="No files match this filter.", text_color=MUTED, font=FONT_TEXT).pack(pady=20)
            self.btn_load_more.configure(state="disabled")
            return

        start = self.gallery_offset
        end = min(start + MAX_THUMBNAILS_PER_BATCH, len(self.filtered_items))
        batch = self.filtered_items[start:end]

        columns = 5
        for i in range(columns):
            self.gallery_scroll.grid_columnconfigure(i, weight=1)

        for idx, item in enumerate(batch, start=start):
            r = idx // columns
            c = idx % columns
            self.create_media_card(item, r, c)

        self.gallery_offset = end
        if self.gallery_offset < len(self.filtered_items) and not self.is_busy:
            self.btn_load_more.configure(state="normal")
        else:
            self.btn_load_more.configure(state="disabled")

        # Load thumbnails in the background so the interface stays responsive.
        threading.Thread(target=self.load_thumbnails_worker, args=(batch,), daemon=True).start()

    def load_more_gallery(self):
        self.render_gallery(reset=False)

    def create_media_card(self, item: MediaItem, row: int, col: int):
        card = ctk.CTkFrame(self.gallery_scroll, fg_color=PANEL_2, corner_radius=8, width=150, height=178)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="n")
        card.grid_propagate(False)

        preview = ctk.CTkLabel(card, text="VIDEO" if item.kind == "video" else "PHOTO", font=FONT_SUB, text_color=MUTED, width=126, height=112, fg_color=BG, corner_radius=8)
        preview.pack(padx=8, pady=(8, 5))
        preview.remote_path = item.remote_path  # dynamic reference
        preview.bind("<Button-1>", lambda _e, it=item: self.select_media_item(it))

        name = self.truncate_middle(item.file_name, 24)
        name_button = ctk.CTkButton(
            card,
            text=name,
            height=24,
            fg_color="transparent",
            hover_color=BG,
            text_color=TEXT,
            font=FONT_SMALL,
            command=lambda it=item: self.select_media_item(it),
        )
        name_button.pack(fill="x", padx=6)

        state = "On Disk" if item.exists_locally else "New"
        state_color = MUTED if item.exists_locally else OK
        ctk.CTkLabel(card, text=f"{state} | {self.truncate_middle(item.folder, 18)}", font=FONT_SMALL, text_color=state_color).pack(padx=6, pady=(0, 6))

        item._preview_widget = preview  # Practical reference to the tkinter widget.

    def select_media_item(self, item: MediaItem):
        state = "Already on disk" if item.exists_locally else "New file"
        size_text = f"{item.size:,} bytes" if item.size else "Size unavailable"
        self.preview_meta_label.configure(
            text=f"{item.file_name}\n{item.folder}\n{state} | {size_text}",
            text_color=TEXT,
        )

        if item.kind != "image":
            self.preview_photo_ref = None
            self.preview_image_label.configure(image=None, text="Video preview is not available here.")
            return

        self.preview_image_label.configure(image=None, text="Loading preview...")
        threading.Thread(target=self.load_inline_preview_worker, args=(item,), daemon=True).start()

    def load_inline_preview_worker(self, item: MediaItem):
        try:
            local = self.ensure_preview_file(item)
            if not local:
                raise RuntimeError("The photo could not be pulled from the phone.")

            image = Image.open(local)
            image.thumbnail((180, 96))
            self.after(0, lambda img=image.copy(): self.show_inline_preview(img))
        except Exception as e:
            self.after(0, lambda err=e: self.preview_image_label.configure(image=None, text=f"Preview failed:\n{err}"))

    def show_inline_preview(self, image):
        photo = ImageTk.PhotoImage(image)
        self.preview_photo_ref = photo
        self.preview_image_label.configure(image=photo, text="")

    def load_thumbnails_worker(self, items: list[MediaItem]):
        for item in items:
            if item.kind != "image":
                continue
            try:
                local = self.ensure_preview_file(item)
                if not local or not local.exists():
                    continue

                image = Image.open(local)
                image.thumbnail(THUMB_SIZE)
                photo = ImageTk.PhotoImage(image)

                self.thumb_refs[item.remote_path] = photo
                widget = getattr(item, "_preview_widget", None)
                if widget:
                    self.after(0, lambda w=widget, p=photo: w.configure(image=p, text=""))
            except Exception:
                # If Pillow cannot open a format such as HEIC, keep the item visible.
                continue

    def ensure_preview_file(self, item: MediaItem) -> Path | None:
        if item.remote_path in self.thumb_cache:
            return self.thumb_cache[item.remote_path]

        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", item.file_name)
        local = self.temp_dir / f"{abs(hash(item.remote_path))}_{safe_name}"

        if local.exists() and local.stat().st_size > 0:
            self.thumb_cache[item.remote_path] = local
            return local

        # Pull only the selected preview file into a temporary folder.
        result = self.run_adb(["pull", item.remote_path, str(local)], timeout=40)
        if result.returncode == 0 and local.exists() and local.stat().st_size > 0:
            self.thumb_cache[item.remote_path] = local
            return local

        return None

    # ---------------- Backup ----------------

    def go_backup(self):
        self.tabs.set("2  Backup")

    def selected_files_for_backup(self) -> list[MediaItem]:
        selected: list[MediaItem] = []
        for folder, files in self.sync_plan.items():
            var = self.folder_vars.get(folder)
            if var and var.get():
                selected.extend(files)
        return selected

    def trigger_backup(self):
        if self.is_busy:
            return
        target = self.target_path.get().strip()
        if not target:
            messagebox.showwarning("Missing Information", "Choose a backup folder.")
            return

        files = self.selected_files_for_backup()
        if not files:
            messagebox.showinfo("No Selection", "No new files are selected for backup.")
            return

        self.lock_ui("backup copy", risky=True)
        self.stop_requested = False
        self.btn_stop.configure(state="normal")
        self.progress.set(0)
        self.set_status("Backing up...", ACCENT_2)
        threading.Thread(target=self.backup_worker, args=(target, files), daemon=True).start()

    def request_stop(self):
        self.stop_requested = True
        self.btn_stop.configure(state="disabled")
        self.backup_status.configure(text="Safe stop requested. The current file will finish first...", text_color=ACCENT)

    def backup_worker(self, target: str, files: list[MediaItem]):
        copied = 0
        failed = 0
        failed_files: list[str] = []
        total = len(files)

        for idx, item in enumerate(files, start=1):
            if self.stop_requested:
                break

            local_path = Path(target) / item.rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            self.after(0, lambda i=idx, t=total, n=item.file_name: self.backup_status.configure(text=f"Copying {i}/{t}: {n}", text_color=TEXT))

            result = self.run_adb(["pull", item.remote_path, str(local_path)], timeout=None)
            copied_ok = result.returncode == 0 and local_path.exists()

            if copied_ok:
                copied += 1
            else:
                failed += 1
                failed_files.append(item.file_name)
                self.after(0, lambda n=item.file_name: self.backup_status.configure(text=f"Failed to copy: {n}", text_color=DANGER))

            self.after(0, lambda p=idx / total: self.progress.set(p))

        self.after(0, lambda: self.backup_finished(copied, failed, self.stop_requested, failed_files))

    def backup_finished(self, copied: int, failed: int, stopped: bool, failed_files: list[str]):
        self.btn_stop.configure(state="disabled")
        self.unlock_ui()

        if stopped:
            self.backup_status.configure(text=f"Backup stopped. Copied: {copied}, Failed: {failed}", text_color=ACCENT)
            self.set_status("Stopped", ACCENT_2)
        else:
            self.backup_status.configure(text=f"Backup finished. Copied: {copied}, Failed: {failed}", text_color=OK if failed == 0 else ACCENT)
            self.set_status("Backup complete", OK)

        if failed_files:
            shown = "\n".join(failed_files[:8])
            extra = "" if len(failed_files) <= 8 else f"\n...and {len(failed_files) - 8} more"
            messagebox.showwarning("Backup Warning", f"Some files could not be copied:\n\n{shown}{extra}")

    # ---------------- Clean duplicates ----------------

    def trigger_clean(self):
        if self.is_busy:
            return
        target = self.target_path.get().strip()
        if not target:
            messagebox.showwarning("Missing Information", "Choose the target disk folder first.")
            return

        if not messagebox.askyesno("Confirm", "The target disk will be scanned for duplicates with the same relative path and file size. Delete the duplicates that are found?"):
            return

        self.lock_ui("disk duplicate cleanup", risky=True)
        self.clean_progress.set(0)
        self.clean_status.configure(text="Scanning target disk...", text_color=TEXT)
        self.set_status("Cleaning...", ACCENT_2)
        threading.Thread(target=self.clean_worker, args=(target,), daemon=True).start()

    def clean_worker(self, target: str):
        try:
            target_path = Path(target)
            groups: dict[tuple[str, int], list[Path]] = {}

            all_files = []
            for root, _dirs, files in os.walk(target_path):
                for name in files:
                    all_files.append(Path(root) / name)

            total = max(len(all_files), 1)
            for idx, full in enumerate(all_files, start=1):
                try:
                    rel = full.relative_to(target_path).as_posix().lower()
                    size = full.stat().st_size
                    groups.setdefault((rel, size), []).append(full)
                except OSError:
                    continue
                if idx % 50 == 0:
                    self.after(0, lambda p=idx / total: self.clean_progress.set(p))

            duplicates = [paths for paths in groups.values() if len(paths) > 1]
            deleted = 0

            for paths in duplicates:
                paths.sort(key=lambda p: p.stat().st_mtime)
                for duplicate in paths[1:]:
                    try:
                        duplicate.unlink()
                        deleted += 1
                    except OSError:
                        pass

            self.after(0, lambda: self.clean_finished(len(duplicates), deleted))
        except Exception as e:
            self.after(0, lambda: self.clean_error(str(e)))

    def clean_finished(self, groups: int, deleted: int):
        self.clean_progress.set(1)
        self.clean_status.configure(text=f"Cleanup finished. Groups: {groups}, Deleted duplicates: {deleted}", text_color=OK)
        self.set_status("Cleanup complete", OK)
        self.unlock_ui()
        messagebox.showinfo("Cleanup Report", f"Duplicate groups: {groups}\nDeleted files: {deleted}")

    def clean_error(self, error: str):
        self.clean_status.configure(text=f"Cleanup error: {error}", text_color=DANGER)
        self.set_status("Error", DANGER)
        self.unlock_ui()

    # ---------------- Phone cleanup ----------------

    def parse_cutoff_timestamp(self) -> float | None:
        try:
            cutoff_day = datetime.strptime(self.selected_cleanup_date_text(), "%Y-%m-%d")
        except ValueError:
            return None
        return (cutoff_day + timedelta(days=1)).timestamp()

    def trigger_phone_cleanup_scan(self):
        if self.is_busy:
            return

        cutoff_ts = self.parse_cutoff_timestamp()
        source = self.source_path.get().strip().rstrip("/")
        target = self.target_path.get().strip()

        if cutoff_ts is None:
            messagebox.showwarning("Invalid Date", "Choose a valid cutoff date.")
            return
        if not source:
            messagebox.showwarning("Missing Information", "Phone folder cannot be empty. Example: /sdcard")
            return
        if not target:
            messagebox.showwarning("Missing Information", "Choose the disk backup folder first.")
            return

        self.phone_cleanup_candidates.clear()
        self.btn_delete_phone_cleanup.configure(state="disabled")
        self.phone_cleanup_progress.set(0)
        for child in self.phone_cleanup_list.winfo_children():
            child.destroy()

        self.lock_ui("phone cleanup scan", risky=False)
        self.set_status("Checking phone cleanup...", ACCENT_2)
        self.phone_cleanup_status.configure(text="Indexing disk backup...", text_color=TEXT)
        threading.Thread(target=self.phone_cleanup_scan_worker, args=(source, target, cutoff_ts), daemon=True).start()

    def phone_cleanup_scan_worker(self, source: str, target: str, cutoff_ts: float):
        try:
            existing = self.cached_local_index(target)
            self.after(0, lambda: self.phone_cleanup_status.configure(text="Reading phone media dates from MediaStore...", text_color=TEXT))
            rows = self.query_phone_cleanup_rows(source)
            if not rows or all(modified_ts is None for _path, modified_ts in rows):
                self.after(0, lambda: self.phone_cleanup_status.configure(text="MediaStore has no dates. Reading folder dates from Android file system...", text_color=TEXT))
                fallback_rows = self.query_phone_cleanup_rows_from_find(source)
                if fallback_rows:
                    rows = fallback_rows
            if not rows and self.media_items:
                rows = [(item.remote_path, None) for item in self.media_items]
            total = max(len(rows), 1)
            candidates: list[MediaItem] = []
            media_seen = 0
            backed_up_seen = 0
            older_seen = 0
            missing_date_seen = 0
            filename_date_seen = 0

            for idx, (remote_path, modified_ts) in enumerate(rows, start=1):
                lower = remote_path.lower()
                if not lower.endswith(MEDIA_EXTS):
                    continue
                media_seen += 1

                rel = self.normalize_remote_path(remote_path, source)
                name = remote_path.split("/")[-1]
                is_backed_up = rel.lower() in existing["paths"] or name.lower() in existing["names"]
                if not is_backed_up:
                    continue
                backed_up_seen += 1

                if modified_ts is None:
                    modified_ts = self.infer_timestamp_from_name_or_path(remote_path)
                    if modified_ts is not None:
                        filename_date_seen += 1
                    else:
                        missing_date_seen += 1
                        continue
                if modified_ts >= cutoff_ts:
                    continue
                older_seen += 1

                folder = os.path.dirname(rel).replace("\\", "/") or "Root"
                kind = "image" if lower.endswith(IMAGE_EXTS) else "video"
                item = MediaItem(remote_path, rel, name, folder, None, kind, True)
                item.cleanup_ts = modified_ts
                candidates.append(item)

                if idx % 50 == 0:
                    self.after(0, lambda p=idx / total: self.phone_cleanup_progress.set(p))

            stats = {
                "media": media_seen,
                "backed_up": backed_up_seen,
                "older": older_seen,
                "missing_date": missing_date_seen,
                "filename_date": filename_date_seen,
            }
            self.after(0, lambda: self.phone_cleanup_scan_finished(candidates, stats))
        except FileNotFoundError:
            self.after(0, lambda: self.phone_cleanup_error("ADB was not found. Put adb_tools/adb.exe next to this app or add adb to PATH."))
        except Exception as e:
            self.after(0, lambda: self.phone_cleanup_error(f"Phone cleanup scan error:\n{e}"))

    def query_phone_cleanup_rows(self, source: str) -> list[tuple[str, float | None]]:
        cmd = ["shell", "content", "query", "--uri", "content://media/external/file", "--projection", "_data,date_modified,date_added"]
        result = self.run_adb(cmd, timeout=60)
        if result.returncode != 0 or not result.stdout.strip():
            return [(path, None) for path, _size in self.query_mediastore(source)]

        search_filter = source.replace("/sdcard", "/storage/emulated/0").rstrip("/")
        rows: list[tuple[str, float | None]] = []
        for line in result.stdout.splitlines():
            if "_data=" not in line:
                continue
            path = line.split("_data=")[-1].split(",")[0].strip()
            if not path.startswith(search_filter):
                continue

            modified_ts = None
            modified_match = re.search(r"date_modified=(\d+)", line)
            added_match = re.search(r"date_added=(\d+)", line)
            date_match = modified_match or added_match
            if date_match:
                try:
                    modified_ts = float(date_match.group(1))
                except ValueError:
                    modified_ts = None
            rows.append((path, modified_ts))
        return rows

    def query_phone_cleanup_rows_from_find(self, source: str) -> list[tuple[str, float | None]]:
        patterns = " -o ".join([f"-iname '*{ext}'" for ext in MEDIA_EXTS])
        cmd = f"find {shell_quote(source)} -type f \\( {patterns} \\) -printf '%T@|%p\\n' 2>/dev/null"
        result = self.run_adb(["shell", cmd], timeout=120)
        if result.returncode != 0 or not result.stdout.strip():
            cmd = f"find {shell_quote(source)} -type f \\( {patterns} \\) -exec stat -c '%Y|%n' {{}} \\; 2>/dev/null"
            result = self.run_adb(["shell", cmd], timeout=180)
        if result.returncode != 0 or not result.stdout.strip():
            return []

        rows: list[tuple[str, float | None]] = []
        for line in result.stdout.splitlines():
            if "|" not in line:
                continue
            ts_text, path = line.split("|", 1)
            try:
                modified_ts = float(ts_text)
                if modified_ts > 100000000000:
                    modified_ts = modified_ts / 1000
            except ValueError:
                modified_ts = None
            if path:
                rows.append((path.strip(), modified_ts))
        return rows

    def infer_timestamp_from_name_or_path(self, remote_path: str) -> float | None:
        name = remote_path.split("/")[-1]
        candidates = [
            r"(20\d{2})[-_.]?([01]\d)[-_.]?([0-3]\d)",
            r"([0-3]\d)[-_.]([01]\d)[-_.](20\d{2})",
        ]

        for pattern in candidates:
            for match in re.finditer(pattern, name):
                parts = match.groups()
                if len(parts[0]) == 4:
                    year, month, day = parts
                else:
                    day, month, year = parts
                ts = self.date_parts_to_timestamp(year, month, day)
                if ts is not None:
                    return ts

        epoch_match = re.search(r"(?<!\d)(1[5-9]\d{8}|2[0-2]\d{8})(?!\d)", name)
        if epoch_match:
            try:
                return float(epoch_match.group(1))
            except ValueError:
                return None

        epoch_ms_match = re.search(r"(?<!\d)(1[5-9]\d{11}|2[0-2]\d{11})(?!\d)", name)
        if epoch_ms_match:
            try:
                return float(epoch_ms_match.group(1)) / 1000
            except ValueError:
                return None

        return None

    def date_parts_to_timestamp(self, year: str, month: str, day: str) -> float | None:
        try:
            parsed = datetime(int(year), int(month), int(day))
        except ValueError:
            return None
        return parsed.timestamp()

    def phone_cleanup_scan_finished(self, candidates: list[MediaItem], stats: dict[str, int] | None = None):
        self.phone_cleanup_candidates = candidates
        self.phone_cleanup_progress.set(1)
        for child in self.phone_cleanup_list.winfo_children():
            child.destroy()

        if not candidates:
            if stats:
                self.phone_cleanup_status.configure(
                    text=(
                        "No deletable files matched. "
                        f"Phone media: {stats['media']} | Backed up on disk: {stats['backed_up']} | "
                        f"Older than cutoff: {stats['older']} | Filename dates: {stats.get('filename_date', 0)} | No date: {stats['missing_date']}"
                    ),
                    text_color=MUTED,
                )
            else:
                self.phone_cleanup_status.configure(text="No backed-up phone media matched this cutoff date.", text_color=MUTED)
            self.set_status("Phone cleanup ready", OK)
            self.unlock_ui()
            return

        images = sum(1 for item in candidates if item.kind == "image")
        videos = len(candidates) - images
        self.phone_cleanup_status.configure(text=f"Found {len(candidates)} deletable files: {images} photos, {videos} videos.", text_color=OK)

        for item in candidates[:120]:
            date_text = datetime.fromtimestamp(getattr(item, "cleanup_ts", 0)).strftime("%Y-%m-%d")
            label = ctk.CTkLabel(
                self.phone_cleanup_list,
                text=f"{date_text} | {self.truncate_middle(item.rel_path, 88)}",
                font=FONT_TEXT,
                text_color=TEXT,
                anchor="w",
            )
            label.pack(fill="x", padx=10, pady=3)

        if len(candidates) > 120:
            ctk.CTkLabel(
                self.phone_cleanup_list,
                text=f"...and {len(candidates) - 120} more files",
                font=FONT_TEXT,
                text_color=MUTED,
            ).pack(anchor="w", padx=10, pady=8)

        self.set_status("Phone cleanup ready", OK)
        self.unlock_ui()
        self.btn_delete_phone_cleanup.configure(state="normal")

    def trigger_phone_cleanup_delete(self):
        if self.is_busy:
            return
        if not self.phone_cleanup_candidates:
            messagebox.showinfo("No Files", "Find deletable files first.")
            return

        count = len(self.phone_cleanup_candidates)
        cutoff = self.selected_cleanup_date_text()
        if not messagebox.askyesno(
            "Confirm Phone Delete",
            f"This will permanently delete {count} backed-up media files from your phone saved on or before {cutoff}.\n\nContinue?",
        ):
            return

        self.lock_ui("phone delete", risky=True)
        self.stop_requested = False
        self.phone_cleanup_progress.set(0)
        self.set_status("Deleting from phone...", DANGER)
        self.phone_cleanup_status.configure(text="Deleting selected phone files...", text_color=DANGER)
        threading.Thread(target=self.phone_cleanup_delete_worker, args=(list(self.phone_cleanup_candidates),), daemon=True).start()

    def phone_cleanup_delete_worker(self, candidates: list[MediaItem]):
        deleted = 0
        failed: list[str] = []
        total = max(len(candidates), 1)

        for idx, item in enumerate(candidates, start=1):
            if self.stop_requested:
                break
            result = self.run_adb(["shell", f"rm -f {shell_quote(item.remote_path)}"], timeout=30)
            if result.returncode == 0:
                deleted += 1
            else:
                failed.append(item.file_name)
            self.after(0, lambda p=idx / total: self.phone_cleanup_progress.set(p))

        self.after(0, lambda: self.phone_cleanup_delete_finished(deleted, failed))

    def phone_cleanup_delete_finished(self, deleted: int, failed: list[str]):
        self.phone_cleanup_candidates.clear()
        self.btn_delete_phone_cleanup.configure(state="disabled")
        self.unlock_ui()
        self.set_status("Phone cleanup complete", OK if not failed else ACCENT)
        self.phone_cleanup_status.configure(text=f"Deleted from phone: {deleted}. Failed: {len(failed)}.", text_color=OK if not failed else ACCENT)
        if failed:
            shown = "\n".join(failed[:8])
            extra = "" if len(failed) <= 8 else f"\n...and {len(failed) - 8} more"
            messagebox.showwarning("Phone Cleanup Warning", f"Some files could not be deleted:\n\n{shown}{extra}")

    def phone_cleanup_error(self, error: str):
        self.phone_cleanup_status.configure(text=error, text_color=DANGER)
        self.set_status("Error", DANGER)
        self.unlock_ui()

    def on_close(self):
        if self.is_busy:
            operation = self.active_operation or "current operation"
            if self.active_operation_is_risky:
                messagebox.showwarning(
                    "Risky Operation Running",
                    f"Cannot close while {operation} is running.\n\nPlease wait until it finishes to avoid interrupted copies or partial deletes.",
                )
            else:
                messagebox.showwarning(
                    "Operation Running",
                    f"Please wait for {operation} to finish before closing the app.",
                )
            return
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        finally:
            self.destroy()


if __name__ == "__main__":
    app = PhoneBackupPro()
    app.mainloop()
