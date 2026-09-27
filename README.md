# 📱 PhotoMatch — Android & Apple iPhone Photo Backup & Match Tool

Android ve Apple iPhone cihazlarındaki fotoğrafları ve videoları bilgisayara aktaran, yerel diskteki fotoğraflarla karşılaştıran ve kopyalananları telefon hafızasından güvenle temizleyen Python masaüstü uygulaması.

---

## 🚀 Özellikler

- **Çift Cihaz Desteği (Android & iPhone):**
  - **Android (ADB):** USB Hata Ayıklama üzerinden yüksek hızlı MediaStore ve find taraması.
  - **Apple iPhone (iOS):** Windows Taşınabilir Aygıtlar (WPD / Shell) protokolü ile doğrudan DCIM taraması.
- **Modern Fotoğraf Formatları:** Apple `.heic`, `.heif`, `.mov`, `.dng` ve tüm yaygın medya formatları için önizleme ve aktarım desteği (`pillow-heif`).
- **Akıllı Karşılaştırma:** Telefonda olup henüz bilgisayara yedeklenmemiş yeni medyaları otomatik ayıklar.
- **Disk Çift Dosya Temizliği:** Yedekleme klasöründeki mükerrer dosyaları bulur ve temizler.
- **Telefondan Güvenli Silme:** Yalnızca bilgisayara yedeklendiği kesinleşmiş eski medyaları belirtilen tarihe göre telefondan kaldırır.

---

## 🛠️ Kurulum

```bash
pip install -r requirements.txt
python main.py
```

### Android Gereksinimleri
- Telefonda **Geliştirici Seçenekleri** ve **USB Hata Ayıklama** açık olmalıdır.
- `adb_tools/adb.exe` proje klasöründe veya sistem PATH ortam değişkeninde bulunmalıdır.

### Apple iPhone (iOS) Gereksinimleri
- iPhone USB kablosuyla bilgisayara bağlanmalı, ekran kilidi açılmalı ve **"Bu Bilgisayara Güven"** onayı verilmelidir.

---

## 📦 Masaüstü Uygulaması (.EXE) Olarak Paketleme

Uygulamayı Python gerektirmeden bağımsız bir `.exe` olarak derlemek için:

```bash
python -m PyInstaller --noconsole --onefile --add-data "adb_tools;adb_tools" --collect-all customtkinter --collect-all pillow_heif --name "PhotoMatch" main.py
```

Derleme tamamlandığında `dist/` klasörü içinde tek tıkla çalıştırılabilir **`PhotoMatch.exe`** oluşacaktır.
