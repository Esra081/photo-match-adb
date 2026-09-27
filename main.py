"""
PhotoMatch — Android & Apple iPhone Photo Backup & Match Tool
Sürüm: 2.0 Pro
Desteklenen Diller: Türkçe (TR), English (EN), Deutsch (DE), Español (ES)
"""

import sys
import os
import re
import shutil
import subprocess
import tempfile
import threading
import calendar
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

import ios_manager
import i18n
from i18n import t

# ============================================================
#  Yollar & Ortam Ayarları
# ============================================================

if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    MEI_DIR = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else EXE_DIR
    if (EXE_DIR / "adb_tools" / "adb.exe").exists():
        EMBEDDED_ADB = EXE_DIR / "adb_tools" / "adb.exe"
    elif (MEI_DIR / "adb_tools" / "adb.exe").exists():
        EMBEDDED_ADB = MEI_DIR / "adb_tools" / "adb.exe"
    else:
        EMBEDDED_ADB = Path("adb")
    BASE_DIR = MEI_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent
    EMBEDDED_ADB = BASE_DIR / "adb_tools" / "adb.exe"

ADB_PATH = str(EMBEDDED_ADB) if EMBEDDED_ADB.exists() else "adb"

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".dng")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".3gp", ".3gpp", ".avi", ".m4v", ".webm", ".mts", ".m2ts", ".ts")
MEDIA_EXTS = IMAGE_EXTS + VIDEO_EXTS

MAX_THUMBNAILS_PER_BATCH = 80
THUMB_SIZE = (118, 118)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ============================================================
#  Renk Paleti (Görsel Tasarıma Uygun)
# ============================================================

BG_DARK = "#0B0F19"          # Ana arka plan
SIDEBAR_BG = "#101522"       # Sol menü arka planı
SIDEBAR_BORDER = "#1B2335"   # Menü kenarlığı
CARD_BG = "#141A28"          # Kart arka planı
CARD_BG_2 = "#1B2334"        # İkincil kart / kutu
CARD_BORDER = "#253147"      # Kart kenarlığı
TEXT_WHITE = "#F8FAFC"       # Ana beyaz metin
TEXT_MUTED = "#8E9CAE"       # Gri soluk metin
ACCENT_PINK = "#FF2A7A"      # Neon pembe / ana vurgu
ACCENT_PINK_HOVER = "#E01E68"# Pembe hover
OK_GREEN = "#10B981"         # Yeşil (cihaz hazır, yeni)
INFO_BLUE = "#38BDF8"        # Açık mavi (diskte var)
PURPLE_DUP = "#A855F7"       # Mor (tekrarlar)
DANGER_RED = "#EF4444"       # Kırmızı (silme, durdur)
WARN_YELLOW = "#F59E0B"      # Sarı/turuncu (uyarı)

FONT_HEAD = ("Segoe UI", 20, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUB = ("Segoe UI", 12, "bold")
FONT_TEXT = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)


@dataclass
class MediaItem:
    remote_path: str
    rel_path: str
    file_name: str
    folder: str
    size: int | None
    kind: str
    exists_locally: bool = False
    path_parts: list[str] | None = None
    cleanup_ts: float | None = None


MAX_BACKUP_WORKERS = 4


