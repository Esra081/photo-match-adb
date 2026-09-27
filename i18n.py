"""
PhotoMatch - Çok Dilli Destek (i18n) Modülü
Türkçe (TR), English (EN), Deutsch (DE), Español (ES) destekler.
"""

import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".photomatch_config.json"

LANGUAGES = {
    "tr": "🇹🇷 Türkçe",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
    "es": "🇪🇸 Español",
}

TRANSLATIONS = {
    "tr": {
        # Genel & Başlıklar
        "app_title": "PhotoMatch | Android & iPhone -> Disk Backup",
        "app_subtitle": "Android & iPhone -> Disk Backup",
        "device_android": "📱 Android (ADB)",
        "device_ios": "🍏 Apple iPhone (iOS)",
        "ready": "Hazır",
        "about": "Hakkında",
        "about_title": "PhotoMatch Hakkında",
        "about_desc": "PhotoMatch, Android ve Apple iPhone cihazlarınızdaki fotoğraf ve videoları bilgisayarınıza aktaran, kopyalananları telefonunuzdan güvenle temizleyen ve diskteki çift dosyaları ayıklayan modern bir yedekleme aracıdır.\n\nSürüm: 2.0 Pro\nGeliştirici: Esra",
        
        # Sidebar Adımları
        "step_1_title": "Fotoğrafları Tara",
        "step_1_sub": "Telefondaki fotoğrafları bul",
        "step_2_title": "Yedekle",
        "step_2_sub": "Fotoğrafları diske kopyala",
        "step_3_title": "Tekrarları Temizle",
        "step_3_sub": "Diskteki tekrarları kontrol et",
        "step_4_title": "Telefonda Temizle",
        "step_4_sub": "Belirli tarihe kadar olanları sil",

        # Adım 1: Tarama & Galeri
        "card_device_connected": "Cihaz Durumu",
        "card_device_none": "Cihaz Bağlı Değil",
        "btn_test_device": "Cihazı Test Et",
        "card_phone_folder": "Telefon Klasörü",
        "card_phone_folder_sub": "Telefonda taranacak klasörü seç",
        "card_target_folder": "Yedekleme Klasörü",
        "card_target_folder_sub": "Fotoğrafların kaydedileceği diski seç",
        "btn_browse": "Gözat",
        "btn_scan": "Fotoğrafları Tara",
        "btn_scan_again": "Yeniden Tara",
        "scanning": "Taranıyor...",
        
        "folders_title": "Klasörler",
        "all_folders": "Tümü",
        "gallery_title": "Telefon Galerisi Önizleme",
        "gallery_sub": "Telefondaki fotoğraflar taranıyor...",
        "gallery_search_placeholder": "Fotoğraf ara...",
        "btn_filter": "Filtrele",
        "btn_load_more": "Daha Fazla Yükle →",
        "btn_go_backup": "Seçilenleri Yedekle →",
        
        "summary_title": "Tarama Özeti",
        "stat_total_media": "Toplam Medya",
        "stat_new_photos": "Yeni Fotoğraf",
        "stat_on_disk": "Diskte Zaten Var",
        "stat_duplicates": "Tekrar (Aynı Dosyalar)",
        "files_found": "{count} fotoğraf ve video bulundu.",
        "on_disk_label": "Diskte Var",
        "new_label": "Yeni",

        # Adım 2: Yedekleme
        "backup_running_title": "Fotoğraflar Diske Yedekleniyor",
        "backup_running_sub": "Seçilen fotoğraflar güvenli bir şekilde diske kopyalanıyor.",
        "backup_source": "Kaynak",
        "backup_target": "Hedef",
        "btn_open_folder": "Klasörü Aç",
        "backup_progress_text": "{copied} / {total} fotoğraf kopyalanıyor...",
        "time_remaining": "Kalan süre: {time}",
        "copying_file": "Kopyalanıyor...",
        "btn_pause": "Duraklat",
        "btn_resume": "Devam Et",
        "btn_stop": "Durdur ve Güvenli Çık",
        "backup_completed": "Yedekleme tamamlandı!",
        "backup_stopped": "Yedekleme durduruldu.",

        # Adım 3: Çift Dosya Temizliği
        "dup_title": "Diskteki Tekrar Eden Dosyaları Bul ve Temizle",
        "dup_sub": "Aynı ada ve dosya boyutuna sahip tekrar eden dosyalar bulunur. Silmeden önce onayınız alınır.",
        "dup_card_count": "Tekrar Eden Dosya",
        "dup_card_space": "Kurtarılacak Alan",
        "dup_card_unique": "Benzersiz Dosya",
        "dup_card_total": "Toplam Dosya",
        "dup_found_title": "Bulunan Tekrarlar",
        "select_all": "Tümünü Seç",
        "sort_size_desc": "Boyuta Göre (Büyükten Küçüğe)",
        "sort_size_asc": "Boyuta Göre (Küçükten Büyüğe)",
        "tag_original": "Orijinal",
        "tag_duplicate": "Tekrar",
        "btn_delete_duplicates": "Seçilenleri Sil",
        "btn_rescan_duplicates": "Yeniden Tara",
        "dup_selected_info": "{count} dosya seçildi ({size})",

        # Adım 4: Telefon Temizleme
        "phone_clean_title": "Telefondaki Fotoğrafları Sil",
        "phone_clean_sub": "Seçilen disk yedeğinde zaten bulunan medya dosyaları silinecektir. Yalnızca yedekte mevcut olanlar seçilir.",
        "clean_date_title": "Silme Tarihi (Bu tarihe ve öncesine ait)",
        "clean_date_sub": "Telefon klasörü ve yedek klasörü 1. adımdan alınır.",
        "media_to_delete": "Silinecek Medya",
        "photos_count": "Fotoğraf",
        "videos_count": "Video",
        "total_count": "Toplam",
        "warning_title": "Önemli Bilgi",
        "warning_bullet_1": "• Yalnızca diskte zaten mevcut olan dosyalar silinecektir.",
        "warning_bullet_2": "• Silmeden önce sizden onay alınacaktır.",
        "warning_bullet_3": "• Silinen dosyalar telefonun geri dönüşüm kutusuna gitmez, doğrudan silinir.",
        "btn_find_phone_cleanup": "Silinebilecekleri Bul",
        "btn_start_phone_clean": "Silme İşlemini Başlat",
        "btn_back": "Geri",
    },
    "en": {
        # General & Headers
        "app_title": "PhotoMatch | Android & iPhone -> Disk Backup",
        "app_subtitle": "Android & iPhone -> Disk Backup",
        "device_android": "📱 Android (ADB)",
        "device_ios": "🍏 Apple iPhone (iOS)",
        "ready": "Ready",
        "about": "About",
        "about_title": "About PhotoMatch",
        "about_desc": "PhotoMatch is a modern photo backup tool that transfers photos and videos from your Android and Apple iPhone devices to your computer, securely cleans backed-up media from your phone, and removes duplicates from your disk.\n\nVersion: 2.0 Pro\nDeveloper: Esra",

        # Sidebar Steps
        "step_1_title": "Scan Photos",
        "step_1_sub": "Find photos on phone",
        "step_2_title": "Backup",
        "step_2_sub": "Copy photos to disk",
        "step_3_title": "Clean Duplicates",
        "step_3_sub": "Check duplicates on disk",
        "step_4_title": "Clean Phone",
        "step_4_sub": "Delete up to selected date",

        # Step 1: Scan & Gallery
        "card_device_connected": "Device Status",
        "card_device_none": "Device Not Connected",
        "btn_test_device": "Test Device",
        "card_phone_folder": "Phone Folder",
        "card_phone_folder_sub": "Select folder to scan on phone",
        "card_target_folder": "Backup Folder",
        "card_target_folder_sub": "Select target backup disk folder",
        "btn_browse": "Browse",
        "btn_scan": "Scan Photos",
        "btn_scan_again": "Scan Again",
        "scanning": "Scanning...",

        "folders_title": "Folders",
        "all_folders": "All",
        "gallery_title": "Phone Gallery Preview",
        "gallery_sub": "Scanning media files on phone...",
        "gallery_search_placeholder": "Search photos...",
        "btn_filter": "Filter",
        "btn_load_more": "Load More →",
        "btn_go_backup": "Backup Selected →",

        "summary_title": "Scan Summary",
        "stat_total_media": "Total Media",
        "stat_new_photos": "New Photos",
        "stat_on_disk": "Already on Disk",
        "stat_duplicates": "Duplicates",
        "files_found": "Found {count} photos and videos.",
        "on_disk_label": "On Disk",
        "new_label": "New",

        # Step 2: Backup
        "backup_running_title": "Photos Backing Up to Disk",
        "backup_running_sub": "Selected media files are safely copying to disk.",
        "backup_source": "Source",
        "backup_target": "Target",
        "btn_open_folder": "Open Folder",
        "backup_progress_text": "Copying {copied} / {total} photos...",
        "time_remaining": "Time remaining: {time}",
        "copying_file": "Copying...",
        "btn_pause": "Pause",
        "btn_resume": "Resume",
        "btn_stop": "Stop & Safe Exit",
        "backup_completed": "Backup finished successfully!",
        "backup_stopped": "Backup stopped.",

        # Step 3: Duplicate Cleanup
        "dup_title": "Find & Clean Duplicate Files on Disk",
        "dup_sub": "Files with matching names and sizes will be listed. You will be prompted before deletion.",
        "dup_card_count": "Duplicate Files",
        "dup_card_space": "Space to Recover",
        "dup_card_unique": "Unique Files",
        "dup_card_total": "Total Files",
        "dup_found_title": "Duplicates Found",
        "select_all": "Select All",
        "sort_size_desc": "By Size (Largest First)",
        "sort_size_asc": "By Size (Smallest First)",
        "tag_original": "Original",
        "tag_duplicate": "Duplicate",
        "btn_delete_duplicates": "Delete Selected",
        "btn_rescan_duplicates": "Rescan",
        "dup_selected_info": "{count} files selected ({size})",

        # Step 4: Phone Cleanup
        "phone_clean_title": "Delete Photos From Phone",
        "phone_clean_sub": "Only media files that already exist on your backup disk will be eligible for phone deletion.",
        "clean_date_title": "Cutoff Date (On or before this date)",
        "clean_date_sub": "Phone and backup folders are taken from step 1.",
        "media_to_delete": "Media to Delete",
        "photos_count": "Photos",
        "videos_count": "Videos",
        "total_count": "Total",
        "warning_title": "Important Notice",
        "warning_bullet_1": "• Only files already backed up on disk will be deleted.",
        "warning_bullet_2": "• Confirmation will be asked before deletion starts.",
        "warning_bullet_3": "• Deleted files bypass the trash bin and are removed directly.",
        "btn_find_phone_cleanup": "Find Deletable Files",
        "btn_start_phone_clean": "Start Phone Cleanup",
        "btn_back": "Back",
    },
    "de": {
        # Deutsch
        "app_title": "PhotoMatch | Android & iPhone -> Festplatten-Backup",
        "app_subtitle": "Android & iPhone -> Festplatten-Backup",
        "device_android": "📱 Android (ADB)",
        "device_ios": "🍏 Apple iPhone (iOS)",
        "ready": "Bereit",
        "about": "Über",
        "about_title": "Über PhotoMatch",
        "about_desc": "PhotoMatch sichert Fotos und Videos von Android- und iPhone-Geräten auf Ihren PC, entfernt Duplikate und bereinigt gesicherte Fotos vom Smartphone.\n\nVersion: 2.0 Pro\nEntwickler: Esra",

        "step_1_title": "Fotos Scannen",
        "step_1_sub": "Fotos auf dem Smartphone finden",
        "step_2_title": "Sichern",
        "step_2_sub": "Fotos auf die Festplatte kopieren",
        "step_3_title": "Duplikate Bereinigen",
        "step_3_sub": "Festplatten-Duplikate prüfen",
        "step_4_title": "Telefon Bereinigen",
        "step_4_sub": "Fotos bis Datum löschen",

        "card_device_connected": "Gerätestatus",
        "card_device_none": "Kein Gerät verbunden",
        "btn_test_device": "Gerät Testen",
        "card_phone_folder": "Smartphone-Ordner",
        "card_phone_folder_sub": "Zu scannenden Ordner wählen",
        "card_target_folder": "Backup-Ordner",
        "card_target_folder_sub": "Zielordner auf Festplatte wählen",
        "btn_browse": "Durchsuchen",
        "btn_scan": "Fotos Scannen",
        "btn_scan_again": "Erneut Scannen",
        "scanning": "Wird gescannt...",

        "folders_title": "Ordner",
        "all_folders": "Alle",
        "gallery_title": "Smartphone Galerie Vorschau",
        "gallery_sub": "Mediendateien werden gesucht...",
        "gallery_search_placeholder": "Fotos suchen...",
        "btn_filter": "Filtern",
        "btn_load_more": "Mehr Laden →",
        "btn_go_backup": "Auswahl Sichern →",

        "summary_title": "Scan-Zusammenfassung",
        "stat_total_media": "Gesamtmedien",
        "stat_new_photos": "Neue Fotos",
        "stat_on_disk": "Bereits Gesichert",
        "stat_duplicates": "Duplikate",
        "files_found": "{count} Fotos und Videos gefunden.",
        "on_disk_label": "Gesichert",
        "new_label": "Neu",

        "backup_running_title": "Fotos werden gesichert",
        "backup_running_sub": "Ausgewählte Medien werden kopiert.",
        "backup_source": "Quelle",
        "backup_target": "Ziel",
        "btn_open_folder": "Ordner Öffnen",
        "backup_progress_text": "{copied} / {total} Fotos werden kopiert...",
        "time_remaining": "Verbleibende Zeit: {time}",
        "copying_file": "Wird kopiert...",
        "btn_pause": "Pause",
        "btn_resume": "Fortsetzen",
        "btn_stop": "Sicher Stoppen",
        "backup_completed": "Backup erfolgreich abgeschlossen!",
        "backup_stopped": "Backup gestoppt.",

        "dup_title": "Duplikate auf der Festplatte finden & bereinigen",
        "dup_sub": "Gleiche Dateien werden aufgelistet. Vor dem Löschen erfolgt eine Bestätigung.",
        "dup_card_count": "Duplikate",
        "dup_card_space": "Freigebbarer Speicher",
        "dup_card_unique": "Einzigartige Dateien",
        "dup_card_total": "Dateien Gesamt",
        "dup_found_title": "Gefundene Duplikate",
        "select_all": "Alle Auswählen",
        "sort_size_desc": "Nach Größe (Absteigend)",
        "sort_size_asc": "Nach Größe (Aufsteigend)",
        "tag_original": "Original",
        "tag_duplicate": "Duplikat",
        "btn_delete_duplicates": "Ausgewählte Löschen",
        "btn_rescan_duplicates": "Erneut Scannen",
        "dup_selected_info": "{count} Dateien ausgewählt ({size})",

        "phone_clean_title": "Fotos vom Smartphone löschen",
        "phone_clean_sub": "Nur Dateien, die bereits auf der Festplatte gesichert sind, werden gelöscht.",
        "clean_date_title": "Stichtag (An oder vor diesem Datum)",
        "clean_date_sub": "Ordner werden aus Schritt 1 übernommen.",
        "media_to_delete": "Zu löschende Medien",
        "photos_count": "Fotos",
        "videos_count": "Videos",
        "total_count": "Gesamt",
        "warning_title": "Wichtiger Hinweis",
        "warning_bullet_1": "• Nur bereits gesicherte Dateien werden gelöscht.",
        "warning_bullet_2": "• Bestätigung wird vor dem Löschen angefordert.",
        "warning_bullet_3": "• Gelöschte Dateien werden endgültig entfernt.",
        "btn_find_phone_cleanup": "Löschbare Dateien Finden",
        "btn_start_phone_clean": "Löschvorgang Starten",
        "btn_back": "Zurück",
    },
    "es": {
        # Español
        "app_title": "PhotoMatch | Android & iPhone -> Copia de Seguridad",
        "app_subtitle": "Android & iPhone -> Copia de Seguridad",
        "device_android": "📱 Android (ADB)",
        "device_ios": "🍏 Apple iPhone (iOS)",
        "ready": "Listo",
        "about": "Acerca de",
        "about_title": "Acerca de PhotoMatch",
        "about_desc": "PhotoMatch transfiere fotos y vídeos desde dispositivos Android e iPhone a su PC, elimina duplicados y limpia fotos respaldadas.\n\nVersión: 2.0 Pro\nDesarrollador: Esra",

        "step_1_title": "Escanear Fotos",
        "step_1_sub": "Buscar fotos en el teléfono",
        "step_2_title": "Respaldar",
        "step_2_sub": "Copiar fotos al disco",
        "step_3_title": "Limpiar Duplicados",
        "step_3_sub": "Verificar duplicados en disco",
        "step_4_title": "Limpiar Teléfono",
        "step_4_sub": "Eliminar hasta fecha seleccionada",

        "card_device_connected": "Estado del Dispositivo",
        "card_device_none": "Dispositivo no conectado",
        "btn_test_device": "Probar Dispositivo",
        "card_phone_folder": "Carpeta del Teléfono",
        "card_phone_folder_sub": "Carpeta a escanear en el móvil",
        "card_target_folder": "Carpeta de Respaldo",
        "card_target_folder_sub": "Carpeta destino en el disco",
        "btn_browse": "Explorar",
        "btn_scan": "Escanear Fotos",
        "btn_scan_again": "Escanear de Nuevo",
        "scanning": "Escaneando...",

        "folders_title": "Carpetas",
        "all_folders": "Todas",
        "gallery_title": "Vista Previa de Galería",
        "gallery_sub": "Buscando fotos en el teléfono...",
        "gallery_search_placeholder": "Buscar fotos...",
        "btn_filter": "Filtrar",
        "btn_load_more": "Cargar Más →",
        "btn_go_backup": "Respaldar Selección →",

        "summary_title": "Resumen de Escaneo",
        "stat_total_media": "Total Medios",
        "stat_new_photos": "Fotos Nuevas",
        "stat_on_disk": "Ya Respaldadas",
        "stat_duplicates": "Duplicados",
        "files_found": "{count} fotos y vídeos encontrados.",
        "on_disk_label": "En Disco",
        "new_label": "Nuevo",

        "backup_running_title": "Respaldando Fotos en Disco",
        "backup_running_sub": "Los archivos seleccionados se están copiando de forma segura.",
        "backup_source": "Origen",
        "backup_target": "Destino",
        "btn_open_folder": "Abrir Carpeta",
        "backup_progress_text": "Copiando {copied} / {total} fotos...",
        "time_remaining": "Tiempo restante: {time}",
        "copying_file": "Copiando...",
        "btn_pause": "Pausar",
        "btn_resume": "Continuar",
        "btn_stop": "Detener de Forma Segura",
        "backup_completed": "¡Copia de seguridad completada!",
        "backup_stopped": "Copia de seguridad detenida.",

        "dup_title": "Buscar y Limpiar Archivos Duplicados",
        "dup_sub": "Se listan archivos idénticos en nombre y tamaño. Se pedirá confirmación antes de borrar.",
        "dup_card_count": "Archivos Duplicados",
        "dup_card_space": "Espacio a Recuperar",
        "dup_card_unique": "Archivos Únicos",
        "dup_card_total": "Total Archivos",
        "dup_found_title": "Duplicados Encontrados",
        "select_all": "Seleccionar Todos",
        "sort_size_desc": "Por Tamaño (Mayor a Menor)",
        "sort_size_asc": "Por Tamaño (Menor a Mayor)",
        "tag_original": "Original",
        "tag_duplicate": "Duplicado",
        "btn_delete_duplicates": "Eliminar Seleccionados",
        "btn_rescan_duplicates": "Escanear de Nuevo",
        "dup_selected_info": "{count} archivos seleccionados ({size})",

        "phone_clean_title": "Eliminar Fotos del Teléfono",
        "phone_clean_sub": "Solo los archivos respaldados previamente en disco podrán eliminarse.",
        "clean_date_title": "Fecha Límite (En o antes de esta fecha)",
        "clean_date_sub": "Las carpetas se toman del paso 1.",
        "media_to_delete": "Medios a Eliminar",
        "photos_count": "Fotos",
        "videos_count": "Vídeos",
        "total_count": "Total",
        "warning_title": "Aviso Importante",
        "warning_bullet_1": "• Solo se eliminarán archivos ya respaldados en el disco.",
        "warning_bullet_2": "• Se solicitará confirmación antes de iniciar la eliminación.",
        "warning_bullet_3": "• Los archivos eliminados se borran de forma permanente.",
        "btn_find_phone_cleanup": "Buscar Eliminables",
        "btn_start_phone_clean": "Iniciar Limpieza",
        "btn_back": "Volver",
    }
}

CURRENT_LANG = "tr"


def load_saved_lang() -> str:
    global CURRENT_LANG
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            saved = data.get("language")
            if saved in LANGUAGES:
                CURRENT_LANG = saved
    except Exception:
        pass
    return CURRENT_LANG


def save_lang(lang: str):
    global CURRENT_LANG
    if lang in LANGUAGES:
        CURRENT_LANG = lang
        try:
            CONFIG_FILE.write_text(json.dumps({"language": lang}, indent=2), encoding="utf-8")
        except Exception:
            pass


def get_current_lang() -> str:
    return CURRENT_LANG


def t(key: str, **kwargs) -> str:
    """Metin anahtarını mevcut dilde döndürür."""
    lang_dict = TRANSLATIONS.get(CURRENT_LANG, TRANSLATIONS["tr"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


load_saved_lang()
