"""
PhotoMatch - iOS / Apple iPhone Bağlantı Yöneticisi (Windows Portable Devices - WPD)
Windows Shell COM arayüzü (win32com) üzerinden Apple iPhone cihazlarına erişim,
fotoğraf/video tarama, aktarma ve önizleme işlemlerini yönetir.
"""

import os
import re
import time
from pathlib import Path
from datetime import datetime

try:
    import pythoncom
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HAS_HEIF = True
except Exception:
    HAS_HEIF = False

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".dng")
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".3gp", ".3gpp", ".avi", ".m4v", ".webm", ".mts", ".m2ts", ".ts")
MEDIA_EXTS = IMAGE_EXTS + VIDEO_EXTS


def is_available() -> bool:
    """Windows COM desteğinin mevcut olup olmadığını kontrol eder."""
    return HAS_WIN32COM and os.name == "nt"


def list_ios_devices() -> list[str]:
    """
    Windows üzerinde takılı olan Apple iPhone / iPad veya WPD kamera cihazlarını listeler.
    """
    if not is_available():
        return []

    pythoncom.CoInitialize()
    devices = []
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        my_pc = shell.NameSpace(17)  # ssfDRIVES (Bu Bilgisayar / This PC)
        if not my_pc:
            return []

        for item in my_pc.Items():
            p = str(item.Path)
            # Yerel sabit diskleri (C:, D:) atla
            if re.match(r"^[a-zA-Z]:", p) or ":\\" in p:
                continue

            name = item.Name
            name_lower = name.lower()

            # Apple / iPhone / iPad isim kontrolü
            if "iphone" in name_lower or "apple" in name_lower or "ipad" in name_lower:
                devices.append(name)
                continue

            # DCIM veya Internal Storage içeren taşınabilir cihazlar
            try:
                subfolder = item.GetFolder
                if subfolder:
                    for sub in subfolder.Items():
                        sub_low = sub.Name.lower()
                        if "internal" in sub_low or "dcim" in sub_low or "storage" in sub_low:
                            devices.append(name)
                            break
            except Exception:
                pass
    except Exception:
        pass
    finally:
        pythoncom.CoUninitialize()

    return devices


def _find_dcim_folder(folder, depth=0, max_depth=3):
    """Cihaz klasörü içinde DCIM klasörünü arar."""
    if depth > max_depth or not folder:
        return None

    try:
        for item in folder.Items():
            if item.IsFolder:
                if item.Name.upper() == "DCIM":
                    return item.GetFolder
                sub = item.GetFolder
                if sub:
                    found = _find_dcim_folder(sub, depth + 1, max_depth)
                    if found:
                        return found
    except Exception:
        pass
    return None


def scan_ios_media(device_name: str = "", progress_callback=None) -> list[dict]:
    """
    iPhone'daki tüm fotoğraf ve video dosyalarını tarar.
    Dönen her eleman bir sözlüktür:
      {
         'name': 'IMG_0001.HEIC',
         'rel_path': 'DCIM/100APPLE/IMG_0001.HEIC',
         'folder': 'DCIM/100APPLE',
         'size': 2451200,
         'modify_ts': 1718000000.0,
         'remote_path': 'ios://Apple iPhone/DCIM/100APPLE/IMG_0001.HEIC',
         'path_parts': ['Apple iPhone', 'Internal Storage', 'DCIM', '100APPLE', 'IMG_0001.HEIC']
      }
    """
    if not is_available():
        return []

    pythoncom.CoInitialize()
    items_found: list[dict] = []

    try:
        shell = win32com.client.Dispatch("Shell.Application")
        my_pc = shell.NameSpace(17)
        if not my_pc:
            return []

        # Cihazı bul
        target_device = None
        for it in my_pc.Items():
            if not device_name:
                if is_ios_or_target(it):
                    target_device = it
                    device_name = it.Name
                    break
            elif it.Name == device_name or it.Name.lower() == device_name.lower():
                target_device = it
                break

        if not target_device:
            return []

        dev_folder = target_device.GetFolder
        if not dev_folder:
            return []

        # DCIM klasörünü tespit et ve yol parçalarını oluştur
        dcim_parts = [device_name]
        dcim_folder = None

        # Doğrudan alt klasörleri tara (Genelde: Apple iPhone -> Internal Storage -> DCIM)
        for sub1 in dev_folder.Items():
            if sub1.IsFolder:
                if sub1.Name.upper() == "DCIM":
                    dcim_folder = sub1.GetFolder
                    dcim_parts.append(sub1.Name)
                    break
                sub1_f = sub1.GetFolder
                if sub1_f:
                    for sub2 in sub1_f.Items():
                        if sub2.IsFolder and sub2.Name.upper() == "DCIM":
                            dcim_folder = sub2.GetFolder
                            dcim_parts.extend([sub1.Name, sub2.Name])
                            break
                    if dcim_folder:
                        break

        root_folder = dcim_folder if dcim_folder else dev_folder
        root_rel = "DCIM" if dcim_folder else "Root"

        # DCIM altındaki albüm klasörlerini tara (100APPLE, 101APPLE vs.)
        queue = [(root_folder, root_rel, dcim_parts)]
        scanned_count = 0

        while queue:
            cur_folder, cur_rel, cur_parts = queue.pop(0)
            try:
                for it in cur_folder.Items():
                    if it.IsFolder:
                        sub_rel = f"{cur_rel}/{it.Name}"
                        sub_f = it.GetFolder
                        if sub_f:
                            queue.append((sub_f, sub_rel, cur_parts + [it.Name]))
                    else:
                        name = it.Name
                        lower = name.lower()
                        if lower.endswith(MEDIA_EXTS):
                            size = None
                            try:
                                size = int(it.Size)
                            except Exception:
                                pass

                            modify_ts = None
                            try:
                                mdate = it.ModifyDate
                                if mdate:
                                    # pywintypes.datetime to timestamp
                                    modify_ts = mdate.timestamp() if hasattr(mdate, "timestamp") else None
                            except Exception:
                                pass

                            item_parts = cur_parts + [name]
                            remote_p = f"ios://{'/'.join(item_parts)}"

                            items_found.append({
                                "name": name,
                                "rel_path": f"{cur_rel}/{name}",
                                "folder": cur_rel,
                                "size": size,
                                "modify_ts": modify_ts,
                                "remote_path": remote_p,
                                "path_parts": item_parts,
                            })

                            scanned_count += 1
                            if progress_callback and scanned_count % 50 == 0:
                                progress_callback(scanned_count)
            except Exception:
                continue

    finally:
        pythoncom.CoUninitialize()

    return items_found