def sanitize_windows_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', name).rstrip(' .')
    stem = cleaned.split('.')[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if stem in reserved:
        cleaned = f"_{cleaned}"
    return cleaned or "unnamed"


def sanitize_rel_path(rel_path: str) -> str:
    parts = Path(rel_path.replace("\\", "/")).parts
    clean_parts = [sanitize_windows_name(p) for p in parts if p and p != "."]
    return "/".join(clean_parts)


def to_windows_safe_path(p: Path) -> Path:
    resolved = p.resolve()
    path_str = str(resolved)
    if os.name == "nt" and not path_str.startswith("\\\\?\\") and len(path_str) >= 240:
        return Path(f"\\\\?\\{path_str}")
    return resolved


def creation_flags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def shell_quote(path: str) -> str:
    return "'" + path.replace("'", "'\"'\"'") + "'"


def format_size(bytes_val: int | None) -> str:
    if bytes_val is None:
        return "Bilinmiyor"
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    if bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


# ============================================================
#  Ana Uygulama Sınıfı
# ============================================================

class PhotoMatchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(t("app_title"))
        self.geometry("1300x820")
        self.minsize(1180, 720)
        self.configure(fg_color=BG_DARK)

        # Durum Değişkenleri
        self.current_step = 1
        self.device_mode = ctk.StringVar(value="Android")  # "Android" veya "iPhone"
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
        self.item_select_vars: dict[str, ctk.BooleanVar] = {}
        self.phone_cleanup_candidates: list[MediaItem] = []

        self.disk_index_cache: dict[str, any] | None = None
        self.disk_index_target = ""

        self.thumb_refs: dict[str, ImageTk.PhotoImage] = {}
        self.thumb_cache: dict[str, Path] = {}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="photomatch_preview_"))

        self.is_busy = False
        self.stop_requested = False
        self.pause_requested = False
        self.gallery_offset = 0
        self.connected_device_info = ""

        # UI Kurulumu
        self.build_shell_layout()
        self.show_step(1)
        self.detect_device_initial()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- Dış Kabuk Arayüzü ----------------

    def build_shell_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Sidebar
        self.grid_columnconfigure(1, weight=1)  # Main View

        # Sol Kenar Çubuğu (Sidebar)
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color=SIDEBAR_BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Logo & Başlık
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=18, pady=(20, 24))

        logo_badge = ctk.CTkLabel(
            logo_frame,
            text="📷",
            font=("Segoe UI", 24),
            width=48,
            height=48,
            fg_color=ACCENT_PINK,
            corner_radius=12,
        )
        logo_badge.pack(side="left", padx=(0, 12))

        title_box = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both")
        self.logo_title = ctk.CTkLabel(title_box, text="PhotoMatch", font=FONT_HEAD, text_color=TEXT_WHITE)
        self.logo_title.pack(anchor="w")
        self.logo_sub = ctk.CTkLabel(title_box, text=t("app_subtitle"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.logo_sub.pack(anchor="w")

        # Dikey Adım Gezgini (Stepper)
        self.stepper_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.stepper_frame.pack(fill="x", padx=12, pady=10)

        self.step_buttons = []
        steps_data = [
            (1, "step_1_title", "step_1_sub"),
            (2, "step_2_title", "step_2_sub"),
            (3, "step_3_title", "step_3_sub"),
            (4, "step_4_title", "step_4_sub"),
        ]

        for step_num, title_key, sub_key in steps_data:
            btn_frame = ctk.CTkFrame(self.stepper_frame, fg_color="transparent", corner_radius=10, height=60, cursor="hand2")
            btn_frame.pack(fill="x", pady=5)
            btn_frame.pack_propagate(False)

            num_badge = ctk.CTkLabel(
                btn_frame,
                text=str(step_num),
                width=32,
                height=32,
                font=FONT_SUB,
                corner_radius=16,
                fg_color=CARD_BG_2,
                text_color=TEXT_MUTED,
            )
            num_badge.pack(side="left", padx=(10, 10))

            text_box = ctk.CTkFrame(btn_frame, fg_color="transparent")
            text_box.pack(side="left", fill="both", expand=True)

            lbl_title = ctk.CTkLabel(text_box, text=t(title_key), font=FONT_SUB, text_color=TEXT_WHITE, anchor="w")
            lbl_title.pack(anchor="w", pady=(8, 0))

            lbl_sub = ctk.CTkLabel(text_box, text=t(sub_key), font=FONT_SMALL, text_color=TEXT_MUTED, anchor="w")
            lbl_sub.pack(anchor="w")

            # Click bind
            for w in (btn_frame, num_badge, text_box, lbl_title, lbl_sub):
                w.bind("<Button-1>", lambda _e, s=step_num: self.show_step(s))

            self.step_buttons.append({
                "num": step_num,
                "frame": btn_frame,
                "badge": num_badge,
                "title": lbl_title,
                "sub": lbl_sub,
                "title_key": title_key,
                "sub_key": sub_key,
            })

        # Alt Bilgi / Hakkında
        self.sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_bottom.pack(side="bottom", fill="x", padx=14, pady=16)

        self.btn_about = ctk.CTkButton(
            self.sidebar_bottom,
            text=f"ⓘ  {t('about')}",
            font=FONT_TEXT,
            fg_color=CARD_BG_2,
            hover_color=CARD_BORDER,
            text_color=TEXT_MUTED,
            border_width=1,
            border_color=CARD_BORDER,
            height=36,
            command=self.show_about_dialog,
        )
        self.btn_about.pack(fill="x")

        # Sağ Ana Kapsayıcı
        self.main_container = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=16, pady=14)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Üst Navigasyon Çubuğu (Top Bar)
        self.build_top_bar()

        # 4 Farklı Adım Panelleri
        self.step_views = {}
        self.step_views[1] = self.build_step1_view()
        self.step_views[2] = self.build_step2_view()
        self.step_views[3] = self.build_step3_view()
        self.step_views[4] = self.build_step4_view()

    def build_top_bar(self):
        top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent", height=46)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        # Sol: Cihaz Seçim Butonları (Android / iPhone)
        self.device_segmented = ctk.CTkSegmentedButton(
            top_bar,
            values=[t("device_android"), t("device_ios")],
            command=self.on_device_toggle,
            selected_color=ACCENT_PINK,
            selected_hover_color=ACCENT_PINK_HOVER,
            unselected_color=CARD_BG,
            unselected_hover_color=CARD_BG_2,
            font=FONT_SUB,
            height=36,
            corner_radius=8,
        )
        self.device_segmented.set(t("device_android"))
        self.device_segmented.pack(side="left")

        # Sağ: Dil Seçimi ve Ayar İkonu
        lang_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        lang_frame.pack(side="right")

        current_lang = i18n.get_current_lang()
        lang_options = list(i18n.LANGUAGES.values())
        cur_lang_text = i18n.LANGUAGES.get(current_lang, lang_options[0])

        self.lang_menu = ctk.CTkOptionMenu(
            lang_frame,
            values=lang_options,
            command=self.on_language_changed,
            fg_color=CARD_BG,
            button_color=CARD_BG_2,
            button_hover_color=CARD_BORDER,
            text_color=TEXT_WHITE,
            font=FONT_TEXT,
            width=130,
            height=36,
            corner_radius=8,
        )
        self.lang_menu.set(cur_lang_text)
        self.lang_menu.pack(side="right", padx=(8, 0))

        btn_settings = ctk.CTkButton(
            lang_frame,
            text="⚙",
            font=("Segoe UI", 16),
            width=36,
            height=36,
            fg_color=CARD_BG,
            hover_color=CARD_BG_2,
            border_width=1,
            border_color=CARD_BORDER,
            corner_radius=8,
            command=self.show_about_dialog,
        )
        btn_settings.pack(side="right")

    # ---------------- Adım Değiştirme (Navigation) ----------------

    def show_step(self, step_num: int):
        self.current_step = step_num
        for s in (1, 2, 3, 4):
            if s == step_num:
                self.step_views[s].grid(row=1, column=0, sticky="nsew")
            else:
                self.step_views[s].grid_forget()

        # Sidebar stilini güncelle
        for item in self.step_buttons:
            is_active = (item["num"] == step_num)
            if is_active:
                item["frame"].configure(fg_color=ACCENT_PINK)
                item["badge"].configure(fg_color=TEXT_WHITE, text_color=ACCENT_PINK)
                item["title"].configure(text_color=TEXT_WHITE)
                item["sub"].configure(text_color="#FFD1E3")
            else:
                item["frame"].configure(fg_color="transparent")
                item["badge"].configure(fg_color=CARD_BG_2, text_color=TEXT_MUTED)
                item["title"].configure(text_color=TEXT_WHITE)
                item["sub"].configure(text_color=TEXT_MUTED)

    def refresh_ui_texts(self):
        """Dil değiştiğinde tüm arayüz metinlerini günceller."""
        self.title(t("app_title"))
        self.logo_sub.configure(text=t("app_subtitle"))
        self.btn_about.configure(text=f"ⓘ  {t('about')}")

        for item in self.step_buttons:
            item["title"].configure(text=t(item["title_key"]))
            item["sub"].configure(text=t(item["sub_key"]))

        self.device_segmented.configure(values=[t("device_android"), t("device_ios")])
        self.device_segmented.set(t("device_ios") if self.is_ios_mode() else t("device_android"))

        # Adım 1 metinleri
        self.card_dev_title.configure(text=t("card_device_connected"))
        self.btn_test_dev.configure(text=f"✔ {t('btn_test_device')}")
        self.lbl_phone_folder.configure(text=t("card_phone_folder"))
        self.lbl_phone_folder_sub.configure(text=t("card_phone_folder_sub"))
        self.lbl_target_folder.configure(text=t("card_target_folder"))
        self.lbl_target_folder_sub.configure(text=t("card_target_folder_sub"))
        self.btn_browse_disk.configure(text=t("btn_browse"))
        self.btn_scan_main.configure(text=t("btn_scan"))
        self.lbl_folders_hdr.configure(text=t("folders_title"))
        self.lbl_gallery_hdr.configure(text=t("gallery_title"))
        self.entry_search.configure(placeholder_text=t("gallery_search_placeholder"))
        self.btn_filter.configure(text=t("btn_filter"))
        self.btn_load_more.configure(text=t("btn_load_more"))
        self.btn_go_backup.configure(text=t("btn_go_backup"))
        self.lbl_summary_hdr.configure(text=t("summary_title"))

        self.tile_total_lbl.configure(text=t("stat_total_media"))
        self.tile_new_lbl.configure(text=t("stat_new_photos"))
        self.tile_ondisk_lbl.configure(text=t("stat_on_disk"))
        self.tile_dup_lbl.configure(text=t("stat_duplicates"))

        # Adım 2 metinleri
        self.step2_title.configure(text=t("backup_running_title"))
        self.step2_sub.configure(text=t("backup_running_sub"))
        self.src_card_lbl.configure(text=t("backup_source"))
        self.dst_card_lbl.configure(text=t("backup_target"))
        self.btn_open_disk.configure(text=t("btn_open_folder"))
        self.btn_pause.configure(text=f"⏸ {t('btn_pause')}")
        self.btn_stop.configure(text=f"⛔ {t('btn_stop')}")

        # Adım 3 metinleri
        self.dup_hdr.configure(text=t("dup_title"))
        self.dup_sub_lbl.configure(text=t("dup_sub"))
        self.tile_dup_cnt_lbl.configure(text=t("dup_card_count"))
        self.tile_dup_spc_lbl.configure(text=t("dup_card_space"))
        self.tile_dup_unq_lbl.configure(text=t("dup_card_unique"))
        self.tile_dup_tot_lbl.configure(text=t("dup_card_total"))
        self.btn_del_dup.configure(text=f"🗑 {t('btn_delete_duplicates')}")
        self.btn_rescan_dup.configure(text=f"🔄 {t('btn_rescan_duplicates')}")

        # Adım 4 metinleri
        self.pclean_hdr.configure(text=t("phone_clean_title"))
        self.pclean_sub.configure(text=t("phone_clean_sub"))
        self.clean_date_lbl.configure(text=t("clean_date_title"))
        self.clean_date_sub.configure(text=t("clean_date_sub"))
        self.lbl_warn_hdr.configure(text=t("warning_title"))
        self.lbl_warn_1.configure(text=t("warning_bullet_1"))
        self.lbl_warn_2.configure(text=t("warning_bullet_2"))
        self.lbl_warn_3.configure(text=t("warning_bullet_3"))
        self.btn_find_clean.configure(text=t("btn_find_phone_cleanup"))
        self.btn_start_clean.configure(text=f"🗑 {t('btn_start_phone_clean')}")

    def on_language_changed(self, chosen_label: str):
        for code, label in i18n.LANGUAGES.items():
            if label == chosen_label:
                i18n.save_lang(code)
                break
        self.refresh_ui_texts()

    def is_ios_mode(self) -> bool:
        val = self.device_segmented.get()
        return "iphone" in val.lower() or "ios" in val.lower()

    def on_device_toggle(self, mode: str):
        if self.is_ios_mode():
            self.device_mode.set("iPhone")
            devices = ios_manager.list_ios_devices()
            if devices:
                self.source_path.set(f"{devices[0]}/DCIM")
                self.set_device_connected_ui(True, devices[0])
            else:
                self.source_path.set("Apple iPhone / DCIM")
                self.set_device_connected_ui(False, "Apple iPhone")
        else:
            self.device_mode.set("Android")
            self.source_path.set("/sdcard")
            self.detect_android_device()

        self.clear_analysis_ui()

    def set_device_connected_ui(self, connected: bool, name: str):
        if connected:
            self.lbl_dev_name.configure(text=f"● {name}", text_color=OK_GREEN)
            self.connected_device_info = name
        else:
            self.lbl_dev_name.configure(text=f"○ {t('card_device_none')}", text_color=TEXT_MUTED)
            self.connected_device_info = ""

    def detect_device_initial(self):
        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _detect_worker(self):
        time.sleep(0.5)
        if self.is_ios_mode():
            devs = ios_manager.list_ios_devices()
            if devs:
                self.after(0, lambda: self.set_device_connected_ui(True, devs[0]))
            else:
                self.after(0, lambda: self.set_device_connected_ui(False, "Apple iPhone"))
        else:
            self.detect_android_device()

    def detect_android_device(self):
        try:
            res = self.run_adb(["devices"], timeout=6)
            lines = [x.strip() for x in res.stdout.splitlines() if x.strip()]
            devices = [x.split("\t")[0] for x in lines[1:] if "\tdevice" in x]
            if devices:
                dev_id = devices[0]
                model_res = self.run_adb(["-s", dev_id, "shell", "getprop", "ro.product.model"], timeout=5)
                model_name = model_res.stdout.strip() if model_res.returncode == 0 and model_res.stdout.strip() else dev_id
                self.after(0, lambda: self.set_device_connected_ui(True, f"{model_name} ({dev_id})"))
            else:
                self.after(0, lambda: self.set_device_connected_ui(False, "Android"))
        except Exception:
            self.after(0, lambda: self.set_device_connected_ui(False, "Android"))

    # ============================================================
    #  ADIM 1: Fotoğrafları Tara (Scan & Gallery)
    # ============================================================

    def build_step1_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        # Üst 3 Kart (Cihaz, Telefon Klasörü, Hedef Klasör)
        top_cards = ctk.CTkFrame(view, fg_color="transparent")
        top_cards.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for i in range(3):
            top_cards.grid_columnconfigure(i, weight=1)

        # Kart 1: Cihaz Durumu
        card_dev = ctk.CTkFrame(top_cards, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER, height=96)
        card_dev.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        card_dev.pack_propagate(False)

        dev_icon_box = ctk.CTkLabel(card_dev, text="📱", font=("Segoe UI", 20), width=42, height=42, fg_color=CARD_BG_2, corner_radius=8)
        dev_icon_box.pack(side="left", padx=12, pady=10)

        dev_info_box = ctk.CTkFrame(card_dev, fg_color="transparent")
        dev_info_box.pack(side="left", fill="both", expand=True, pady=8)

        self.card_dev_title = ctk.CTkLabel(dev_info_box, text=t("card_device_connected"), font=FONT_SUB, text_color=TEXT_WHITE)
        self.card_dev_title.pack(anchor="w")

        self.lbl_dev_name = ctk.CTkLabel(dev_info_box, text=f"○ {t('card_device_none')}", font=FONT_TEXT, text_color=TEXT_MUTED)
        self.lbl_dev_name.pack(anchor="w")

        self.btn_test_dev = ctk.CTkButton(
            card_dev,
            text=f"✔ {t('btn_test_device')}",
            font=FONT_SMALL,
            width=100,
            height=28,
            fg_color=CARD_BG_2,
            hover_color=CARD_BORDER,
            border_width=1,
            border_color=CARD_BORDER,
            command=self.test_device_action,
        )
        self.btn_test_dev.pack(side="right", padx=12)

        # Kart 2: Telefon Klasörü
        card_src = ctk.CTkFrame(top_cards, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER, height=96)
        card_src.grid(row=0, column=1, sticky="ew", padx=4)
        card_src.pack_propagate(False)

        src_icon_box = ctk.CTkLabel(card_src, text="📁", font=("Segoe UI", 20), width=42, height=42, fg_color=CARD_BG_2, corner_radius=8)
        src_icon_box.pack(side="left", padx=12, pady=10)

        src_info_box = ctk.CTkFrame(card_src, fg_color="transparent")
        src_info_box.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=8)

        self.lbl_phone_folder = ctk.CTkLabel(src_info_box, text=t("card_phone_folder"), font=FONT_SUB, text_color=TEXT_WHITE)
        self.lbl_phone_folder.pack(anchor="w")

        self.lbl_phone_folder_sub = ctk.CTkLabel(src_info_box, text=t("card_phone_folder_sub"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.lbl_phone_folder_sub.pack(anchor="w")

        self.entry_source = ctk.CTkEntry(src_info_box, textvariable=self.source_path, height=26, fg_color=BG_DARK, border_width=1, border_color=CARD_BORDER, text_color=TEXT_WHITE, font=FONT_SMALL)
        self.entry_source.pack(fill="x", pady=(4, 0))

        # Kart 3: Yedekleme Klasörü
        card_dst = ctk.CTkFrame(top_cards, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER, height=96)
        card_dst.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        card_dst.pack_propagate(False)

        dst_icon_box = ctk.CTkLabel(card_dst, text="💾", font=("Segoe UI", 20), width=42, height=42, fg_color=CARD_BG_2, corner_radius=8)
        dst_icon_box.pack(side="left", padx=12, pady=10)

        dst_info_box = ctk.CTkFrame(card_dst, fg_color="transparent")
        dst_info_box.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)

        self.lbl_target_folder = ctk.CTkLabel(dst_info_box, text=t("card_target_folder"), font=FONT_SUB, text_color=TEXT_WHITE)
        self.lbl_target_folder.pack(anchor="w")

        self.lbl_target_folder_sub = ctk.CTkLabel(dst_info_box, text=t("card_target_folder_sub"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.lbl_target_folder_sub.pack(anchor="w")

        self.entry_target = ctk.CTkEntry(dst_info_box, textvariable=self.target_path, height=26, fg_color=BG_DARK, border_width=1, border_color=CARD_BORDER, text_color=TEXT_WHITE, font=FONT_SMALL)
        self.entry_target.pack(fill="x", pady=(4, 0))

        self.btn_browse_disk = ctk.CTkButton(
            card_dst,
            text=t("btn_browse"),
            font=FONT_SMALL,
            width=68,
            height=28,
            fg_color=CARD_BG_2,
            hover_color=CARD_BORDER,
            border_width=1,
            border_color=CARD_BORDER,
            command=self.select_target_disk,
        )
        self.btn_browse_disk.pack(side="right", padx=10)

        # Ana Gövde (3 Sütun: Klasörler | Galeri | Özet)
        body = ctk.CTkFrame(view, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0)  # Klasörler ~210px
        body.grid_columnconfigure(1, weight=1)  # Galeri
        body.grid_columnconfigure(2, weight=0)  # Özet ~230px

        # Sütun 1: Klasörler
        col_folders = ctk.CTkFrame(body, width=220, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        col_folders.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        col_folders.grid_propagate(False)

        folder_hdr = ctk.CTkFrame(col_folders, fg_color="transparent")
        folder_hdr.pack(fill="x", padx=12, pady=(12, 8))
        self.lbl_folders_hdr = ctk.CTkLabel(folder_hdr, text=t("folders_title"), font=FONT_TITLE, text_color=TEXT_WHITE)
        self.lbl_folders_hdr.pack(side="left")

        self.folder_scroll = ctk.CTkScrollableFrame(col_folders, fg_color="transparent")
        self.folder_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # Sütun 2: Galeri Önizleme
        col_gallery = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        col_gallery.grid(row=0, column=1, sticky="nsew", padx=4)
        col_gallery.grid_rowconfigure(1, weight=1)
        col_gallery.grid_columnconfigure(0, weight=1)

        gallery_top = ctk.CTkFrame(col_gallery, fg_color="transparent")
        gallery_top.grid(row=0, column=0, sticky="ew", padx=14, pady=12)

        icon_cam = ctk.CTkLabel(gallery_top, text="🖼️", font=("Segoe UI", 16))
        icon_cam.pack(side="left", padx=(0, 8))

        gal_info = ctk.CTkFrame(gallery_top, fg_color="transparent")
        gal_info.pack(side="left")
        self.lbl_gallery_hdr = ctk.CTkLabel(gal_info, text=t("gallery_title"), font=FONT_TITLE, text_color=TEXT_WHITE)
        self.lbl_gallery_hdr.pack(anchor="w")
        self.lbl_gallery_sub = ctk.CTkLabel(gal_info, text=t("gallery_sub"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.lbl_gallery_sub.pack(anchor="w")

        # Filtreleme & Arama Kutusu
        gal_search_box = ctk.CTkFrame(gallery_top, fg_color="transparent")
        gal_search_box.pack(side="right")

        self.entry_search = ctk.CTkEntry(
            gal_search_box,
            textvariable=self.search_text,
            placeholder_text=t("gallery_search_placeholder"),
            font=FONT_TEXT,
            width=200,
            height=32,
            fg_color=BG_DARK,
            border_width=1,
            border_color=CARD_BORDER,
            text_color=TEXT_WHITE,
        )
        self.entry_search.pack(side="left", padx=(0, 6))
        self.entry_search.bind("<KeyRelease>", lambda _e: self.apply_filter())

        self.btn_filter = ctk.CTkButton(
            gal_search_box,
            text=t("btn_filter"),
            font=FONT_SMALL,
            width=68,
            height=32,
            fg_color=CARD_BG_2,
            hover_color=CARD_BORDER,
            border_width=1,
            border_color=CARD_BORDER,
            command=self.apply_filter,
        )
        self.btn_filter.pack(side="left")

        # Fotoğraf Kartları Tablosu
        self.gallery_scroll = ctk.CTkScrollableFrame(col_gallery, fg_color=BG_DARK, corner_radius=8)
        self.gallery_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

        # Sütun 3: Tarama Özeti
        col_summary = ctk.CTkFrame(body, width=230, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        col_summary.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        col_summary.grid_propagate(False)

        summary_hdr = ctk.CTkFrame(col_summary, fg_color="transparent")
        summary_hdr.pack(fill="x", padx=14, pady=(12, 10))
        self.lbl_summary_hdr = ctk.CTkLabel(summary_hdr, text=t("summary_title"), font=FONT_TITLE, text_color=TEXT_WHITE)
        self.lbl_summary_hdr.pack(anchor="w")

        # 4 Özet Kartı
        self.tile_total_val, self.tile_total_lbl = self.build_stat_tile(col_summary, "📷", ACCENT_PINK, "0", "stat_total_media")
        self.tile_new_val, self.tile_new_lbl = self.build_stat_tile(col_summary, "✨", OK_GREEN, "0", "stat_new_photos")
        self.tile_ondisk_val, self.tile_ondisk_lbl = self.build_stat_tile(col_summary, "💾", INFO_BLUE, "0", "stat_on_disk")
        self.tile_dup_val, self.tile_dup_lbl = self.build_stat_tile(col_summary, "🔄", PURPLE_DUP, "0", "stat_duplicates")

        # Taramayı Başlat Butonu
        self.btn_scan_main = ctk.CTkButton(
            col_summary,
            text=t("btn_scan"),
            font=FONT_SUB,
            fg_color=ACCENT_PINK,
            hover_color=ACCENT_PINK_HOVER,
            height=40,
            corner_radius=8,
            command=self.trigger_scan,
        )
        self.btn_scan_main.pack(fill="x", padx=12, pady=(16, 0))

        # Alt İşlem Çubuğu (Footer)
        bottom_bar = ctk.CTkFrame(view, fg_color="transparent", height=44)
        bottom_bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.lbl_footer_status = ctk.CTkLabel(bottom_bar, text="", font=FONT_TEXT, text_color=TEXT_MUTED)
        self.lbl_footer_status.pack(side="left")

        self.btn_go_backup = ctk.CTkButton(
            bottom_bar,
            text=t("btn_go_backup"),
            font=FONT_SUB,
            fg_color=ACCENT_PINK,
            hover_color=ACCENT_PINK_HOVER,
            height=38,
            corner_radius=8,
            command=self.go_to_backup_step,
        )
        self.btn_go_backup.pack(side="right")

        self.btn_load_more = ctk.CTkButton(
            bottom_bar,
            text=t("btn_load_more"),
            font=FONT_SUB,
            fg_color=CARD_BG,
            hover_color=CARD_BG_2,
            border_width=1,
            border_color=CARD_BORDER,
            height=38,
            corner_radius=8,
            command=self.load_more_gallery,
            state="disabled",
        )
        self.btn_load_more.pack(side="right", padx=(0, 10))

        return view

    def build_stat_tile(self, parent, icon: str, color: str, initial_val: str, label_key: str):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG_2, corner_radius=8, border_width=1, border_color=CARD_BORDER)
        card.pack(fill="x", padx=12, pady=5)

        icon_lbl = ctk.CTkLabel(card, text=icon, font=("Segoe UI", 16), text_color=color, width=32, height=32, fg_color=BG_DARK, corner_radius=6)
        icon_lbl.pack(side="left", padx=10, pady=8)

        text_f = ctk.CTkFrame(card, fg_color="transparent")
        text_f.pack(side="left", fill="both", expand=True, pady=6)

        val_lbl = ctk.CTkLabel(text_f, text=initial_val, font=FONT_TITLE, text_color=TEXT_WHITE)
        val_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(text_f, text=t(label_key), font=FONT_SMALL, text_color=TEXT_MUTED)
        desc_lbl.pack(anchor="w")

        return val_lbl, desc_lbl

    # ============================================================
    #  ADIM 2: Yedekle (Backup View)
    # ============================================================

    def build_step2_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)

        # Başlık
        hdr_frame = ctk.CTkFrame(view, fg_color="transparent")
        hdr_frame.pack(fill="x", pady=(10, 20))
        self.step2_title = ctk.CTkLabel(hdr_frame, text=t("backup_running_title"), font=FONT_HEAD, text_color=TEXT_WHITE)
        self.step2_title.pack(anchor="w")
        self.step2_sub = ctk.CTkLabel(hdr_frame, text=t("backup_running_sub"), font=FONT_TEXT, text_color=TEXT_MUTED)
        self.step2_sub.pack(anchor="w", pady=(4, 0))

        # Akış Kartı (Kaynak -> Hedef)
        flow_card = ctk.CTkFrame(view, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        flow_card.pack(fill="x", pady=(0, 20))
        flow_card.grid_columnconfigure(0, weight=1)
        flow_card.grid_columnconfigure(1, weight=0)
        flow_card.grid_columnconfigure(2, weight=1)

        # Kaynak
        src_box = ctk.CTkFrame(flow_card, fg_color="transparent")
        src_box.grid(row=0, column=0, sticky="ew", padx=20, pady=16)
        ctk.CTkLabel(src_box, text="📱", font=("Segoe UI", 24), width=48, height=48, fg_color=CARD_BG_2, corner_radius=10).pack(side="left", padx=(0, 14))
        src_t = ctk.CTkFrame(src_box, fg_color="transparent")
        src_t.pack(side="left", fill="both")
        self.src_card_lbl = ctk.CTkLabel(src_t, text=t("backup_source"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.src_card_lbl.pack(anchor="w")
        self.src_name_lbl = ctk.CTkLabel(src_t, text="Telefon / DCIM", font=FONT_SUB, text_color=TEXT_WHITE)
        self.src_name_lbl.pack(anchor="w")

        # Ok İşareti
        ctk.CTkLabel(flow_card, text="➔", font=("Segoe UI", 24), text_color=ACCENT_PINK).grid(row=0, column=1)

        # Hedef
        dst_box = ctk.CTkFrame(flow_card, fg_color="transparent")
        dst_box.grid(row=0, column=2, sticky="ew", padx=20, pady=16)
        ctk.CTkLabel(dst_box, text="💾", font=("Segoe UI", 24), width=48, height=48, fg_color=CARD_BG_2, corner_radius=10).pack(side="left", padx=(0, 14))
        dst_t = ctk.CTkFrame(dst_box, fg_color="transparent")
        dst_t.pack(side="left", fill="both", expand=True)
        self.dst_card_lbl = ctk.CTkLabel(dst_t, text=t("backup_target"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.dst_card_lbl.pack(anchor="w")
        self.dst_name_lbl = ctk.CTkLabel(dst_t, text="Seçilen Disk Klasörü", font=FONT_SUB, text_color=TEXT_WHITE)
        self.dst_name_lbl.pack(anchor="w")

        self.btn_open_disk = ctk.CTkButton(
            dst_box,
            text=t("btn_open_folder"),
            font=FONT_SMALL,
            width=100,
            height=30,
            fg_color=CARD_BG_2,
            hover_color=CARD_BORDER,
            command=self.open_target_disk,
        )
        self.btn_open_disk.pack(side="right")

        # İlerleme Çubuğu ve Yüzde
        progress_wrap = ctk.CTkFrame(view, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER, padx=20, pady=20)
        progress_wrap.pack(fill="x", pady=(0, 20))

        prog_hdr = ctk.CTkFrame(progress_wrap, fg_color="transparent")
        prog_hdr.pack(fill="x", pady=(0, 8))

        self.backup_status_text = ctk.CTkLabel(prog_hdr, text=t("backup_completed"), font=FONT_SUB, text_color=TEXT_WHITE)
        self.backup_status_text.pack(side="left")

        self.backup_pct_label = ctk.CTkLabel(prog_hdr, text="%0", font=FONT_TITLE, text_color=ACCENT_PINK)
        self.backup_pct_label.pack(side="right")

        self.backup_progress_bar = ctk.CTkProgressBar(progress_wrap, height=14, fg_color=BG_DARK, progress_color=ACCENT_PINK)
        self.backup_progress_bar.set(0)
        self.backup_progress_bar.pack(fill="x", pady=(0, 10))

        self.lbl_time_remaining = ctk.CTkLabel(progress_wrap, text="", font=FONT_SMALL, text_color=TEXT_MUTED)
        self.lbl_time_remaining.pack(anchor="w")

        # Anlık Kopyalanan Dosya Kartı
        self.current_copy_card = ctk.CTkFrame(view, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER, height=90)
        self.current_copy_card.pack(fill="x", pady=(0, 24))
        self.current_copy_card.pack_propagate(False)

        self.cur_file_thumb = ctk.CTkLabel(self.current_copy_card, text="📷", font=("Segoe UI", 24), width=64, height=64, fg_color=BG_DARK, corner_radius=8)
        self.cur_file_thumb.pack(side="left", padx=14, pady=12)

        cur_info = ctk.CTkFrame(self.current_copy_card, fg_color="transparent")
        cur_info.pack(side="left", fill="both", expand=True, pady=14)

        self.cur_file_title = ctk.CTkLabel(cur_info, text=t("copying_file"), font=FONT_SMALL, text_color=ACCENT_PINK)
        self.cur_file_title.pack(anchor="w")

        self.cur_file_name = ctk.CTkLabel(cur_info, text="...", font=FONT_SUB, text_color=TEXT_WHITE)
        self.cur_file_name.pack(anchor="w")

        self.cur_file_size = ctk.CTkLabel(cur_info, text="", font=FONT_SMALL, text_color=TEXT_MUTED)
        self.cur_file_size.pack(anchor="w")

        # Butonlar (Duraklat, Durdur)
        action_bar = ctk.CTkFrame(view, fg_color="transparent")
        action_bar.pack(fill="x")

        self.btn_pause = ctk.CTkButton(
            action_bar,
            text=f"⏸ {t('btn_pause')}",
            font=FONT_SUB,
            width=140,
            height=40,
            fg_color=CARD_BG,
            hover_color=CARD_BG_2,
            border_width=1,
            border_color=CARD_BORDER,
            command=self.toggle_pause_backup,
        )
        self.btn_pause.pack(side="left")

        self.btn_stop = ctk.CTkButton(
            action_bar,
            text=f"⛔ {t('btn_stop')}",
            font=FONT_SUB,
            width=200,
            height=40,
            fg_color=CARD_BG,
            hover_color=DANGER_RED,
            border_width=1,
            border_color=DANGER_RED,
            text_color="#FFD6D6",
            command=self.stop_backup_action,
        )
        self.btn_stop.pack(side="right")

        return view

    # ============================================================
    #  ADIM 3: Tekrarları Temizle (Duplicate Cleanup)
    # ============================================================

    def build_step3_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(2, weight=1)
        view.grid_columnconfigure(0, weight=1)

        # Başlık
        hdr = ctk.CTkFrame(view, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(10, 16))
        self.dup_hdr = ctk.CTkLabel(hdr, text=t("dup_title"), font=FONT_HEAD, text_color=TEXT_WHITE)
        self.dup_hdr.pack(anchor="w")
        self.dup_sub_lbl = ctk.CTkLabel(hdr, text=t("dup_sub"), font=FONT_TEXT, text_color=TEXT_MUTED)
        self.dup_sub_lbl.pack(anchor="w", pady=(4, 0))

        # 4 İstatistik Kartı
        stats_frame = ctk.CTkFrame(view, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)

        self.tile_dup_cnt_val, self.tile_dup_cnt_lbl = self.build_dup_tile(stats_frame, 0, "🔄", PURPLE_DUP, "0", "dup_card_count")
        self.tile_dup_spc_val, self.tile_dup_spc_lbl = self.build_dup_tile(stats_frame, 1, "💾", INFO_BLUE, "0 MB", "dup_card_space")
        self.tile_dup_unq_val, self.tile_dup_unq_lbl = self.build_dup_tile(stats_frame, 2, "✨", OK_GREEN, "0", "dup_card_unique")
        self.tile_dup_tot_val, self.tile_dup_tot_lbl = self.build_dup_tile(stats_frame, 3, "📷", ACCENT_PINK, "0", "dup_card_total")

        # Tekrar Listesi Kartı
        list_container = ctk.CTkFrame(view, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        list_container.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
        list_container.grid_rowconfigure(1, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        list_top = ctk.CTkFrame(list_container, fg_color="transparent")
        list_top.grid(row=0, column=0, sticky="ew", padx=16, pady=12)

        ctk.CTkLabel(list_top, text=t("dup_found_title"), font=FONT_TITLE, text_color=TEXT_WHITE).pack(side="left")

        self.btn_rescan_dup = ctk.CTkButton(
            list_top,
            text=f"🔄 {t('btn_rescan_duplicates')}",
            font=FONT_SMALL,
            width=110,
            height=30,
            fg_color=CARD_BG_2,
            hover_color=CARD_BORDER,
            command=self.trigger_duplicate_scan,
        )
        self.btn_rescan_dup.pack(side="right")

        self.dup_scroll = ctk.CTkScrollableFrame(list_container, fg_color=BG_DARK, corner_radius=8)
        self.dup_scroll.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))

        # Alt Butonlar
        bot_bar = ctk.CTkFrame(view, fg_color="transparent")
        bot_bar.grid(row=3, column=0, sticky="ew")

        self.lbl_dup_selection_info = ctk.CTkLabel(bot_bar, text="", font=FONT_TEXT, text_color=TEXT_MUTED)
        self.lbl_dup_selection_info.pack(side="left")

        self.btn_del_dup = ctk.CTkButton(
            bot_bar,
            text=f"🗑 {t('btn_delete_duplicates')}",
            font=FONT_SUB,
            fg_color=ACCENT_PINK,
            hover_color=ACCENT_PINK_HOVER,
            height=38,
            corner_radius=8,
            command=self.delete_selected_duplicates,
        )
        self.btn_del_dup.pack(side="right")

        return view

    def build_dup_tile(self, parent, col: int, icon: str, color: str, initial_val: str, label_key: str):
        tile = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        tile.grid(row=0, column=col, sticky="ew", padx=4)

        icon_lbl = ctk.CTkLabel(tile, text=icon, font=("Segoe UI", 18), width=36, height=36, fg_color=CARD_BG_2, corner_radius=8)
        icon_lbl.pack(side="left", padx=10, pady=10)

        t_frame = ctk.CTkFrame(tile, fg_color="transparent")
        t_frame.pack(side="left", fill="both", expand=True, pady=8)

        v_lbl = ctk.CTkLabel(t_frame, text=initial_val, font=FONT_TITLE, text_color=TEXT_WHITE)
        v_lbl.pack(anchor="w")

        d_lbl = ctk.CTkLabel(t_frame, text=t(label_key), font=FONT_SMALL, text_color=TEXT_MUTED)
        d_lbl.pack(anchor="w")

        return v_lbl, d_lbl

    # ============================================================
    #  ADIM 4: Telefonda Temizle (Phone Cleanup)
    # ============================================================

    def build_step4_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)

        # Başlık
        hdr = ctk.CTkFrame(view, fg_color="transparent")
        hdr.pack(fill="x", pady=(10, 16))
        self.pclean_hdr = ctk.CTkLabel(hdr, text=t("phone_clean_title"), font=FONT_HEAD, text_color=TEXT_WHITE)
        self.pclean_hdr.pack(anchor="w")
        self.pclean_sub = ctk.CTkLabel(hdr, text=t("phone_clean_sub"), font=FONT_TEXT, text_color=TEXT_MUTED)
        self.pclean_sub.pack(anchor="w", pady=(4, 0))

        # Tarih Seçim Kartı
        date_card = ctk.CTkFrame(view, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        date_card.pack(fill="x", pady=(0, 14))

        d_top = ctk.CTkFrame(date_card, fg_color="transparent")
        d_top.pack(fill="x", padx=16, pady=14)

        cal_icon = ctk.CTkLabel(d_top, text="📅", font=("Segoe UI", 24), width=48, height=48, fg_color=CARD_BG_2, corner_radius=10)
        cal_icon.pack(side="left", padx=(0, 14))

        d_txt = ctk.CTkFrame(d_top, fg_color="transparent")
        d_txt.pack(side="left", fill="both")
        self.clean_date_lbl = ctk.CTkLabel(d_txt, text=t("clean_date_title"), font=FONT_SUB, text_color=TEXT_WHITE)
        self.clean_date_lbl.pack(anchor="w")
        self.clean_date_sub = ctk.CTkLabel(d_txt, text=t("clean_date_sub"), font=FONT_SMALL, text_color=TEXT_MUTED)
        self.clean_date_sub.pack(anchor="w")

        # Tarih Seçiciler (Yıl, Ay, Gün)
        picker_box = ctk.CTkFrame(d_top, fg_color="transparent")
        picker_box.pack(side="right")

        years = [str(y) for y in range(datetime.now().year, 2011, -1)]
        months = [f"{m:02d}" for m in range(1, 13)]

        self.menu_year = ctk.CTkOptionMenu(picker_box, values=years, variable=self.cleanup_year, width=85, height=32, fg_color=CARD_BG_2, button_color=CARD_BORDER, command=lambda _v: self.update_cleanup_days())
        self.menu_year.pack(side="left", padx=4)

        self.menu_month = ctk.CTkOptionMenu(picker_box, values=months, variable=self.cleanup_month, width=70, height=32, fg_color=CARD_BG_2, button_color=CARD_BORDER, command=lambda _v: self.update_cleanup_days())
        self.menu_month.pack(side="left", padx=4)

        self.menu_day = ctk.CTkOptionMenu(picker_box, values=[f"{d:02d}" for d in range(1, 32)], variable=self.cleanup_day, width=70, height=32, fg_color=CARD_BG_2, button_color=CARD_BORDER)
        self.menu_day.pack(side="left", padx=4)

        self.btn_find_clean = ctk.CTkButton(
            picker_box,
            text=t("btn_find_phone_cleanup"),
            font=FONT_SUB,
            width=140,
            height=32,
            fg_color=ACCENT_PINK,
            hover_color=ACCENT_PINK_HOVER,
            command=self.trigger_phone_cleanup_scan,
        )
        self.btn_find_clean.pack(side="left", padx=(10, 0))

        # Silinecek Medya Özeti
        self.media_summary_card = ctk.CTkFrame(view, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=CARD_BORDER)
        self.media_summary_card.pack(fill="x", pady=(0, 14))

        m_top = ctk.CTkFrame(self.media_summary_card, fg_color="transparent")
        m_top.pack(fill="x", padx=16, pady=12)

        trash_icon = ctk.CTkLabel(m_top, text="🗑️", font=("Segoe UI", 24), width=48, height=48, fg_color=CARD_BG_2, corner_radius=10)
        trash_icon.pack(side="left", padx=(0, 14))

        m_info = ctk.CTkFrame(m_top, fg_color="transparent")
        m_info.pack(side="left", fill="both")
        ctk.CTkLabel(m_info, text=t("media_to_delete"), font=FONT_TITLE, text_color=TEXT_WHITE).pack(anchor="w")
        self.lbl_clean_summary = ctk.CTkLabel(m_info, text="0 Fotoğraf  |  0 Video  |  Toplam: 0", font=FONT_SUB, text_color=TEXT_MUTED)
        self.lbl_clean_summary.pack(anchor="w")

        # Uyarı Kutusu (Sarı İkaz)
        warn_card = ctk.CTkFrame(view, fg_color="#1E1A11", corner_radius=10, border_width=1, border_color="#523E15")
        warn_card.pack(fill="x", pady=(0, 20))

        w_inner = ctk.CTkFrame(warn_card, fg_color="transparent")
        w_inner.pack(fill="x", padx=16, pady=14)

        warn_icon = ctk.CTkLabel(w_inner, text="⚠️", font=("Segoe UI", 22), text_color=WARN_YELLOW)
        warn_icon.pack(side="left", anchor="n", padx=(0, 12))

        w_text = ctk.CTkFrame(w_inner, fg_color="transparent")
        w_text.pack(side="left", fill="both", expand=True)

        self.lbl_warn_hdr = ctk.CTkLabel(w_text, text=t("warning_title"), font=FONT_SUB, text_color=WARN_YELLOW)
        self.lbl_warn_hdr.pack(anchor="w")

        self.lbl_warn_1 = ctk.CTkLabel(w_text, text=t("warning_bullet_1"), font=FONT_SMALL, text_color="#E2D4B3")
        self.lbl_warn_1.pack(anchor="w", pady=(2, 0))
        self.lbl_warn_2 = ctk.CTkLabel(w_text, text=t("warning_bullet_2"), font=FONT_SMALL, text_color="#E2D4B3")
        self.lbl_warn_2.pack(anchor="w")
        self.lbl_warn_3 = ctk.CTkLabel(w_text, text=t("warning_bullet_3"), font=FONT_SMALL, text_color="#E2D4B3")
        self.lbl_warn_3.pack(anchor="w")

        # Alt Butonlar
        p_bot = ctk.CTkFrame(view, fg_color="transparent")
        p_bot.pack(fill="x")

        self.btn_back_to_3 = ctk.CTkButton(
            p_bot,
            text=f"← {t('btn_back')}",
            font=FONT_SUB,
            width=100,
            height=38,
            fg_color=CARD_BG,
            hover_color=CARD_BG_2,
            command=lambda: self.show_step(3),
        )
        self.btn_back_to_3.pack(side="left")

        self.btn_start_clean = ctk.CTkButton(
            p_bot,
            text=f"🗑 {t('btn_start_phone_clean')}",
            font=FONT_SUB,
            width=220,
            height=40,
            fg_color=DANGER_RED,
            hover_color="#DC2626",
            command=self.trigger_phone_cleanup_delete,
            state="disabled",
        )
        self.btn_start_clean.pack(side="right")

        return view

    def update_cleanup_days(self):
        try:
            year = int(self.cleanup_year.get())
            month = int(self.cleanup_month.get())
        except ValueError:
            return
        max_day = calendar.monthrange(year, month)[1]
        values = [f"{day:02d}" for day in range(1, max_day + 1)]
        self.menu_day.configure(values=values)
        if self.cleanup_day.get() not in values:
            self.cleanup_day.set(values[-1])

    # ============================================================
    #  Yardımcı İşlemler & İletişim Fonksiyonları
    # ============================================================

    def run_adb(self, args: list[str], timeout: int = 40, text: bool = True) -> subprocess.CompletedProcess:
        cmd = [ADB_PATH] + args
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            timeout=timeout,
            creationflags=creation_flags(),
        )

    def select_target_disk(self):
        p = filedialog.askdirectory(title=t("card_target_folder"))
        if p:
            self.target_path.set(p)
            self.dst_name_lbl.configure(text=p)
            self.disk_index_cache = None
            self.disk_index_target = ""

    def open_target_disk(self):
        target = self.target_path.get().strip()
        if target and os.path.exists(target):
            try:
                os.startfile(target)
            except Exception:
                pass

    def test_device_action(self):
        if self.is_ios_mode():
            devs = ios_manager.list_ios_devices()
            if devs:
                self.set_device_connected_ui(True, devs[0])
                messagebox.showinfo("iOS", f"Apple iPhone / iPad:\n{devs[0]}")
            else:
                self.set_device_connected_ui(False, "Apple iPhone")
                messagebox.showwarning(
                    "iOS",
                    "Apple iPhone bulunamadı.\n\n"
                    "1. USB kablosunu kontrol edin.\n"
                    "2. Telefon ekran kilidini açın.\n"
                    "3. 'Bu Bilgisayara Güven' onayını verin.",
                )
        else:
            try:
                res = self.run_adb(["devices"], timeout=10)
                lines = [x.strip() for x in res.stdout.splitlines() if x.strip()]
                devs = [x for x in lines[1:] if "\tdevice" in x]
                if devs:
                    self.detect_android_device()
                    messagebox.showinfo("Android", f"Cihaz Hazır:\n{devs[0]}")
                else:
                    self.set_device_connected_ui(False, "Android")
                    messagebox.showwarning(
                        "Android",
                        "Android cihaz bulunamadı.\n\n"
                        "1. USB Hata Ayıklama modunu açın.\n"
                        "2. Telefonda çıkan izni onaylayın.",
                    )
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def show_about_dialog(self):
        messagebox.showinfo(t("about_title"), t("about_desc"))

    # ============================================================
    #  Tarama Mantığı (Scan Logic)
    # ============================================================

    def clear_analysis_ui(self):
        for frame in (self.folder_scroll, self.gallery_scroll):
            for child in frame.winfo_children():
                child.destroy()
        self.media_items.clear()
        self.filtered_items.clear()
        self.sync_plan.clear()
        self.folder_vars.clear()
        self.item_select_vars.clear()
        self.thumb_refs.clear()
        self.thumb_cache.clear()
        self.gallery_offset = 0

        self.tile_total_val.configure(text="0")
        self.tile_new_val.configure(text="0")
        self.tile_ondisk_val.configure(text="0")
        self.tile_dup_val.configure(text="0")
        self.lbl_footer_status.configure(text="")
        self.btn_load_more.configure(state="disabled")

    def trigger_scan(self):
        if self.is_busy:
            return
        target = self.target_path.get().strip()
        if not target:
            messagebox.showwarning("Hedef Seçilmedi", t("card_target_folder_sub"))
            self.select_target_disk()
            target = self.target_path.get().strip()
            if not target:
                return

        source = self.source_path.get().strip()
        self.clear_analysis_ui()
        self.is_busy = True
        self.btn_scan_main.configure(state="disabled", text=t("scanning"))
        self.lbl_gallery_sub.configure(text=t("scanning"))
        threading.Thread(target=self.scan_worker, args=(source, target), daemon=True).start()

    def scan_worker(self, source: str, target: str):
        try:
            existing = self.cached_local_index(target)

            if self.is_ios_mode():
                devs = ios_manager.list_ios_devices()
                dev_name = devs[0] if devs else ""
                raw_items = ios_manager.scan_ios_media(device_name=dev_name)
                if not raw_items:
                    self.after(0, lambda: self.scan_finished_error("iPhone'da fotoğraf bulunamadı. Ekran kilidini açıp güven onayını verin."))
                    return

                items: list[MediaItem] = []
                for raw in raw_items:
                    safe_rel = sanitize_rel_path(raw["rel_path"])
                    name = raw["name"]
                    lower = name.lower()
                    safe_rel_lower = safe_rel.lower()
                    name_lower = name.lower()
                    size = raw["size"]

                    exists = False
                    if safe_rel_lower in existing["path_sizes"]:
                        local_size = existing["path_sizes"][safe_rel_lower]
                        exists = (local_size == size) if size is not None else (local_size > 0)
                    elif name_lower in existing.get("name_entries", {}):
                        for local_rel, local_size in existing["name_entries"][name_lower]:
                            if local_size <= 0:
                                continue
                            if size is not None:
                                if local_size == size:
                                    exists = True
                                    break
                            elif safe_rel_lower.endswith(local_rel) or local_rel.endswith(name_lower):
                                exists = True
                                break

                    kind = "image" if lower.endswith(IMAGE_EXTS) else "video"
                    items.append(MediaItem(
                        remote_path=raw["remote_path"],
                        rel_path=safe_rel,
                        file_name=name,
                        folder=raw["folder"],
                        size=size,
                        kind=kind,
                        exists_locally=exists,
                        path_parts=raw["path_parts"],
                        cleanup_ts=raw["modify_ts"],
                    ))
            else:
                items = self.get_phone_media_android(source, existing)

            if not items:
                self.after(0, lambda: self.scan_finished_error("Telefonda fotoğraf veya video bulunamadı."))
                return

            plan: dict[str, list[MediaItem]] = {}
            for item in items:
                if not item.exists_locally:
                    plan.setdefault(item.folder, []).append(item)

            self.after(0, lambda: self.scan_success(items, plan))
        except Exception as e:
            self.after(0, lambda err=e: self.scan_finished_error(str(err)))

    def scan_finished_error(self, message: str):
        self.is_busy = False
        self.btn_scan_main.configure(state="normal", text=t("btn_scan"))
        self.lbl_gallery_sub.configure(text=message)
        messagebox.showerror("Tarama Hatası", message)

    def scan_success(self, items: list[MediaItem], plan: dict[str, list[MediaItem]]):
        self.is_busy = False
        self.media_items = items
        self.filtered_items = list(items)
        self.sync_plan = plan

        total = len(items)
        new_cnt = sum(1 for it in items if not it.exists_locally)
        ondisk_cnt = total - new_cnt

        self.tile_total_val.configure(text=f"{total:,}")
        self.tile_new_val.configure(text=f"{new_cnt:,}")
        self.tile_ondisk_val.configure(text=f"{ondisk_cnt:,}")
        self.lbl_footer_status.configure(text=t("files_found", count=f"{total:,}"))

        self.btn_scan_main.configure(state="normal", text=t("btn_scan_again"))
        self.lbl_gallery_sub.configure(text=t("files_found", count=f"{total:,}"))

        self.render_folders_list()
        self.render_gallery_cards(reset=True)

    def render_folders_list(self):
        for child in self.folder_scroll.winfo_children():
            child.destroy()

        # "Tümü" satırı
        all_row = ctk.CTkFrame(self.folder_scroll, fg_color=CARD_BG_2, corner_radius=6, height=36, cursor="hand2")
        all_row.pack(fill="x", pady=3)
        all_row.pack_propagate(False)

        ctk.CTkLabel(all_row, text=t("all_folders"), font=FONT_SUB, text_color=TEXT_WHITE).pack(side="left", padx=10)
        ctk.CTkLabel(all_row, text=str(len(self.media_items)), font=FONT_SMALL, text_color=ACCENT_PINK).pack(side="right", padx=10)
        all_row.bind("<Button-1>", lambda _e: self.filter_by_folder(""))

        # Klasör bazlı gruplar
        folder_counts = {}
        for it in self.media_items:
            folder_counts[it.folder] = folder_counts.get(it.folder, 0) + 1

        for f_name, count in sorted(folder_counts.items(), key=lambda x: x[0].lower()):
            f_row = ctk.CTkFrame(self.folder_scroll, fg_color="transparent", corner_radius=6, height=32, cursor="hand2")
            f_row.pack(fill="x", pady=2)
            f_row.pack_propagate(False)

            short_name = f_name.split("/")[-1] or f_name
            if len(short_name) > 16:
                short_name = short_name[:14] + ".."

            lbl_n = ctk.CTkLabel(f_row, text=short_name, font=FONT_TEXT, text_color=TEXT_WHITE)
            lbl_n.pack(side="left", padx=10)

            lbl_c = ctk.CTkLabel(f_row, text=str(count), font=FONT_SMALL, text_color=TEXT_MUTED)
            lbl_c.pack(side="right", padx=10)

            for w in (f_row, lbl_n, lbl_c):
                w.bind("<Button-1>", lambda _e, folder=f_name: self.filter_by_folder(folder))

    def filter_by_folder(self, folder: str):
        if not folder:
            self.filtered_items = list(self.media_items)
        else:
            self.filtered_items = [it for it in self.media_items if it.folder == folder or it.folder.startswith(folder)]
        self.render_gallery_cards(reset=True)

    def apply_filter(self):
        q = self.search_text.get().strip().lower()
        if not q:
            self.filtered_items = list(self.media_items)
        else:
            self.filtered_items = [
                it for it in self.media_items
                if q in it.file_name.lower() or q in it.folder.lower()
            ]
        self.render_gallery_cards(reset=True)

    def render_gallery_cards(self, reset=True):
        if reset:
            for child in self.gallery_scroll.winfo_children():
                child.destroy()
            self.gallery_offset = 0
            self.thumb_refs.clear()

        if not self.filtered_items:
            ctk.CTkLabel(self.gallery_scroll, text="Medya bulunamadı.", font=FONT_TEXT, text_color=TEXT_MUTED).pack(pady=40)
            self.btn_load_more.configure(state="disabled")
            return

        start = self.gallery_offset
        end = min(start + MAX_THUMBNAILS_PER_BATCH, len(self.filtered_items))
        batch = self.filtered_items[start:end]

        cols = 5
        for i in range(cols):
            self.gallery_scroll.grid_columnconfigure(i, weight=1)

        for idx, item in enumerate(batch, start=start):
            r = idx // cols
            c = idx % cols
            self.create_thumb_card(item, r, c)

        self.gallery_offset = end
        if self.gallery_offset < len(self.filtered_items):
            self.btn_load_more.configure(state="normal")
        else:
            self.btn_load_more.configure(state="disabled")

        threading.Thread(target=self.load_thumbs_batch, args=(batch,), daemon=True).start()

    def load_more_gallery(self):
        self.render_gallery_cards(reset=False)

    def create_thumb_card(self, item: MediaItem, row: int, col: int):
        card = ctk.CTkFrame(self.gallery_scroll, fg_color=CARD_BG, corner_radius=8, width=130, height=160)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="n")
        card.grid_propagate(False)

        # Önizleme Görseli
        thumb_lbl = ctk.CTkLabel(card, text="VIDEO" if item.kind == "video" else "PHOTO", font=FONT_SMALL, text_color=TEXT_MUTED, width=118, height=110, fg_color=BG_DARK, corner_radius=6)
        thumb_lbl.pack(padx=6, pady=(6, 4))

        # Checkbox & Durum
        bot_box = ctk.CTkFrame(card, fg_color="transparent")
        bot_box.pack(fill="x", padx=6)

        is_new = not item.exists_locally
        status_text = t("new_label") if is_new else t("on_disk_label")
        status_color = OK_GREEN if is_new else TEXT_MUTED

        ctk.CTkLabel(bot_box, text=status_text, font=FONT_SMALL, text_color=status_color).pack(side="left")

        # Dosya adı
        name_short = item.file_name if len(item.file_name) <= 14 else item.file_name[:11] + "..."
        ctk.CTkLabel(card, text=name_short, font=FONT_SMALL, text_color=TEXT_WHITE).pack(anchor="w", padx=6)

        item._thumb_widget = thumb_lbl

    def load_thumbs_batch(self, batch: list[MediaItem]):
        for it in batch:
            if it.kind != "image":
                continue
            try:
                local_path = self.get_preview_file(it)
                if not local_path or not local_path.exists():
                    continue

                img = Image.open(local_path)
                img.thumbnail(THUMB_SIZE)
                photo = ImageTk.PhotoImage(img)

                self.thumb_refs[it.remote_path] = photo
                widget = getattr(it, "_thumb_widget", None)
                if widget:
                    self.after(0, lambda w=widget, p=photo: w.configure(image=p, text=""))
            except Exception:
                continue

    def get_preview_file(self, item: MediaItem) -> Path | None:
        if item.remote_path in self.thumb_cache:
            return self.thumb_cache[item.remote_path]

        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", item.file_name)
        local = self.temp_dir / f"{abs(hash(item.remote_path))}_{safe_name}"

        if local.exists() and local.stat().st_size > 0:
            self.thumb_cache[item.remote_path] = local
            return local

        if item.remote_path.startswith("ios://"):
            success, _err = ios_manager.copy_ios_file(item.path_parts or [], local, timeout=30)
            if success and local.exists() and local.stat().st_size > 0:
                self.thumb_cache[item.remote_path] = local
                return local
            return None

        # Android ADB
        res = self.run_adb(["pull", item.remote_path, str(local)], timeout=40)
        if res.returncode == 0 and local.exists() and local.stat().st_size > 0:
            self.thumb_cache[item.remote_path] = local
            return local

        return None

    # ============================================================
    #  Yedekleme Mantığı (Backup Operations)
    # ============================================================

    def go_to_backup_step(self):
        target = self.target_path.get().strip()
        if not target:
            messagebox.showwarning("Hedef Seçilmedi", t("card_target_folder_sub"))
            self.select_target_disk()
            target = self.target_path.get().strip()
            if not target:
                return

        new_items = [it for it in self.media_items if not it.exists_locally]
        if not new_items:
            messagebox.showinfo("Yedeklenecek Yeni Dosya Yok", "Tüm fotoğraflarınız zaten yerel diskinizde mevcut!")
            return

        self.show_step(2)
        self.start_backup_process(new_items, target)

    def start_backup_process(self, items: list[MediaItem], target: str):
        if self.is_busy:
            return

        self.is_busy = True
        self.stop_requested = False
        self.pause_requested = False

        self.dst_name_lbl.configure(text=target)
        self.src_name_lbl.configure(text=self.connected_device_info or "Telefon")
        self.backup_progress_bar.set(0)
        self.backup_pct_label.configure(text="%0")
        self.backup_status_text.configure(text=t("backup_progress_text", copied=0, total=len(items)))

        threading.Thread(target=self.backup_worker_task, args=(items, target), daemon=True).start()

    def toggle_pause_backup(self):
        self.pause_requested = not self.pause_requested
        if self.pause_requested:
            self.btn_pause.configure(text=f"▶ {t('btn_resume')}")
            self.backup_status_text.configure(text="Yedekleme duraklatıldı.")
        else:
            self.btn_pause.configure(text=f"⏸ {t('btn_pause')}")
            self.backup_status_text.configure(text="Yedekleme devam ediyor...")

    def stop_backup_action(self):
        self.stop_requested = True
        self.btn_stop.configure(state="disabled")
        self.backup_status_text.configure(text=t("backup_stopped"))

    def backup_worker_task(self, items: list[MediaItem], target: str):
        target_path = Path(target)
        total = len(items)
        copied = 0
        failed = 0
        failed_files = []

        start_time = time.time()

        for idx, item in enumerate(items, start=1):
            if self.stop_requested:
                break

            while self.pause_requested:
                time.sleep(0.3)
                if self.stop_requested:
                    break

            local_file = to_windows_safe_path(target_path / item.rel_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Arayüzü anlık güncelle
            self.after(0, lambda n=item.file_name, s=format_size(item.size): (
                self.cur_file_name.configure(text=n),
                self.cur_file_size.configure(text=s)
            ))

            if item.remote_path.startswith("ios://"):
                success, err = ios_manager.copy_ios_file(item.path_parts or [], local_file, timeout=180)
            else:
                res = self.run_adb(["pull", item.remote_path, str(local_file)], timeout=180)
                success = (res.returncode == 0 and local_file.exists() and local_file.stat().st_size > 0)
                err = res.stderr or "Hata"

            if success:
                copied += 1
                item.exists_locally = True
            else:
                failed += 1
                failed_files.append((item.file_name, err))

            pct = copied / total
            elapsed = time.time() - start_time
            if copied > 0:
                speed = copied / elapsed
                rem_seconds = int((total - copied) / speed)
                rem_str = f"~{rem_seconds // 60} dk {rem_seconds % 60} sn"
            else:
                rem_str = "..."

            self.after(0, lambda p=pct, c=copied, t_cnt=total, rem=rem_str: (
                self.backup_progress_bar.set(p),
                self.backup_pct_label.configure(text=f"%{int(p * 100)}"),
                self.backup_status_text.configure(text=t("backup_progress_text", copied=c, total=t_cnt)),
                self.lbl_time_remaining.configure(text=t("time_remaining", time=rem)),
            ))

        self.is_busy = False
        self.after(0, lambda: self.backup_completed_ui(copied, failed, failed_files))

    def backup_completed_ui(self, copied: int, failed: int, failed_files: list):
        self.btn_stop.configure(state="normal")
        self.backup_progress_bar.set(1)
        self.backup_pct_label.configure(text="%100")
        self.backup_status_text.configure(text=t("backup_completed"))
        self.lbl_time_remaining.configure(text=f"Başarılı: {copied}  |  Hatalı: {failed}")

        messagebox.showinfo("Yedekleme", f"Yedekleme işlemi tamamlandı!\n\nKopyalanan: {copied}\nBaşarısız: {failed}")

    # ============================================================
    #  ADIM 3: Tekrar Eden Dosyalar (Duplicate Cleaner)
    # ============================================================

    def trigger_duplicate_scan(self):
        target = self.target_path.get().strip()
        if not target or not os.path.exists(target):
            messagebox.showwarning("Hedef Bulunamadı", "Lütfen önce geçerli bir disk klasörü seçin.")
            return

        for child in self.dup_scroll.winfo_children():
            child.destroy()
        self.btn_rescan_dup.configure(state="disabled")
        threading.Thread(target=self.duplicate_scan_worker, args=(target,), daemon=True).start()

    def duplicate_scan_worker(self, target: str):
        target_path = Path(target)
        groups: dict[tuple[str, int], list[Path]] = {}
        total_files = 0
        total_bytes = 0

        for root, _dirs, files in os.walk(target_path):
            for f in files:
                full = Path(root) / f
                try:
                    sz = full.stat().st_size
                    if sz > 0:
                        groups.setdefault((f.lower(), sz), []).append(full)
                        total_files += 1
                        total_bytes += sz
                except OSError:
                    continue

        duplicates_found = []
        recoverable_bytes = 0

        for (name, sz), paths in groups.items():
            if len(paths) > 1:
                # 1. dosya orijinal kabul edilir, diğerleri tekrar
                recoverable_bytes += sz * (len(paths) - 1)
                duplicates_found.append((name, sz, paths[0], paths[1:]))

        unique_count = total_files - sum(len(dup[3]) for dup in duplicates_found)

        self.after(0, lambda: self.render_duplicates_ui(duplicates_found, recoverable_bytes, unique_count, total_files))

    def render_duplicates_ui(self, duplicates: list, rec_bytes: int, unique_cnt: int, total_cnt: int):
        self.btn_rescan_dup.configure(state="normal")
        self.tile_dup_cnt_val.configure(text=str(len(duplicates)))
        self.tile_dup_spc_val.configure(text=format_size(rec_bytes))
        self.tile_dup_unq_val.configure(text=f"{unique_cnt:,}")
        self.tile_dup_tot_val.configure(text=f"{total_cnt:,}")

        self.dup_delete_candidates = []
        for name, sz, orig_p, dup_paths in duplicates:
            card = ctk.CTkFrame(self.dup_scroll, fg_color=CARD_BG_2, corner_radius=8, border_width=1, border_color=CARD_BORDER)
            card.pack(fill="x", padx=6, pady=4)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(top_row, text=f"📄 {name}", font=FONT_SUB, text_color=TEXT_WHITE).pack(side="left")
            ctk.CTkLabel(top_row, text=format_size(sz), font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="right")

            # Orijinal satırı
            orig_row = ctk.CTkFrame(card, fg_color="transparent")
            orig_row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(orig_row, text=t("tag_original"), font=FONT_SMALL, text_color=OK_GREEN, fg_color=BG_DARK, corner_radius=4, width=54).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(orig_row, text=str(orig_p), font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="left")

            # Tekrar eden satırlar
            for d_p in dup_paths:
                dup_row = ctk.CTkFrame(card, fg_color="transparent")
                dup_row.pack(fill="x", padx=10, pady=2)
                ctk.CTkLabel(dup_row, text=t("tag_duplicate"), font=FONT_SMALL, text_color=DANGER_RED, fg_color=BG_DARK, corner_radius=4, width=54).pack(side="left", padx=(0, 8))
                ctk.CTkLabel(dup_row, text=str(d_p), font=FONT_SMALL, text_color=TEXT_WHITE).pack(side="left")
                self.dup_delete_candidates.append(d_p)

        self.lbl_dup_selection_info.configure(text=t("dup_selected_info", count=len(self.dup_delete_candidates), size=format_size(rec_bytes)))

    def delete_selected_duplicates(self):
        if not getattr(self, "dup_delete_candidates", None):
            messagebox.showinfo("Seçim Yok", "Silinecek tekrar eden dosya bulunamadı.")
            return

        cnt = len(self.dup_delete_candidates)
        if not messagebox.askyesno("Onay", f"{cnt} adet mükerrer dosya diskten silinecektir.\n\nDevam etmek istiyor musunuz?"):
            return

        deleted = 0
        for p in self.dup_delete_candidates:
            try:
                p.unlink()
                deleted += 1
            except Exception:
                pass

        messagebox.showinfo("Temizlik", f"{deleted} adet mükerrer dosya başarıyla silindi.")
        self.trigger_duplicate_scan()

    # ============================================================
    #  ADIM 4: Telefondan Temizleme (Phone Cleanup)
    # ============================================================

    def trigger_phone_cleanup_scan(self):
        cutoff_date = f"{self.cleanup_year.get()}-{self.cleanup_month.get()}-{self.cleanup_day.get()}"
        try:
            cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%d")
            cutoff_ts = cutoff_dt.timestamp()
        except ValueError:
            messagebox.showerror("Hata", "Geçersiz tarih formatı.")
            return

        target = self.target_path.get().strip()
        if not target or not os.path.exists(target):
            messagebox.showwarning("Hedef Eksik", "Lütfen önce disk yedekleme klasörünü seçin.")
            return

        self.phone_cleanup_candidates.clear()
        self.btn_start_clean.configure(state="disabled")
        threading.Thread(target=self.phone_clean_scan_worker, args=(target, cutoff_ts), daemon=True).start()

    def phone_clean_scan_worker(self, target: str, cutoff_ts: float):
        existing = self.cached_local_index(target)
        candidates = []

        for item in self.media_items:
            if not item.exists_locally:
                continue

            ts = item.cleanup_ts
            if ts is None:
                # İsimden tarih çıkarma denemesi
                m = re.search(r"(20\d{2})[-_.]?([01]\d)[-_.]?([0-3]\d)", item.file_name)
                if m:
                    try:
                        ts = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).timestamp()
                    except Exception:
                        pass

            if ts and ts <= cutoff_ts:
                candidates.append(item)

        self.phone_cleanup_candidates = candidates
        img_c = sum(1 for it in candidates if it.kind == "image")
        vid_c = len(candidates) - img_c

        self.after(0, lambda: self.render_phone_clean_results(img_c, vid_c, len(candidates)))

    def render_phone_clean_results(self, images: int, videos: int, total: int):
        self.lbl_clean_summary.configure(text=f"{images} Fotoğraf  |  {videos} Video  |  Toplam: {total}")
        if total > 0:
            self.btn_start_clean.configure(state="normal")
        else:
            self.btn_start_clean.configure(state="disabled")
            messagebox.showinfo("Bilgi", "Seçilen tarihe kadar yedeklenmiş silinebilecek medya bulunamadı.")

    def trigger_phone_cleanup_delete(self):
        if not self.phone_cleanup_candidates:
            return

        cnt = len(self.phone_cleanup_candidates)
        if not messagebox.askyesno(
            "Telefondan Silme Onayı",
            f"DİKKAT: Bu işlem telefonunuzdaki {cnt} adet medyayı KALICI OLARAK SİLECEKTİR.\n\n"
            "Bu dosyalar daha önce bilgisayarınıza yedeklenmiştir.\n\n"
            "Silme işlemini başlatmak istiyor musunuz?"
        ):
            return

        self.btn_start_clean.configure(state="disabled")
        threading.Thread(target=self.phone_cleanup_delete_worker, daemon=True).start()

    def phone_cleanup_delete_worker(self):
        deleted = 0
        failed = 0

        for it in self.phone_cleanup_candidates:
            if it.remote_path.startswith("ios://"):
                success, _err = ios_manager.delete_ios_file(it.path_parts or [])
            else:
                res = self.run_adb(["shell", f"rm -f {shell_quote(it.remote_path)}"], timeout=30)
                success = (res.returncode == 0)

            if success:
                deleted += 1
            else:
                failed += 1

        self.after(0, lambda: self.phone_cleanup_done_ui(deleted, failed))

    def phone_cleanup_done_ui(self, deleted: int, failed: int):
        self.phone_cleanup_candidates.clear()
        self.btn_start_clean.configure(state="disabled")
        messagebox.showinfo("Silme Tamamlandı", f"Telefondan silinen dosya: {deleted}\nBaşarısız: {failed}")

    # ============================================================
    #  Yardımcı Yerel Dizin İndeksi & Android Tarama
    # ============================================================

    def cached_local_index(self, target: str) -> dict[str, any]:
        norm = str(Path(target).resolve()).lower()
        if self.disk_index_cache is not None and self.disk_index_target == norm:
            return self.disk_index_cache

        idx = {"path_sizes": {}, "paths": set(), "names": set(), "name_entries": {}}
        t_path = Path(target)
        if t_path.exists():
            for root, _dirs, files in os.walk(t_path):
                for name in files:
                    try:
                        full = Path(root) / name
                        rel = full.relative_to(t_path).as_posix().lower()
                        sz = full.stat().st_size
                        idx["path_sizes"][rel] = sz
                        idx["paths"].add(rel)
                        n_lower = name.lower()
                        idx["names"].add(n_lower)
                        idx["name_entries"].setdefault(n_lower, []).append((rel, sz))
                    except OSError:
                        continue

        self.disk_index_cache = idx
        self.disk_index_target = norm
        return idx

    def get_phone_media_android(self, source: str, existing: dict[str, any]) -> list[MediaItem]:
        # MediaStore sorgusu
        cmd = ["shell", "content", "query", "--uri", "content://media/external/file", "--projection", "_data:_size"]
        res = self.run_adb(cmd, timeout=45)
        raw_rows = []

        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                if "_data=" not in line:
                    continue
                m = re.search(r"_data=(.+?)(?:,\s*_size=|$)", line)
                if m:
                    p = m.group(1).strip()
                    sz = None
                    sm = re.search(r"_size=(\d+)", line)
                    if sm:
                        try:
                            sz = int(sm.group(1))
                        except Exception:
                            pass
                    raw_rows.append((p, sz))

        # Fallback find
        if not raw_rows:
            patterns = " -o ".join([f"-iname '*{ext}'" for ext in MEDIA_EXTS])
            cmd_f = f"find {shell_quote(source)} -type f \\( {patterns} \\) 2>/dev/null"
            res_f = self.run_adb(["shell", cmd_f], timeout=90)
            if res_f.returncode == 0 and res_f.stdout.strip():
                for line in res_f.stdout.splitlines():
                    if line.strip():
                        raw_rows.append((line.strip(), None))

        items: list[MediaItem] = []
        seen = set()

        for remote_p, sz in raw_rows:
            lower = remote_p.lower()
            if lower in seen or not lower.endswith(MEDIA_EXTS):
                continue
            seen.add(lower)

            rel = re.sub(r"^/storage/emulated/0", "", remote_p)
            rel = re.sub(r"^/sdcard", "", rel).lstrip("/")
            safe_rel = sanitize_rel_path(rel)
            name = remote_p.split("/")[-1]
            folder = os.path.dirname(safe_rel).replace("\\", "/") or "Root"
            kind = "image" if lower.endswith(IMAGE_EXTS) else "video"

            safe_rel_lower = safe_rel.lower()
            name_lower = name.lower()

            exists = False
            if safe_rel_lower in existing["path_sizes"]:
                loc_sz = existing["path_sizes"][safe_rel_lower]
                exists = (loc_sz == sz) if sz is not None else (loc_sz > 0)
            elif name_lower in existing.get("name_entries", {}):
                for local_rel, local_size in existing["name_entries"][name_lower]:
                    if local_size <= 0:
                        continue
                    if sz is not None:
                        if local_size == sz:
                            exists = True
                            break
                    elif safe_rel_lower.endswith(local_rel) or local_rel.endswith(name_lower):
                        exists = True
                        break

            items.append(MediaItem(
                remote_path=remote_p,
                rel_path=safe_rel,
                file_name=name,
                folder=folder,
                size=sz,
                kind=kind,
                exists_locally=exists,
            ))

        return items

    def on_close(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
        self.destroy()


# ============================================================
#  Giriş Noktası
# ============================================================

def main():
    app = PhotoMatchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