def is_ios_or_target(item) -> bool:
    name = item.Name.lower()
    return "iphone" in name or "apple" in name or "ipad" in name


def _navigate_to_folder(shell, path_parts: list[str]):
    """
    path_parts listesindeki son eleman (dosya adı) hariç klasöre ulaşır.
    Döner: (Folder nesnesi, dosya adı)
    """
    if not path_parts:
        return None, None

    file_name = path_parts[-1]
    folder_parts = path_parts[:-1]

    cur = shell.NameSpace(17)  # ssfDRIVES
    if not cur:
        return None, None

    for part in folder_parts:
        found_folder = None
        for it in cur.Items():
            if it.Name == part or it.Name.lower() == part.lower():
                found_folder = it.GetFolder
                break
        if not found_folder:
            return None, None
        cur = found_folder

    return cur, file_name


def copy_ios_file(path_parts: list[str], target_local_file: Path, timeout: int = 180) -> tuple[bool, str]:
    """
    iPhone üzerindeki bir dosyayı yerel Windows diskine kopyalar.
    Windows Shell CopyHere mekanizmasını kullanır ve kopyalamanın bitmesini bekler.
    """
    if not is_available():
        return False, "Windows COM desteği bulunamadı."

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        folder, file_name = _navigate_to_folder(shell, path_parts)
        if not folder:
            return False, f"iPhone klasörü bulunamadı: {'/'.join(path_parts[:-1])}"

        # Dosya öğesini bul
        src_item = None
        try:
            src_item = folder.ParseName(file_name)
        except Exception:
            src_item = None

        if not src_item:
            # ParseName bulamadıysa klasördeki öğeler arasında ara
            for it in folder.Items():
                if it.Name == file_name or it.Name.lower() == file_name.lower():
                    src_item = it
                    break

        if not src_item:
            return False, f"iPhone üzerinde dosya bulunamadı: {file_name}"

        expected_size = None
        try:
            expected_size = int(src_item.Size)
        except Exception:
            pass

        target_local_file = Path(target_local_file).resolve()
        target_dir = target_local_file.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        dst_namespace = shell.NameSpace(str(target_dir))
        if not dst_namespace:
            return False, f"Hedef klasör açılamadı: {target_dir}"

        # Hedef dosya önceden varsa veya geçiciyse
        if target_local_file.exists():
            try:
                target_local_file.unlink()
            except Exception:
                pass

        # 4 = FOF_SILENT
        # 16 = FOF_NOCONFIRMATION (tüm onaylara evet)
        # 512 = FOF_NOCOPYSECURITYATTRIBS
        # 1024 = FOF_NOERRORUI (hata penceresi çıkarma)
        copy_flags = 4 | 16 | 512 | 1024
        dst_namespace.CopyHere(src_item, copy_flags)

        # Windows CopyHere asenkron çalıştığından dosyanın yazılmasını bekle
        start_time = time.time()
        last_size = -1
        stable_count = 0

        while time.time() - start_time < timeout:
            if target_local_file.exists():
                cur_size = target_local_file.stat().st_size
                if expected_size and expected_size > 0:
                    if cur_size >= expected_size:
                        return True, ""
                else:
                    if cur_size > 0:
                        if cur_size == last_size:
                            stable_count += 1
                            if stable_count >= 3:
                                return True, ""
                        else:
                            stable_count = 0
                            last_size = cur_size
            time.sleep(0.1)

        if target_local_file.exists() and target_local_file.stat().st_size > 0:
            return True, ""

        return False, f"Dosya kopyalama zaman aşımına uğradı ({timeout}s): {file_name}"

    except Exception as e:
        return False, str(e)
    finally:
        pythoncom.CoUninitialize()


def delete_ios_file(path_parts: list[str]) -> tuple[bool, str]:
    """
    iPhone üzerindeki bir dosyayı silmeyi dener.
    Not: Apple iOS güvenlik kuralları gereği, WPD üzerinden dosya silme
    yalnızca telefon kilidi açıkken ve cihaz izin verdiğinde mümkündür.
    """
    if not is_available():
        return False, "Windows COM desteği bulunamadı."

    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        folder, file_name = _navigate_to_folder(shell, path_parts)
        if not folder:
            return False, "Klasör bulunamadı."

        src_item = None
        for it in folder.Items():
            if it.Name == file_name or it.Name.lower() == file_name.lower():
                src_item = it
                break

        if not src_item:
            return False, "Dosya bulunamadı."

        # Shell delete komutunu çağır
        src_item.InvokeVerb("delete")
        return True, ""
    except Exception as e:
        return False, str(e)
    finally:
        pythoncom.CoUninitialize()
